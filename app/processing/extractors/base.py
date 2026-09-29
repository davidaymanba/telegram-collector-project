from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.config import Settings


class ExtractionError(RuntimeError):
    pass


class OCRUnavailableError(ExtractionError):
    pass


@dataclass(slots=True)
class ExtractionResult:
    text: str
    method: str                  # embedded | ocr | docx | pptx | embedded+ocr
    pages: int | None = None
    ocr_pages: int = 0
    warnings: list[str] = field(default_factory=list)


def extract_text(path: Path, extension: str, settings: Settings) -> ExtractionResult:
    ext = extension.lower().lstrip(".")
    if ext == "pdf":
        from app.processing.extractors.pdf import extract_pdf

        return extract_pdf(path, settings)
    if ext in {"jpg", "jpeg", "png"}:
        from app.processing.extractors.image import extract_image

        return extract_image(path, settings)
    if ext == "docx":
        from app.processing.extractors.office import extract_docx

        return extract_docx(path)
    if ext == "pptx":
        from app.processing.extractors.office import extract_pptx

        return extract_pptx(path)
    raise ExtractionError(f"Unsupported extension for extraction: {ext!r}")
