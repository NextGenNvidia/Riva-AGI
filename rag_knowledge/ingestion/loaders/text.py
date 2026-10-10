"""Text and Markdown document loader for RAG knowledge ingestion."""

from pathlib import Path
import re
from typing import Any, Dict, List


def load_text_or_markdown(filepath: Path) -> List[Dict[str, Any]]:
    """Loads plain text or Markdown files into sectioned knowledge documents."""
    if not filepath.is_file():
        return []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read().strip()
    if not text:
        return []

    sections = re.split(r"\n(?=#{1,3}\s+)", text)
    documents = []
    for idx, sec in enumerate(sections):
        lines = [line.strip() for line in sec.strip().split("\n") if line.strip()]
        if not lines:
            continue
        first_line = lines[0].lstrip("#").strip()
        title = first_line if first_line else f"{filepath.stem} #{idx + 1}"
        content = sec.strip()
        summary = lines[1] if len(lines) > 1 else content[:200]
        doc_id = f"doc_{filepath.stem}_{idx + 1}"

        documents.append({
            "id": doc_id,
            "title": title,
            "category": "document",
            "summary": summary,
            "content": content,
            "aliases": [title, filepath.stem],
            "keywords": ["document", filepath.stem],
            "metadata": {"source": filepath.name, "section_index": idx},
            "is_active": True,
        })
    return documents
