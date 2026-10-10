"""Dispatching loader for multi-format knowledge document ingestion."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ..joiner import StudentEntityJoiner
from ..readers.word import WordDocxReader
from ..tabular import load_generic_tabular_dataset
from .image import load_image_documents
from .json_docs import load_json_documents
from .pdf import load_pdf_documents
from .text import load_text_or_markdown


def load_word_documents(filepath: Path) -> List[Dict[str, Any]]:
    """Loads Word .docx documents into knowledge documents using WordDocxReader."""
    reader = WordDocxReader()
    units = reader.read(filepath)
    docs: List[Dict[str, Any]] = []
    clean_stem = re.sub(r"[^a-zA-Z0-9]+", "_", filepath.stem).strip("_").lower()
    for idx, u in enumerate(units):
        title = u.get("title") or f"{filepath.stem} #{idx + 1}"
        content = u.get("content", "").strip()
        summary = content.split("\n")[0][:200] if content else title
        doc_id = f"word_{clean_stem}_{idx + 1}"
        docs.append({
            "id": doc_id,
            "title": title,
            "category": "document",
            "summary": summary,
            "content": content,
            "aliases": [title, filepath.stem],
            "keywords": ["document", "word", filepath.stem] + (u.get("section", "").lower().split()),
            "metadata": {"source": filepath.name, **u.get("provenance", {})},
            "is_active": True,
        })
    return docs


def _load_single_file(
    source_path: Path,
    dtype: str,
    allow_cloud_vision: bool,
    safe_identifiers: Optional[Set[str]],
    known_private_values: Optional[Set[str]],
) -> List[Dict[str, Any]]:
    ext = source_path.suffix.lower()
    if dtype == "json" or ext == ".json":
        return load_json_documents(source_path)
    if ext in (".csv", ".tsv", ".xlsx", ".xls"):
        return load_generic_tabular_dataset(
            source_path,
            safe_identifiers=safe_identifiers,
            known_private_values=known_private_values,
        )
    if dtype in ("doc", "text", "markdown") or ext in (".md", ".txt"):
        return load_text_or_markdown(source_path)
    if dtype in ("word", "docx") or ext == ".docx":
        return load_word_documents(source_path)
    if dtype == "pdf" or ext == ".pdf":
        return load_pdf_documents(source_path)
    if dtype in ("image", "vision") or ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff"):
        return load_image_documents(source_path, allow_cloud_vision=allow_cloud_vision)
    return []


def _handle_student_join(
    source_path: Path,
    dtype: str,
    safe_identifiers: Optional[Set[str]],
    known_private_values: Optional[Set[str]],
) -> Tuple[List[Dict[str, Any]], Set[Path], Set[str], Set[str]]:
    docs: List[Dict[str, Any]] = []
    handled_files: Set[Path] = set()
    active_safe_ids = set(safe_identifiers) if safe_identifiers else set()
    active_private_vals = set(known_private_values) if known_private_values else set()

    has_uid = (source_path / "UID.xlsx").exists()
    has_nominal = any("Nominal" in f.name for f in source_path.glob("*.xlsx"))
    has_student = any("STUDENT" in f.name for f in source_path.glob("*.xlsx"))
    if dtype in ("student", "auto") and (has_uid or has_nominal or has_student):
        joiner = StudentEntityJoiner(source_path)
        student_docs = joiner.to_knowledge_documents()
        if student_docs:
            docs.extend(student_docs)
            active_safe_ids.update(joiner.safe_identifiers)
            active_private_vals.update(joiner.known_private_values)
            if safe_identifiers is not None:
                safe_identifiers.update(joiner.safe_identifiers)
            if known_private_values is not None:
                known_private_values.update(joiner.known_private_values)

            uid_path = source_path / "UID.xlsx"
            if uid_path.exists():
                handled_files.add(uid_path)
            for p in source_path.glob("*Nominal*.xlsx"):
                handled_files.add(p)
            for p in source_path.glob("*STUDENT*.xlsx"):
                handled_files.add(p)

    return docs, handled_files, active_safe_ids, active_private_vals


def _load_directory_sources(
    source_path: Path,
    dtype: str,
    allow_cloud_vision: bool,
    safe_identifiers: Optional[Set[str]],
    known_private_values: Optional[Set[str]],
) -> List[Dict[str, Any]]:
    docs, handled_files, active_safe_ids, active_private_vals = _handle_student_join(
        source_path, dtype, safe_identifiers, known_private_values
    )
    if dtype == "student":
        return docs

    for file in sorted(source_path.iterdir()):
        if not file.is_file() or file in handled_files:
            continue
        ext = file.suffix.lower()
        if ext == ".json":
            docs.extend(load_json_documents(file))
        elif ext in (".csv", ".tsv", ".xlsx", ".xls"):
            docs.extend(
                load_generic_tabular_dataset(
                    file,
                    safe_identifiers=active_safe_ids,
                    known_private_values=active_private_vals,
                )
            )
        elif ext in (".md", ".txt"):
            docs.extend(load_text_or_markdown(file))
        elif ext == ".docx":
            docs.extend(load_word_documents(file))
        elif ext == ".pdf":
            docs.extend(load_pdf_documents(file))
        elif ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff"):
            docs.extend(load_image_documents(file, allow_cloud_vision=allow_cloud_vision))

    return docs


def load_source_documents(
    source: Path,
    data_type: str = "auto",
    allow_cloud_vision: bool = False,
    safe_identifiers: Optional[Set[str]] = None,
    known_private_values: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """Loads knowledge documents from a file or folder supporting JSON, CSV, Markdown, text, Word, PDF, and Excel."""
    source_path = Path(source)
    dtype = (data_type or "auto").lower()

    if source_path.is_file():
        return _load_single_file(
            source_path,
            dtype=dtype,
            allow_cloud_vision=allow_cloud_vision,
            safe_identifiers=safe_identifiers,
            known_private_values=known_private_values,
        )

    if source_path.is_dir():
        return _load_directory_sources(
            source_path,
            dtype=dtype,
            allow_cloud_vision=allow_cloud_vision,
            safe_identifiers=safe_identifiers,
            known_private_values=known_private_values,
        )

    return []
