"""Dataset aggregations: overview, waiting list, attendance, and category breakdowns."""

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .rows import get_safe_row_attributes, safe_name


def split_into_parts(
    items: List[Any],
    base_title: str,
    chunk_size: int = 40,
) -> List[Tuple[int, int, str, List[Any]]]:
    """Splits a list of items into chunked parts when exceeding chunk_size."""
    total = len(items)
    if total <= chunk_size:
        return []
    num_parts = (total + chunk_size - 1) // chunk_size
    parts = []
    for part_idx in range(num_parts):
        part_num = part_idx + 1
        title = f"{base_title} (Part {part_num}/{num_parts}, Total: {total})"
        chunk = items[part_idx * chunk_size : (part_idx + 1) * chunk_size]
        parts.append((part_num, num_parts, title, chunk))
    return parts


def _make_agg_doc(
    doc_id: str,
    title: str,
    summary: str,
    content: str,
    aliases: List[str],
    keywords: List[str],
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "id": doc_id,
        "title": title,
        "category": "aggregation",
        "summary": summary,
        "content": content,
        "aliases": aliases,
        "keywords": keywords,
        "metadata": metadata,
        "is_active": True,
    }


def build_overview_document(
    filepath: Path,
    sub_title: str,
    clean_slug: str,
    headers: List[str],
    data_rows: List[List[str]],
    categorical_cols: Dict[int, Tuple[str, Counter]],
) -> Dict[str, Any]:
    """Generates a high-level statistical overview document for a tabular dataset."""
    safe_headers = [
        h for h in headers
        if not any(k in h.lower() for k in [
            "email", "phone", "mobile", "contact", "father", "parent",
            "guardian", "gender", "address", "dob", "birth",
        ])
    ]
    col_list_str = ", ".join(safe_headers or headers)
    overview_lines = [
        f"Dataset: {sub_title}",
        f"Source File: {filepath.name}",
        f"Total Records: {len(data_rows)}",
        f"Available Attributes: {col_list_str}",
        "",
        "Key Summary Statistics:",
    ]
    for _c_idx, (h, cnt) in categorical_cols.items():
        overview_lines.append(f"\nBreakdown of {h} ({len(cnt)} distinct categories):")
        for val, count in cnt.most_common(12):
            overview_lines.append(f"* {val}: {count} records")

    return {
        "id": f"table_{clean_slug}_overview",
        "title": f"{sub_title} - Dataset Overview",
        "category": "dataset_overview",
        "summary": f"Overview of {sub_title} ({len(data_rows)} records, columns: {col_list_str[:160]}).",
        "content": "\n".join(overview_lines),
        "aliases": [sub_title, f"{sub_title} Overview", f"{sub_title} Summary"],
        "keywords": ["dataset", "table", "overview", "summary"] + clean_slug.split("_"),
        "metadata": {"source": filepath.name, "total_records": len(data_rows)},
        "is_active": True,
    }


def build_waiting_list_documents(
    filepath: Path,
    sub_title: str,
    clean_slug: str,
    h: str,
    c_idx: int,
    data_rows: List[List[str]],
    name_col_idx: int,
    headers: List[str],
) -> List[Dict[str, Any]]:
    """Builds waiting list aggregation documents, chunked if necessary."""
    docs: List[Dict[str, Any]] = []
    wl_rows = [r for r in data_rows if len(r) > c_idx and "wait" in str(r[c_idx]).lower()]
    wl_entries = []
    for i, r in enumerate(wl_rows, 1):
        entity = safe_name(r[name_col_idx]) if len(r) > name_col_idx and r[name_col_idx] else f"Record {i}"
        safe_attrs = get_safe_row_attributes(r, headers, name_col_idx)
        attr_str = f" ({', '.join(safe_attrs[:5])})" if safe_attrs else ""
        wl_entries.append(f"{i}. {entity}{attr_str}")

    base_title = f"{sub_title} - Waiting List ({h})"
    parts = split_into_parts(wl_entries, base_title, chunk_size=40)
    if not parts:
        wl_lines = [
            f"{sub_title} - Waiting List ({h})", "",
            f"Total Students on Waiting List: {len(wl_rows)} students", "",
            "List of Waitlisted Entries:",
        ] + wl_entries + ["", f"Summary: Exactly {len(wl_rows)} entries are placed on the waiting list in {sub_title}."]

        docs.append(_make_agg_doc(
            f"table_{clean_slug}_waiting_list",
            f"{sub_title} - Waiting List ({h})",
            f"There are exactly {len(wl_rows)} students on the waiting list (waitlist) in {sub_title}.",
            "\n".join(wl_lines),
            [f"{sub_title} Waiting List", f"{sub_title} Waitlist", "Waiting List"],
            ["waiting", "list", "waitlist", "waitlisted", clean_slug],
            {"source": filepath.name, "waitlisted_count": len(wl_rows)},
        ))
    else:
        for part_idx, num_parts, part_title, chunk_entries in parts:
            chunk_lines = [
                f"{sub_title} - Waiting List ({h}) (Part {part_idx}/{num_parts})", "",
                f"Total Students on Waiting List: {len(wl_rows)} students (Displaying {len(chunk_entries)} in this part)", "",
                "List of Waitlisted Entries:",
            ] + chunk_entries + ["", f"Summary: Exactly {len(wl_rows)} total entries on the waiting list in {sub_title} (Part {part_idx}/{num_parts})."]
            docs.append(_make_agg_doc(
                f"table_{clean_slug}_waiting_list_part{part_idx}",
                part_title,
                f"Waiting list for {sub_title} ({len(wl_rows)} total, Part {part_idx}/{num_parts}).",
                "\n".join(chunk_lines),
                [f"{sub_title} Waiting List Part {part_idx}", f"{sub_title} Waitlist"],
                ["waiting", "list", "waitlist", "waitlisted", clean_slug],
                {"source": filepath.name, "waitlisted_count": len(wl_rows), "part": part_idx, "total_parts": num_parts},
            ))
    return docs


def build_attendance_documents(
    filepath: Path,
    sub_title: str,
    clean_slug: str,
    clean_h_key: str,
    h: str,
    c_idx: int,
    cnt: Counter,
    data_rows: List[List[str]],
    name_col_idx: int,
) -> List[Dict[str, Any]]:
    """Builds attendance summary aggregation documents, chunked if necessary."""
    docs: List[Dict[str, Any]] = []
    p_rows = [r for r in data_rows if len(r) > c_idx and str(r[c_idx]).upper() in ("P", "PRESENT")]
    p_entries = [
        f"{i}. {safe_name(r[name_col_idx]) if len(r) > name_col_idx and r[name_col_idx] else f'Entry {i}'}"
        for i, r in enumerate(p_rows, 1)
    ]

    base_title = f"{sub_title} - Attendance Summary ({h})"
    parts = split_into_parts(p_entries, base_title, chunk_size=40)
    if not parts:
        att_lines = [
            f"{sub_title} - Attendance Summary ({h})", "",
            f"Total Attendance Entries: {sum(cnt.values())}", "",
            "Attendance Breakdown:",
        ] + [f"* {val}: {count} candidates" for val, count in cnt.most_common()]
        if p_entries:
            att_lines.extend([f"\nCandidates Marked Present / 'P' ({len(p_entries)} total):"] + p_entries)

        docs.append(_make_agg_doc(
            f"table_{clean_slug}_attendance_{clean_h_key}",
            f"{sub_title} - Attendance Summary ({h})",
            f"Attendance summary for {sub_title} ({h}): " + ", ".join(f"{k}: {v}" for k, v in cnt.items()),
            "\n".join(att_lines),
            [f"{sub_title} Attendance", "Attendance Summary", "Attendance"],
            ["attendance", "present", "absent", "roster", clean_slug],
            {"source": filepath.name, "present_count": len(p_rows) if p_rows else 0},
        ))
    else:
        for part_idx, num_parts, part_title, chunk_entries in parts:
            att_lines = [
                f"{sub_title} - Attendance Summary ({h}) (Part {part_idx}/{num_parts})", "",
                f"Total Attendance Entries: {sum(cnt.values())} (Displaying {len(chunk_entries)} present in this part)", "",
                "Attendance Breakdown:",
            ] + [f"* {val}: {count} candidates" for val, count in cnt.most_common()] + [
                f"\nCandidates Marked Present (Part {part_idx}/{num_parts}, Total: {len(p_entries)}):"
            ] + chunk_entries

            docs.append(_make_agg_doc(
                f"table_{clean_slug}_attendance_{clean_h_key}_part{part_idx}",
                part_title,
                f"Attendance summary for {sub_title} ({h}) (Part {part_idx}/{num_parts}, {len(p_entries)} total present).",
                "\n".join(att_lines),
                [f"{sub_title} Attendance Part {part_idx}", "Attendance Summary"],
                ["attendance", "present", "absent", "roster", clean_slug],
                {"source": filepath.name, "present_count": len(p_rows), "part": part_idx, "total_parts": num_parts},
            ))
    return docs


def build_category_breakdown_documents(
    filepath: Path,
    sub_title: str,
    clean_slug: str,
    clean_h_key: str,
    h: str,
    c_idx: int,
    cnt: Counter,
    data_rows: List[List[str]],
    name_col_idx: int,
) -> List[Dict[str, Any]]:
    """Builds category group breakdowns and member lists, chunked if necessary."""
    docs: List[Dict[str, Any]] = []
    cat_lines = [
        f"{sub_title} - Breakdown by {h}", "",
        f"Distribution across {len(cnt)} categories:",
    ] + [f"* {val}: {count} records" for val, count in cnt.most_common()]

    by_cat = defaultdict(list)
    for r in data_rows:
        if len(r) > c_idx and r[c_idx]:
            entity = safe_name(r[name_col_idx]) if len(r) > name_col_idx and r[name_col_idx] else "Entry"
            by_cat[r[c_idx]].append(entity)

    for cat_val, names in sorted(by_cat.items(), key=lambda x: len(x[1]), reverse=True):
        cat_slug = re.sub(r"[^a-zA-Z0-9]+", "_", cat_val).strip("_").lower()
        base_title = f"{sub_title} - {h}: {cat_val}"
        parts = split_into_parts(names, base_title, chunk_size=40)
        if not parts:
            cat_lines.append(f"\n### {cat_val} ({len(names)} records):")
            cat_lines.append(", ".join(names))
        else:
            for part_idx, num_parts, part_title, chunk_names in parts:
                chunk_lines = [
                    f"{sub_title} - {h}: {cat_val} (Part {part_idx}/{num_parts})", "",
                    f"Total records in {cat_val}: {len(names)} (Displaying {len(chunk_names)} in this part)", "",
                    ", ".join(chunk_names),
                ]
                docs.append(_make_agg_doc(
                    f"table_{clean_slug}_{clean_h_key}_{cat_slug}_part{part_idx}",
                    part_title,
                    f"{sub_title} members for {cat_val} in {h} (Part {part_idx}/{num_parts}, {len(names)} total).",
                    "\n".join(chunk_lines),
                    [f"{sub_title} {cat_val}", f"{cat_val} {h}"],
                    [h.lower(), clean_slug, cat_slug, "breakdown"],
                    {"source": filepath.name, "column": h, "category_value": cat_val, "total_records": len(names)},
                ))

    docs.append(_make_agg_doc(
        f"table_{clean_slug}_{clean_h_key}",
        f"{sub_title} - Breakdown by {h}",
        f"{sub_title} breakdown across {len(cnt)} groups in {h}.",
        "\n".join(cat_lines),
        [f"{sub_title} {h}", f"{sub_title} by {h}"],
        [h.lower(), clean_slug, "breakdown", "category"],
        {"source": filepath.name, "column": h},
    ))
    return docs


def build_aggregate_documents(
    filepath: Path,
    sub_title: str,
    clean_slug: str,
    headers: List[str],
    data_rows: List[List[str]],
    name_col_idx: int,
    categorical_cols: Dict[int, Tuple[str, Counter]],
) -> List[Dict[str, Any]]:
    """Generates all aggregate documents (overview, waiting list, attendance, category breakdown) for a sheet."""
    docs: List[Dict[str, Any]] = [
        build_overview_document(filepath, sub_title, clean_slug, headers, data_rows, categorical_cols)
    ]
    for c_idx, (h, cnt) in categorical_cols.items():
        h_low = h.lower()
        clean_h_key = re.sub(r"[^a-zA-Z0-9]+", "_", h).strip("_").lower()

        if any("wait" in str(v).lower() for v in cnt):
            docs.extend(build_waiting_list_documents(filepath, sub_title, clean_slug, h, c_idx, data_rows, name_col_idx, headers))

        is_attendance = "attendance" in h_low or (len(cnt) <= 4 and set(cnt.keys()).issubset({"P", "A", "Present", "Absent", "p", "a"}))
        if is_attendance and len(cnt) <= 6:
            docs.extend(build_attendance_documents(filepath, sub_title, clean_slug, clean_h_key, h, c_idx, cnt, data_rows, name_col_idx))

        is_category = any(k in h_low for k in ["domain", "branch", "department", "category", "role", "section", "status", "result"])
        if is_category and len(cnt) <= 25:
            docs.extend(build_category_breakdown_documents(filepath, sub_title, clean_slug, clean_h_key, h, c_idx, cnt, data_rows, name_col_idx))
    return docs
