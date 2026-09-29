from __future__ import annotations

from pathlib import Path

import pytesseract
from PIL import Image, ImageOps

from app.config import Settings
from app.processing.extractors.base import ExtractionResult, OCRUnavailableError
from app.runtime.tesseract import find_tesseract, missing_languages

MAX_OCR_PIXELS = 40_000_000


def configure_tesseract(settings: Settings) -> None:
    if not settings.ocr_enabled:
        raise OCRUnavailableError("OCR is disabled (TUC_OCR_ENABLED=false)")
    cmd = find_tesseract(settings.tesseract_cmd)
    if not cmd:
        raise OCRUnavailableError("tesseract not found (brew install tesseract tesseract-lang)")
    missing = missing_languages(cmd, settings.ocr_language)
    if missing:
        raise OCRUnavailableError(f"tesseract language data missing: {', '.join(missing)}")
    pytesseract.pytesseract.tesseract_cmd = cmd


def ocr_image(image: Image.Image, settings: Settings) -> str:
    image = ImageOps.exif_transpose(image) or image
    if image.mode not in ("L", "RGB"):
        image = image.convert("RGB")
    w, h = image.size
    if w * h > MAX_OCR_PIXELS:
        scale = (MAX_OCR_PIXELS / (w * h)) ** 0.5
        image = image.resize((int(w * scale), int(h * scale)))
    return str(pytesseract.image_to_string(image, lang=settings.ocr_language, timeout=120))


def extract_image(path: Path, settings: Settings) -> ExtractionResult:
    configure_tesseract(settings)
    with Image.open(path) as img:
        text = ocr_image(img, settings)
    return ExtractionResult(text=text, method="ocr", pages=1, ocr_pages=1)
