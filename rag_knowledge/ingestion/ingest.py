"""Universal Data Ingestion Engine for RAG Knowledge.

This module acts as the public entry point and facade for the modularized
ingestion subsystem, re-exporting all loaders, tabular processors, pipeline
executors, and CLI utilities for backward compatibility.
"""

from pathlib import Path
from typing import Any, Dict, List

from .cli import build_arg_parser, handle_clear_action, main, resolve_source_path
from .config import (
    get_vision_api_key,
    get_vision_fallback_models,
    get_vision_model,
    is_cloud_vision_permitted,
)
from .joiner import StudentEntityJoiner, make_opaque_ref_id
from .loaders.dispatch import load_source_documents, load_word_documents
from .loaders.image import extract_image_text
from .loaders.image import load_image_documents as _load_img_docs
from .loaders.json_docs import load_json_documents
from .loaders.pdf import load_pdf_documents
from .loaders.text import load_text_or_markdown
from .pipeline import run_ingestion
from .privacy import (
    PrivacyGateError,
    assert_no_privacy_leaks,
    is_email_address,
    is_phone_number,
)
from .tabular import (
    _ID_COLUMN_PATTERN,
    _SENSITIVE_HEADER_KEYWORDS,
    build_aggregate_documents,
    build_attendance_documents,
    build_category_breakdown_documents,
    build_overview_document,
    build_row_documents,
    build_waiting_list_documents,
    find_categorical_columns,
    find_name_column,
    get_safe_row_attributes,
    is_id_header,
    is_sensitive_header,
    load_generic_tabular_dataset,
    open_tabular_sheets,
    safe_name,
    split_into_parts,
)
from .textutil import (
    clean_identifier,
    normalize_whitespace,
    slugify,
    to_title_case,
)

# Backward-compatibility aliases
assert_no_private_in_embedded_fields = assert_no_privacy_leaks
_safe_name = safe_name
_get_safe_row_attributes = get_safe_row_attributes


def load_image_documents(filepath: Path, allow_cloud_vision: bool = False) -> List[Dict[str, Any]]:
    """Loads knowledge documents from an image file, resolving extract_image_text dynamically."""
    return _load_img_docs(filepath, allow_cloud_vision=allow_cloud_vision, extractor=extract_image_text)


if __name__ == "__main__":
    main()
