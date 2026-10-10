"""Tabular row extraction, privacy masking, and record document generation."""

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ..privacy import is_email_address, is_phone_number
from ..textutil import clean_identifier
from .columns import _ID_COLUMN_PATTERN, is_id_header, is_sensitive_header


def safe_name(raw: str) -> str:
    """Strips email domains and phone numbers from raw entity names."""
    clean = raw.split("@")[0] if "@" in raw else raw
    clean = re.sub(r"\+?\d{10,12}", "", clean).strip()
    return clean if clean else "Candidate"


def get_safe_row_attributes(
    r_row: List[str],
    headers: List[str],
    name_col_idx: int,
) -> List[str]:
    """Extracts non-sensitive attribute key-value pairs for aggregation entries."""
    attrs = []
    for ci in range(len(r_row)):
        if ci != name_col_idx and ci < len(headers) and r_row[ci]:
            if is_sensitive_header(headers[ci]):
                continue
            v = str(r_row[ci]).strip()
            if is_email_address(v) or is_phone_number(v):
                continue
            attrs.append(f"{headers[ci]}: {v}")
    return attrs


def _extract_row_fields(
    r: List[str],
    headers: List[str],
    safe_clean: Set[str],
    private_digits: Set[str],
    row_contact_digits: Set[str],
) -> Tuple[List[str], Dict[str, Any], Optional[str]]:
    row_fields: List[str] = []
    row_meta: Dict[str, Any] = {}
    id_val: Optional[str] = None

    for ci, h in enumerate(headers):
        if ci < len(r) and r[ci]:
            val = str(r[ci]).strip()
            is_contact_header = is_sensitive_header(h)
            is_id_col = is_id_header(h) and not is_contact_header

            if is_contact_header or is_email_address(val):
                continue

            digits = re.sub(r"[^\d]", "", val)
            is_known_phone = bool(
                len(digits) >= 10 and (digits in row_contact_digits or digits in private_digits)
            )
            val_is_safe = bool(
                safe_clean and (val.upper() in safe_clean or clean_identifier(val).upper() in safe_clean)
            )

            if is_id_col:
                if is_known_phone and not val_is_safe:
                    continue
                if not id_val:
                    id_val = clean_identifier(val)
            else:
                if is_phone_number(val) and not val_is_safe:
                    continue
                if (
                    len(digits) >= 10
                    and (val.startswith("+") or digits.startswith(("6", "7", "8", "9")))
                    and not val_is_safe
                ):
                    continue

            row_meta[h] = val
            row_fields.append(f"* **{h}**: {val}")

    return row_fields, row_meta, id_val


def build_row_documents(
    filepath: Path,
    sub_title: str,
    clean_slug: str,
    headers: List[str],
    data_rows: List[List[str]],
    name_col_idx: int,
    safe_clean: Set[str],
    private_digits: Set[str],
) -> List[Dict[str, Any]]:
    """Builds individual record documents for each row in a tabular dataset."""
    documents: List[Dict[str, Any]] = []

    for idx, r in enumerate(data_rows):
        entity_name = r[name_col_idx] if len(r) > name_col_idx and r[name_col_idx] else f"Record #{idx + 1}"
        if not entity_name or entity_name.lower() in ("not found", "none", "nan"):
            continue

        row_contact_digits: Set[str] = set()
        for ci, h in enumerate(headers):
            if ci < len(r) and r[ci]:
                val_str = str(r[ci]).strip()
                if is_sensitive_header(h):
                    digs = re.sub(r"[^\d]", "", val_str)
                    if len(digs) >= 10:
                        row_contact_digits.add(digs)

        row_fields, meta_fields, id_val = _extract_row_fields(
            r, headers, safe_clean, private_digits, row_contact_digits
        )
        if not row_fields:
            continue

        row_meta = {"source": filepath.name, "row_index": idx + 1, **meta_fields}
        entity_title = f"{entity_name} - {sub_title}"
        row_content = f"### {entity_name}\n**Dataset**: {sub_title}\n\n" + "\n".join(row_fields)
        clean_entity_id = re.sub(r"[^a-zA-Z0-9]+", "_", entity_name).strip("_").lower()

        if id_val:
            doc_seed = f"{clean_slug}_{id_val}"
        else:
            doc_seed = f"{clean_slug}_{clean_entity_id}"
        stable_doc_id = f"rec_{clean_slug[:16]}_{hashlib.sha256(doc_seed.encode()).hexdigest()[:16]}"

        documents.append({
            "id": stable_doc_id,
            "title": entity_title[:120],
            "category": "record",
            "summary": f"Record for {entity_name} in {sub_title}. " + "; ".join(row_fields[:3])[:180],
            "content": row_content,
            "aliases": [entity_name, entity_title[:120]],
            "keywords": ["record", clean_slug] + entity_name.lower().split(),
            "metadata": row_meta,
            "is_active": True,
        })

    return documents
