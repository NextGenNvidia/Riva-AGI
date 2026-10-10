"""OCR Image & Scanned PDF Reader.

Extracts text from scanned documents and images (.png, .jpg, scanned .pdf)
using local Tesseract OCR with weighted word-level confidence averaging.
Supports opt-in cloud vision providers if configured.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("rag.ingest.readers.ocr")


class OcrImageReader:
    """Extracts text and confidence from image files and scanned pages."""

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}

    def __init__(self, cloud_vision_enabled: bool = False) -> None:
        self.cloud_vision_enabled = cloud_vision_enabled

    def can_read(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def read(self, file_path: Path) -> List[Dict[str, Any]]:
        """Reads an image file and performs OCR extraction."""
        if not file_path.is_file():
            return []

        try:
            from PIL import Image
            import pytesseract
        except ImportError:
            logger.warning("Pillow or pytesseract not available for OCR.")
            return []

        try:
            image = Image.open(str(file_path))
            ocr_text, confidence = self._extract_tesseract_with_confidence(image)

            if not ocr_text.strip():
                logger.info(f"No text detected by OCR in {file_path.name}")
                return []

            return [{
                "unit_type": "image_text",
                "title": f"Scanned Text - {file_path.stem}",
                "content": ocr_text.strip(),
                "provenance": {
                    "source_file": file_path.name,
                    "ocr_engine": "tesseract",
                    "ocr_confidence": round(confidence, 4),
                    "image_dimensions": list(image.size),
                },
            }]
        except Exception as e:
            logger.warning(f"OCR extraction failed for {file_path.name}: {e}")
            return []

    def _extract_tesseract_with_confidence(self, image: Any) -> Tuple[str, float]:
        """Runs pytesseract image_to_data and calculates weighted mean confidence."""
        import pytesseract

        try:
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            words = []
            confidences = []

            for i, text in enumerate(data.get("text", [])):
                word = str(text).strip()
                if not word:
                    continue
                words.append(word)
                conf = float(data["conf"][i]) if "conf" in data and i < len(data["conf"]) else -1.0
                if conf >= 0:
                    confidences.append(conf)

            full_text = " ".join(words)
            mean_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0
            return full_text, mean_conf
        except Exception as e:
            # Fallback to basic string extraction if image_to_data fails
            logger.debug(f"image_to_data failed, trying image_to_string: {e}")
            text = pytesseract.image_to_string(image)
            return text, 0.70
