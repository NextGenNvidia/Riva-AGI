"""JSON document loader for RAG knowledge ingestion."""

import json
from pathlib import Path
from typing import Any, Dict, List


def load_json_documents(filepath: Path) -> List[Dict[str, Any]]:
    """Loads documents or Q&A pairs from a JSON file."""
    if not filepath.is_file():
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    documents = []
    items = data if isinstance(data, list) else [data]
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("question") or f"{filepath.stem} #{idx + 1}"
        content = item.get("content") or item.get("answer") or str(item)
        summary = item.get("summary") or item.get("answer") or content[:200]
        doc_id = str(item.get("id") or f"doc_{filepath.stem}_{idx + 1}")
        category = item.get("category") or "general"
        keywords = item.get("keywords") or [category]
        aliases = item.get("aliases") or [title]

        documents.append({
            "id": doc_id,
            "title": title,
            "category": category,
            "summary": summary,
            "content": content,
            "aliases": aliases,
            "keywords": keywords,
            "metadata": item.get("metadata", {}),
            "is_active": bool(item.get("is_active", True)),
        })
    return documents
