"""Pre-Ingestion Student Entity Joiner."""

from collections import Counter
import hashlib
import hmac
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import openpyxl

from rag_knowledge.ingestion.privacy import is_email_address, is_phone_number

logger = logging.getLogger("rag.ingest.joiner")


def normalize_clean_str(text: Optional[Any]) -> str:
    """Collapses whitespace and trims text."""
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def clean_identifier(val: Optional[Any]) -> str:
    """Sanitizes an alphanumeric identifier (uppercase, stripped)."""
    if val is None:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", str(val)).upper()


def normalize_person_name(name: str) -> str:
    """Normalizes person name to Title Case for consistent join matching."""
    clean = normalize_clean_str(name)
    if not clean:
        return ""
    parts = clean.split(" ")
    capitalized = []
    for p in parts:
        if p.upper() in {"I", "II", "III", "IV", "CSE", "CSIT", "IT", "ECE", "ME", "AIML", "AI"}:
            capitalized.append(p.upper())
        else:
            capitalized.append(p.capitalize())
    return " ".join(capitalized)


_WARNED_SECRET_UNSET = False


def make_opaque_ref_id(primary_key: str, secret_key: Optional[str] = None) -> str:
    """Creates a deterministic, non-reversible synthetic reference ID using HMAC-SHA256."""
    global _WARNED_SECRET_UNSET
    secret = secret_key or os.getenv("RAG_ENTITY_SECRET", "").strip()
    if not secret:
        if not _WARNED_SECRET_UNSET:
            logger.warning(
                "CRITICAL SECURITY WARNING: 'RAG_ENTITY_SECRET' environment variable is NOT set! "
                "Using fallback ephemeral secret. Hashes may be vulnerable or inconsistent across deployments. "
                "Set RAG_ENTITY_SECRET in production."
            )
            _WARNED_SECRET_UNSET = True
        secret = "riva_ephemeral_entity_salt_2026_change_in_production"
    digest = hmac.new(
        secret.encode("utf-8"),
        str(primary_key).strip().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"ref_{digest[:16]}"


def get_known_core_members() -> Set[str]:
    """Retrieves normalized set of known core team member names from environment."""
    val = os.getenv("CORE_MEMBERS", "").strip()
    return {m.strip().upper() for m in val.split(",") if m.strip()} if val else set()


class StudentEntityJoiner:

    """Merges disparate student spreadsheets into canonical, deduplicated entities."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.canonical_students: List[Dict[str, Any]] = []
        self.safe_identifiers: Set[str] = set()
        self.known_private_values: Set[str] = set()

    def build_joined_students(self) -> List[Dict[str, Any]]:
        """Loads and merges student datasets with strict namesake protection."""
        uid_file = self.data_dir / "UID.xlsx"
        nom_files = list(self.data_dir.glob("*Nominal*.xlsx"))
        master_files = list(self.data_dir.glob("*STUDENT*.xlsx"))

        uid_map = self._load_uid_file(uid_file) if uid_file.exists() else {}
        nom_map = self._load_nominal_roll(nom_files[0]) if nom_files else {}
        master_list = self._load_master_list(master_files[0]) if master_files else []

        name_counts = Counter(m["name"].upper() for m in master_list if m.get("name"))
        master_by_roll: Dict[str, Dict[str, Any]] = {}
        master_by_email: Dict[str, Dict[str, Any]] = {}
        master_by_unique_name: Dict[str, Dict[str, Any]] = {}

        for m in master_list:
            roll = m["roll_number"]
            name_u = m["name"].upper()
            email = m.get("in_memory_email", "").strip().lower()

            if roll:
                master_by_roll[roll] = m
                self.safe_identifiers.add(roll)

            if email and "@" in email and email not in master_by_email:
                master_by_email[email] = m

            if name_u and name_counts[name_u] == 1:
                master_by_unique_name[name_u] = m

        matched_both_count = 0
        merged_entities: Dict[str, Dict[str, Any]] = {}
        processed_master_rolls: Set[str] = set()

        all_uids = set(uid_map.keys()) | set(nom_map.keys())
        for uid in sorted(all_uids):
            self.safe_identifiers.add(uid)
            u_info = uid_map.get(uid, {})
            n_info = nom_map.get(uid, {})

            display_name = n_info.get("name") or u_info.get("name") or ""
            name_u = display_name.upper()
            nom_email = n_info.get("in_memory_email", "").strip().lower()

            matched_master = None
            if nom_email and nom_email in master_by_email:
                matched_master = master_by_email[nom_email]
            elif name_u and name_u in master_by_unique_name:
                matched_master = master_by_unique_name[name_u]

            roll = matched_master["roll_number"] if matched_master else ""
            if roll:
                processed_master_rolls.add(roll)
                matched_both_count += 1

            branch = (matched_master.get("branch") if matched_master else "") or u_info.get("batch_name", "")
            degree = matched_master.get("degree", "") if matched_master else ""
            batch = (matched_master.get("academic_batch") if matched_master else "") or ""
            year = matched_master.get("year", "") if matched_master else ""
            sec = n_info.get("section") or (matched_master.get("section", "") if matched_master else "")
            sem = n_info.get("sem", "")
            mentor = n_info.get("mentor", "")
            status = matched_master.get("admission_status", "ACTIVE") if matched_master else "ACTIVE"

            for pv in [
                u_info.get("father_name"),
                n_info.get("father_name"),
                nom_email,
                n_info.get("phone"),
            ]:
                if pv and len(str(pv).strip()) >= 3:
                    self.known_private_values.add(str(pv).strip())

            ref_id = make_opaque_ref_id(roll or uid)

            entity_record = {
                "roll_number": roll,
                "student_uid": uid,
                "name": display_name,
                "degree": degree,
                "branch": branch,
                "academic_batch": batch,
                "year": year,
                "section": sec,
                "semester": sem,
                "mentor": mentor,
                "admission_status": status,
                "entity_ref_id": ref_id,
            }
            merged_entities[ref_id] = entity_record

        unmatched_master_count = 0
        for m in master_list:
            roll = m["roll_number"]
            if roll and roll in processed_master_rolls:
                continue

            unmatched_master_count += 1
            ref_id = make_opaque_ref_id(roll or m["name"])
            merged_entities[ref_id] = {
                "roll_number": roll,
                "student_uid": "",
                "name": m["name"],
                "degree": m.get("degree", ""),
                "branch": m.get("branch", ""),
                "academic_batch": m.get("academic_batch", ""),
                "year": m.get("year", ""),
                "section": m.get("section", ""),
                "semester": "",
                "mentor": "",
                "admission_status": m.get("admission_status", "ACTIVE"),
                "entity_ref_id": ref_id,
            }

            for pv in [m.get("phone"), m.get("in_memory_email"), m.get("father_name")]:
                if pv and len(str(pv).strip()) >= 3:
                    self.known_private_values.add(str(pv).strip())

        self.canonical_students = list(merged_entities.values())

        student_names = {s["name"].upper().strip() for s in self.canonical_students if s.get("name")}
        mentor_names = {s["mentor"].upper().strip() for s in self.canonical_students if s.get("mentor")}
        public_identities = student_names | mentor_names
        name_tokens = {token for pub in public_identities for token in pub.split() if len(token) >= 3}
        self.safe_identifiers.update(student_names)
        self.safe_identifiers.update(name_tokens)

        cleaned_private: Set[str] = set()
        for pv in self.known_private_values:
            pv_clean = str(pv).strip()
            if not pv_clean:
                continue
            if is_email_address(pv_clean) or is_phone_number(pv_clean):
                cleaned_private.add(pv_clean)
                continue
            pv_up = pv_clean.upper()
            if len(pv_clean.split()) < 2:
                continue
            is_public_name = (
                any(pv_up in pub or pub in pv_up for pub in public_identities if len(pub) >= 3)
                or pv_up in name_tokens
            )
            if not is_public_name:
                cleaned_private.add(pv_clean)

        self.known_private_values = cleaned_private

        logger.info(
            f"StudentEntityJoiner compiled {len(self.canonical_students)} students. "
            f"Both Roll+UID matched: {matched_both_count}, Master-only: {unmatched_master_count}. "
            f"Safe IDs: {len(self.safe_identifiers)}, Known Private Values: {len(self.known_private_values)}"
        )
        return self.canonical_students

    def to_knowledge_documents(self) -> List[Dict[str, Any]]:
        """Converts joined canonical student entities into standard RAG knowledge documents."""
        if not self.canonical_students:
            self.build_joined_students()

        inst_name = os.getenv("INSTITUTION_NAME", "").strip()
        core_members = get_known_core_members()
        documents = []
        for s in self.canonical_students:
            name = s.get("name", "")
            if not name:
                continue
            if name.upper().strip() in core_members:
                continue
            display_name = normalize_person_name(name)
            roll = s.get("roll_number", "")
            uid = s.get("student_uid", "")
            branch = s.get("branch", "")
            degree = s.get("degree", "")
            sec = s.get("section", "")
            sem = s.get("semester", "")
            mentor = s.get("mentor", "")
            batch = s.get("academic_batch", "")
            year = s.get("year", "")
            status = s.get("admission_status", "ACTIVE")
            ref_id = s.get("entity_ref_id") or make_opaque_ref_id(roll or uid or name)

            aliases = []
            if uid:
                aliases.append(uid)
            if roll:
                aliases.append(roll)
            if display_name:
                aliases.extend([display_name, display_name.upper(), display_name.lower()])

            keywords = ["student"]
            if branch:
                keywords.append(branch)
            if sec:
                keywords.extend([sec, f"section {sec}"])
            if mentor:
                keywords.extend([f"mentor {mentor}", mentor])
            if sem:
                keywords.append(f"sem {sem}")
            if batch:
                keywords.append(batch)

            parts = []
            degree_part = f"{degree} " if degree else ""
            year_part = f"Year {year} " if year else ""
            student_label = f"{year_part}{degree_part}student".strip()
            if branch:
                parts.append(f"{display_name} is a {student_label} in {branch}")
            else:
                parts.append(f"{display_name} is a {student_label}")

            details = []
            if sec:
                details.append(f"Section {sec}")
            if batch:
                details.append(f"Batch {batch}")
            if details:
                parts.append(f"({', '.join(details)})")
            if mentor:
                parts.append(f"mentored by {mentor}")
            if inst_name:
                parts.append(f"at {inst_name}.")
            else:
                parts[-1] = parts[-1].rstrip(".") + "."

            summary = " ".join(parts)

            content_lines = [f"Student Name: {display_name}"]
            if uid:
                content_lines.append(f"UID: {uid}")
            if roll:
                content_lines.append(f"University Roll Number: {roll}")
            if degree:
                content_lines.append(f"Degree: {degree}")
            if branch:
                content_lines.append(f"Branch: {branch}")
            if sec:
                content_lines.append(f"Class Section: {sec}")
            if sem:
                content_lines.append(f"Semester: Semester {sem}")
            if year:
                content_lines.append(f"Current Year: Year {year}")
            if mentor:
                content_lines.append(f"Faculty Mentor: {mentor}")
            if batch:
                content_lines.append(f"Academic Batch: {batch}")
            if status:
                content_lines.append(f"Admission Status: {status}")

            doc_id = f"student_{uid.lower()}" if uid else f"student_{roll.lower()}"
            title = f"{display_name} - {branch}" if branch else display_name

            doc_meta = {
                "name": display_name,
                "admission_status": status,
                "entity_ref_id": ref_id,
            }
            if uid:
                doc_meta["uid"] = uid
            if roll:
                doc_meta["roll_number"] = roll
            if branch:
                doc_meta["branch"] = branch
            if sec:
                doc_meta["section"] = sec
            if degree:
                doc_meta["degree"] = degree
            if batch:
                doc_meta["academic_batch"] = batch
            if sem:
                doc_meta["semester"] = sem
            if mentor:
                doc_meta["mentor"] = mentor

            documents.append({
                "id": doc_id,
                "category": "student",
                "title": title,
                "aliases": sorted(list(set(aliases))),
                "keywords": sorted(list(set(keywords))),
                "summary": summary,
                "content": "\n".join(content_lines),
                "metadata": doc_meta,
                "is_active": True,
            })
        return documents

    def _load_uid_file(self, path: Path) -> Dict[str, Dict[str, Any]]:
        wb = openpyxl.load_workbook(path, data_only=True)
        try:
            sheet = wb.active or wb.worksheets[0]
            records = {}
            for r in list(sheet.iter_rows(values_only=True))[1:]:
                if not r or len(r) < 6:
                    continue
                _, name_raw, father_raw, gender_raw, batch_raw, uid_raw = r[:6]
                uid = clean_identifier(uid_raw)
                if not uid or uid.lower() in {"uid", "studentuid", "none"}:
                    continue
                records[uid] = {
                    "uid": uid,
                    "name": normalize_person_name(name_raw),
                    "father_name": normalize_clean_str(father_raw),
                    "gender": normalize_clean_str(gender_raw).upper(),
                    "batch_name": normalize_clean_str(batch_raw),
                }
            return records
        finally:
            wb.close()

    def _load_nominal_roll(self, path: Path) -> Dict[str, Dict[str, Any]]:
        wb = openpyxl.load_workbook(path, data_only=True)
        try:
            sheet = wb.active or wb.worksheets[0]
            rows = list(sheet.iter_rows(values_only=True))

            header_idx = -1
            col_map: Dict[str, int] = {}
            for idx, r in enumerate(rows):
                if not r:
                    continue
                row_str = " ".join(str(c).lower() for c in r if c is not None)
                if "student uid" in row_str or "uid" in row_str:
                    header_idx = idx
                    for ci, c in enumerate(r):
                        if c is not None:
                            col_map[str(c).strip().lower()] = ci
                    break

            if header_idx == -1:
                logger.warning(f"No header with Student UID found in {path.name}")
                return {}

            records = {}
            for r in rows[header_idx + 1:]:
                if not r:
                    continue

                def _get(col_substr: str) -> str:
                    for k, ci in col_map.items():
                        if col_substr in k and ci < len(r) and r[ci] is not None:
                            return normalize_clean_str(r[ci])
                    return ""

                uid = clean_identifier(_get("uid"))
                name = normalize_person_name(_get("name"))
                if not uid or uid.lower() in {"uid", "studentuid", "none", "roll", "rollno", "rollnumber"} or name.lower() in {"name", "student name", "studentname", "candidate name"}:
                    continue

                records[uid] = {
                    "student_uid": uid,
                    "name": name,
                    "sem": _get("sem"),
                    "section": _get("sec"),
                    "phone": _get("phone"),
                    "in_memory_email": _get("email").lower(),
                    "father_name": _get("father"),
                    "mentor": normalize_person_name(_get("mentor")),
                }
            return records
        finally:
            wb.close()

    def _load_master_list(self, path: Path) -> List[Dict[str, Any]]:
        wb = openpyxl.load_workbook(path, data_only=True)
        try:
            sheet = wb.active or wb.worksheets[0]
            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                return []

            col_map: Dict[str, int] = {}
            header_idx = 0
            for idx, r in enumerate(rows[:5]):
                row_str = " ".join(str(c).lower() for c in r if c is not None)
                if "roll number" in row_str or "roll no" in row_str or "display name" in row_str:
                    header_idx = idx
                    for ci, c in enumerate(r):
                        if c is not None:
                            col_map[str(c).strip().lower()] = ci
                    break

            records = []
            for r in rows[header_idx + 1:]:
                if not r:
                    continue

                def _get(col_substr: str) -> str:
                    for k, ci in col_map.items():
                        if col_substr in k and ci < len(r) and r[ci] is not None:
                            return normalize_clean_str(r[ci])
                    return ""

                roll = clean_identifier(_get("roll"))
                name = normalize_person_name(_get("name"))
                if not roll and not name:
                    continue
                if roll.lower() in {"roll", "rollno", "rollnumber", "none"} or name.lower() in {"name", "student name", "studentname", "display name", "candidate name"}:
                    continue

                status = _get("status") or "ACTIVE"

                records.append({
                    "roll_number": roll,
                    "name": name,
                    "degree": _get("degree"),
                    "branch": _get("branch"),
                    "academic_batch": _get("batch"),
                    "year": _get("year"),
                    "section": _get("section"),
                    "admission_status": status,
                    "in_memory_email": _get("email").lower(),
                    "phone": _get("phone"),
                    "father_name": _get("father"),
                })
            return records
        finally:
            wb.close()
