"""Tabular column definitions and detection heuristics."""

import re
from collections import Counter
from typing import Dict, List, Tuple

_ID_COLUMN_PATTERN = re.compile(
    r"\b(?:id|uid|roll|urn|reg|registration|serial|sno|s_no|code|candidate_id|applicant_id|student_id|enrollment)\b",
    re.IGNORECASE,
)

_SENSITIVE_HEADER_KEYWORDS = (
    "email", "phone", "mobile", "contact",
    "father", "mother", "parent", "guardian",
    "gender", "address", "dob", "birth",
    "bank", "account", "ifsc", "caste", "aadhar", "pan", "salary", "income",
)


def is_sensitive_header(header: str) -> bool:
    """Checks if a column header refers to private contact, parental, or financial data."""
    h_low = str(header).lower()
    return any(k in h_low for k in _SENSITIVE_HEADER_KEYWORDS)


def is_id_header(header: str) -> bool:
    """Checks if a column header represents an ID or roll number, supporting underscores."""
    h_str = str(header)
    normalized = h_str.replace("_", " ")
    return bool(_ID_COLUMN_PATTERN.search(normalized) or _ID_COLUMN_PATTERN.search(h_str))


def find_name_column(headers: List[str], data_rows: List[List[str]]) -> int:
    """Detects the index of the primary name or entity column in tabular data."""
    name_col_idx = -1
    for i, h in enumerate(headers):
        h_low = h.lower()
        if "email" in h_low or "phone" in h_low or "mobile" in h_low:
            continue
        if h_low in ("name", "student name", "candidate name", "full name", "title", "applicant name"):
            name_col_idx = i
            break
    if name_col_idx == -1:
        for i, h in enumerate(headers):
            h_low = h.lower()
            if "email" in h_low or "phone" in h_low or "mobile" in h_low:
                continue
            if any(k in h_low for k in ["name", "candidate", "applicant", "student", "title", "event"]):
                name_col_idx = i
                break
    if name_col_idx == -1:
        for i, h in enumerate(headers):
            h_low = h.lower()
            if "email" in h_low or "phone" in h_low or "mobile" in h_low:
                continue
            vals = [r[i] for r in data_rows if len(r) > i and r[i]]
            if len(vals) > 0 and len(set(vals)) / len(vals) > 0.4 and not all(v.replace(".", "", 1).isdigit() for v in vals):
                name_col_idx = i
                break
    if name_col_idx == -1:
        name_col_idx = 0
    return name_col_idx


def find_categorical_columns(
    headers: List[str], data_rows: List[List[str]]
) -> Dict[int, Tuple[str, Counter]]:
    """Identifies low-cardinality categorical columns for aggregation generation."""
    categorical_cols: Dict[int, Tuple[str, Counter]] = {}
    for c_idx, h in enumerate(headers):
        h_low = h.lower()
        if any(
            k in h_low
            for k in [
                "email",
                "phone",
                "mobile",
                "contact",
                "father",
                "parent",
                "guardian",
                "gender",
                "address",
                "dob",
                "birth",
            ]
        ):
            continue
        vals = [
            r[c_idx]
            for r in data_rows
            if len(r) > c_idx and r[c_idx] and r[c_idx].lower() not in ("none", "not found", "-", "nan")
        ]
        if not vals:
            continue
        distinct = set(vals)
        if 1 <= len(distinct) <= 30 and (len(distinct) / len(vals) <= 0.65 or len(distinct) <= 10):
            categorical_cols[c_idx] = (h, Counter(vals))
    return categorical_cols
