"""Tabular data ingestion module."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ..textutil import normalize_whitespace
from .aggregates import (
    build_aggregate_documents,
    build_attendance_documents,
    build_category_breakdown_documents,
    build_overview_document,
    build_waiting_list_documents,
    split_into_parts,
)
from .columns import (
    _ID_COLUMN_PATTERN,
    _SENSITIVE_HEADER_KEYWORDS,
    find_categorical_columns,
    find_name_column,
    is_id_header,
    is_sensitive_header,
)
from .rows import (
    build_row_documents,
    get_safe_row_attributes,
    safe_name,
)
from .sheets import open_tabular_sheets


def load_generic_tabular_dataset(
    filepath: Path,
    max_row_docs: int = 1500,
    safe_identifiers: Optional[Set[str]] = None,
    known_private_values: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """Universal tabular ingestion engine for CSV, TSV, and Excel spreadsheets."""
    if not filepath.is_file():
        return []

    sheet_datasets = open_tabular_sheets(filepath)
    if not sheet_datasets:
        return []

    safe_clean = {str(s).strip().upper() for s in (safe_identifiers or set()) if s}
    private_digits = {
        re.sub(r"[^\d]", "", str(p))
        for p in (known_private_values or set())
        if p and len(re.sub(r"[^\d]", "", str(p))) >= 10
    }

    documents: List[Dict[str, Any]] = []

    for sub_title, raw_headers, data_rows in sheet_datasets:
        headers = [normalize_whitespace(h) for h in raw_headers]
        if not headers or not data_rows:
            continue

        name_col_idx = find_name_column(headers, data_rows)
        categorical_cols = find_categorical_columns(headers, data_rows)
        clean_slug = re.sub(r"[^a-zA-Z0-9]+", "_", sub_title).strip("_").lower()

        documents.extend(
            build_aggregate_documents(
                filepath, sub_title, clean_slug, headers, data_rows, name_col_idx, categorical_cols
            )
        )
        documents.extend(
            build_row_documents(
                filepath, sub_title, clean_slug, headers, data_rows, name_col_idx, safe_clean, private_digits
            )
        )

    return documents


__all__ = [
    "load_generic_tabular_dataset",
    "open_tabular_sheets",
    "is_sensitive_header",
    "is_id_header",
    "_ID_COLUMN_PATTERN",
    "_SENSITIVE_HEADER_KEYWORDS",
    "find_name_column",
    "find_categorical_columns",
    "safe_name",
    "get_safe_row_attributes",
    "build_row_documents",
    "build_aggregate_documents",
    "build_overview_document",
    "build_waiting_list_documents",
    "build_attendance_documents",
    "build_category_breakdown_documents",
    "split_into_parts",
]
