"""Image and vision document loader for RAG knowledge ingestion."""

import base64
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import urllib.error
import urllib.request

from ..config import (
    get_vision_api_key,
    get_vision_fallback_models,
    get_vision_model,
    is_cloud_vision_permitted,
)
from ..readers.ocr import OcrImageReader

logger = logging.getLogger("rag.ingest.loaders.image")


def _extract_gemini_vision(filepath: Path) -> Optional[str]:
    """Transcribes an image using the Google Gemini Vision API."""
    api_key = get_vision_api_key()
    if not api_key:
        return None

    ext = filepath.suffix.lower().lstrip(".")
    mime_map = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "gif": "image/gif",
        "bmp": "image/bmp",
    }
    mime_type = mime_map.get(ext, "image/png")

    try:
        with open(filepath, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        logger.warning(f"Failed to read image file for vision {filepath.name}: {e}")
        return None

    primary_model = get_vision_model()
    fallback_models = get_vision_fallback_models()
    model_candidates = ([primary_model] if primary_model else []) + fallback_models
    valid_models = []
    for m in model_candidates:
        if m and "live" not in m.lower() and m not in valid_models:
            valid_models.append(m)

    prompt_text = (
        "Transcribe and extract all content from this document/image accurately. "
        "Include all questions, numbered items, formulas, answers, solutions, tables, "
        "headings, and details in clean Markdown format."
    )

    for model_name in valid_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"inlineData": {"mimeType": mime_type, "data": b64_data}},
                        {"text": prompt_text},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 4096,
            },
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                cand = res.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                if cand.strip():
                    logger.info(f"Successfully extracted text from image {filepath.name} using Gemini Vision ({model_name}).")
                    return cand.strip()
        except urllib.error.HTTPError as he:
            logger.warning(f"Gemini Vision call for {model_name} HTTP {he.code}: {he.reason}")
            continue
        except Exception as ex:
            logger.warning(f"Gemini Vision call for {model_name} failed: {ex}")
            continue
    return None


def extract_image_text(filepath: Path, allow_cloud_vision: bool = False) -> Tuple[str, str, Any]:
    """Extracts textual content from an image via Gemini Vision or local OCR fallback."""
    cloud_opted_in = is_cloud_vision_permitted(filepath, allow_cloud_vision=allow_cloud_vision)

    if cloud_opted_in:
        gemini_text = _extract_gemini_vision(filepath)
        if gemini_text:
            return gemini_text, "gemini_vision", None

    try:
        ocr_reader = OcrImageReader()
        units = ocr_reader.read(filepath)
        if units and units[0].get("content"):
            ocr_text = units[0]["content"].strip()
            confidence = units[0].get("provenance", {}).get("ocr_confidence")
            logger.info(f"Extracted OCR text from {filepath.name} via local OCR (confidence={confidence}).")
            return ocr_text, "local_ocr", confidence
    except Exception as e:
        logger.warning(f"Local OCR failed or unavailable for {filepath.name}: {e}")

    if not cloud_opted_in:
        logger.info(f"Cloud vision is disabled for {filepath.name}. To enable, pass --cloud-vision or configure ALLOW_CLOUD_VISION.")

    logger.warning(f"No textual content could be extracted from image {filepath.name}. Skipping indexing.")
    return "", "none", None


def load_image_documents(
    filepath: Path,
    allow_cloud_vision: bool = False,
    extractor: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Loads knowledge documents from an image file using multimodal Vision or local OCR."""
    if not filepath.is_file():
        return []

    if extractor is not None:
        ext_fn = extractor
    else:
        import sys
        ingest_mod = sys.modules.get("rag_knowledge.ingestion.ingest")
        if ingest_mod and hasattr(ingest_mod, "extract_image_text"):
            ext_fn = getattr(ingest_mod, "extract_image_text")
        else:
            ext_fn = extract_image_text
    try:
        res = ext_fn(filepath, allow_cloud_vision=allow_cloud_vision)
    except TypeError:
        res = ext_fn(filepath)
    if isinstance(res, tuple):
        raw_text, method, confidence = res
    else:
        raw_text, method, confidence = str(res or ""), "custom", None

    if not raw_text or not raw_text.strip():
        return []

    conf_record = confidence if confidence is not None else "unknown"
    img_meta: Dict[str, Any] = {
        "source": filepath.name,
        "file_type": "image",
        "extraction_method": method,
        "confidence": conf_record,
    }
    if isinstance(confidence, (int, float)) and confidence < 0.6:
        img_meta["flagged_for_review"] = True

    try:
        from PIL import Image
        with Image.open(filepath) as img:
            img_meta["width"] = img.size[0]
            img_meta["height"] = img.size[1]
            img_meta["dimensions"] = f"{img.size[0]}x{img.size[1]}"
            img_meta["format"] = img.format or filepath.suffix.lstrip(".").upper()
    except Exception:
        pass

    documents = []
    clean_stem = re.sub(r"[^a-zA-Z0-9]+", "_", filepath.stem).strip("_").lower()

    raw_sections = [s.strip() for s in re.split(r"\n\s*---\s*\n", raw_text) if s.strip()]
    if len(raw_sections) <= 1:
        raw_sections = [s.strip() for s in re.split(r"\n(?=#{1,3}\s+)", raw_text) if s.strip()]

    extra_keywords = ["image", "transcription", clean_stem]
    if isinstance(confidence, (int, float)) and confidence < 0.6:
        extra_keywords.append("needs_review")

    if len(raw_sections) > 1:
        documents.append({
            "id": f"img_{clean_stem}_full",
            "title": f"{filepath.stem.replace('_', ' ').title()} - Full Content",
            "category": "document",
            "summary": f"Image transcription of {filepath.name} with {len(raw_sections)} sections.",
            "content": raw_text,
            "aliases": [filepath.stem, filepath.name],
            "keywords": extra_keywords,
            "metadata": dict(img_meta),
            "is_active": True,
        })
        for idx, sec in enumerate(raw_sections):
            lines = [l.strip() for l in sec.split("\n") if l.strip()]
            sec_title = lines[0].lstrip("#* -").rstrip("*").strip() if lines else f"Section {idx + 1}"
            if len(sec_title) > 80:
                sec_title = sec_title[:80] + "..."
            summary = lines[1] if len(lines) > 1 else sec[:200]
            sec_meta = dict(img_meta)
            sec_meta["section_index"] = idx + 1

            documents.append({
                "id": f"img_{clean_stem}_{idx + 1}",
                "title": f"{filepath.stem.replace('_', ' ').title()} - {sec_title}",
                "category": "document",
                "summary": summary[:250],
                "content": sec,
                "aliases": [sec_title, filepath.stem],
                "keywords": extra_keywords + [w.lower() for w in re.findall(r"\b[A-Za-z]{3,}\b", sec_title)[:5]],
                "metadata": sec_meta,
                "is_active": True,
            })
    else:
        clean_first = re.sub(r"[#*|`_-]+", " ", raw_text.splitlines()[0]).strip() if raw_text else ""
        title = f"{filepath.stem.replace('_', ' ').title()}"
        if clean_first and len(clean_first) < 80:
            title = f"{title} - {clean_first}"

        text_keywords = [w.lower() for w in re.findall(r"\b[A-Za-z0-9]{3,}\b", raw_text)[:30]]
        documents.append({
            "id": f"img_{clean_stem}_1",
            "title": title,
            "category": "document",
            "summary": raw_text[:250].replace("\n", " "),
            "content": raw_text,
            "aliases": [filepath.stem, filepath.name, title],
            "keywords": list(dict.fromkeys(extra_keywords + text_keywords)),
            "metadata": dict(img_meta),
            "is_active": True,
        })

    return documents
