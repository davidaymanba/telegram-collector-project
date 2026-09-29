from __future__ import annotations

import io
from pathlib import Path

import pymupdf
from PIL import Image

from app.config import Settings
from app.processing.extractors.base import ExtractionError, ExtractionResult, OCRUnavailableError
from app.processing.extractors.image import configure_tesseract, ocr_image

OCR_DPI = 200


def extract_pdf(path: Path, settings: Settings) -> ExtractionResult:
    try:
        doc = pymupdf.open(path)
    except Exception as exc:
        raise ExtractionError(f"Cannot open PDF: {exc}") from exc
    with doc:
        if doc.needs_pass:
            raise ExtractionError("PDF is password protected")
        page_count = doc.page_count
        embedded = "\n\n".join(doc[i].get_text("text") for i in range(page_count))
        if len(embedded.strip()) >= settings.min_pdf_text_chars:
            return ExtractionResult(text=embedded, method="embedded", pages=page_count)

        # Scanned / image-only PDF: OCR the first N pages.
        try:
            configure_tesseract(settings)
        except OCRUnavailableError as exc:
            return ExtractionResult(
                text=embedded, method="embedded", pages=page_count,
                warnings=[f"Embedded text below {settings.min_pdf_text_chars} chars; {exc}"],
            )
        limit = min(page_count, settings.ocr_max_pages)
        chunks: list[str] = []
        for index in range(limit):
            pix = doc[index].get_pixmap(dpi=OCR_DPI)
            with Image.open(io.BytesIO(pix.tobytes("png"))) as img:
                chunks.append(ocr_image(img, settings))
        warnings = []
        if page_count > limit:
            warnings.append(f"OCR limited to first {limit} of {page_count} pages")
        text = "\n\n".join(chunks)
        method = "ocr" if not embedded.strip() else "embedded+ocr"
        if embedded.strip():
            text = embedded + "\n\n" + text
        return ExtractionResult(text=text, method=method, pages=page_count, ocr_pages=limit,
                                warnings=warnings)
