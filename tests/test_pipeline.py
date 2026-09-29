from __future__ import annotations

import stat
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.enums import FileStatus
from app.database.models import Channel, Subject
from app.database.repositories import ClassificationRepository, ProcessingLogRepository
from app.processing.extractors.base import ExtractionError, extract_text
from app.processing.pipeline import Processor
from app.runtime.tesseract import find_tesseract, missing_languages
from tests.conftest import make_file
from tests.factories import make_docx, make_image_pdf, make_pdf, make_png, make_pptx

_TESS = find_tesseract()
requires_ocr = pytest.mark.skipif(
    _TESS is None or bool(missing_languages(_TESS, "ara+eng")),
    reason="tesseract with ara+eng not installed (brew install tesseract tesseract-lang)",
)


def incoming(settings: Settings, name: str) -> Path:
    settings.incoming_dir.mkdir(parents=True, exist_ok=True)
    return settings.incoming_dir / name


def test_extract_pdf_embedded(settings: Settings, tmp_path: Path) -> None:
    p = make_pdf(tmp_path / "a.pdf", ["Database Systems", "Lecture 1: SQL basics and ERD"])
    res = extract_text(p, "pdf", settings)
    assert res.method == "embedded" and "SQL basics" in res.text and res.pages == 1


def test_extract_docx_and_pptx(settings: Settings, tmp_path: Path) -> None:
    d = make_docx(tmp_path / "a.docx", ["تكليف رقم 1", "Database assignment"])
    res = extract_text(d, "docx", settings)
    assert "تكليف رقم 1" in res.text and "SQL joins" in res.text
    p = make_pptx(tmp_path / "a.pptx", [("Lecture 2", "Normalization"), ("محاضرة", "ERD")])
    res = extract_text(p, "pptx", settings)
    assert "Normalization" in res.text and "محاضرة" in res.text and res.pages == 2


def test_extract_errors(settings: Settings, tmp_path: Path) -> None:
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    with pytest.raises(ExtractionError):
        extract_text(bad, "pdf", settings)
    with pytest.raises(ExtractionError):
        extract_text(bad, "doc", settings)


def test_scanned_pdf_without_ocr_warns(settings: Settings, tmp_path: Path) -> None:
    settings.ocr_enabled = False
    p = make_image_pdf(tmp_path / "scan.pdf", "Database Lecture")
    res = extract_text(p, "pdf", settings)
    assert res.method == "embedded" and res.warnings


@requires_ocr
def test_ocr_image(settings: Settings, tmp_path: Path) -> None:
    p = make_png(tmp_path / "a.png", "Database Lecture")
    res = extract_text(p, "png", settings)
    assert res.method == "ocr" and "database" in res.text.lower()


@requires_ocr
def test_ocr_scanned_pdf_respects_page_limit(settings: Settings, tmp_path: Path) -> None:
    settings.ocr_max_pages = 1
    p = make_image_pdf(tmp_path / "scan.pdf", "Final Exam")
    res = extract_text(p, "pdf", settings)
    assert res.method == "ocr" and "exam" in res.text.lower()


def test_process_classifies_and_moves(settings: Settings, db: Session, channel: Channel,
                                      subjects: list[Subject]) -> None:
    path = make_pdf(incoming(settings, "1_1_DB101 Lecture 1.pdf"),
                    ["Database Systems course", "SQL, ERD, normalization"])
    f = make_file(db, channel, path, name="DB101 Lecture 1.pdf", msg_id=1)
    outcomes = Processor(settings, db).process_pending()
    assert [o.status for o in outcomes] == [FileStatus.CLASSIFIED]
    db.refresh(f)
    dest = Path(f.storage_path or "")
    assert dest.parent == settings.processed_dir / "DB101" / "lecture"
    assert dest.exists() and not path.exists()
    text_path = Path(f.extracted_text_path or "")
    assert text_path == settings.texts_dir / f"{f.id}.txt"
    assert stat.S_IMODE(text_path.stat().st_mode) == 0o600
    assert "normalization" in text_path.read_text(encoding="utf-8")
    cls = ClassificationRepository(db).get_for_file(f.id)
    assert cls is not None and cls.classifier_version == "rules-v1" and cls.confidence == 0.9
    stages = [(x.stage, x.status.value) for x in ProcessingLogRepository(db).for_file(f.id)]
    assert stages == [("extract", "success"), ("classify", "success"), ("move", "success")]


def test_process_unclassified_goes_to_unclassified(settings: Settings, db: Session,
                                                   channel: Channel,
                                                   subjects: list[Subject]) -> None:
    path = make_docx(incoming(settings, "x.docx"), ["some unrelated text"])
    f = make_file(db, channel, path, name="notes.docx", msg_id=1)
    Processor(settings, db).process_pending()
    db.refresh(f)
    assert f.status == FileStatus.UNCLASSIFIED
    assert Path(f.storage_path or "").parent == settings.unclassified_dir
    cls = ClassificationRepository(db).get_for_file(f.id)
    assert cls is not None and cls.reason == "AI provider is disabled"


def test_process_failure_is_recorded(settings: Settings, db: Session, channel: Channel,
                                     subjects: list[Subject]) -> None:
    bad = incoming(settings, "bad.pdf")
    bad.write_bytes(b"garbage")
    good = make_pptx(incoming(settings, "g.pptx"), [("CS101 Lecture 3", "algorithms")])
    f_bad = make_file(db, channel, bad, name="bad.pdf", msg_id=1)
    f_good = make_file(db, channel, good, name="CS101 Lecture 3.pptx", msg_id=2)
    outcomes = Processor(settings, db).process_pending()
    assert [o.status for o in outcomes] == [FileStatus.FAILED, FileStatus.CLASSIFIED]
    db.refresh(f_bad)
    db.refresh(f_good)
    assert f_bad.status == FileStatus.FAILED and "PDF" in (f_bad.error_message or "")
    assert f_good.status == FileStatus.CLASSIFIED


def test_process_limit_and_skips_non_pending(settings: Settings, db: Session, channel: Channel,
                                             subjects: list[Subject]) -> None:
    for i in range(3):
        p = make_pdf(incoming(settings, f"{i}.pdf"), [f"DB101 lecture {i} database sql text"])
        make_file(db, channel, p, name=f"DB101 lecture {i}.pdf", msg_id=i + 1)
    make_file(db, channel, None, name="dup.pdf", msg_id=9, status=FileStatus.DUPLICATE)
    assert len(Processor(settings, db).process_pending(limit=2)) == 2
    assert len(Processor(settings, db).process_pending()) == 1
    assert Processor(settings, db).process_pending() == []


def test_reclassify_after_subject_added(settings: Settings, db: Session, channel: Channel) -> None:
    path = make_pdf(incoming(settings, "n.pdf"), ["Networks lecture: TCP/IP and OSI model"])
    f = make_file(db, channel, path, name="Networks lecture 1.pdf", msg_id=1)
    Processor(settings, db).process_pending()
    db.refresh(f)
    assert f.status.value == "unclassified"

    db.add(Subject(code="NET301", name_ar="شبكات الحاسب", name_en="Computer Networks",
                   keywords=["networks", "tcp"]))
    db.commit()
    Processor(settings, db).reclassify(statuses=[FileStatus.UNCLASSIFIED])
    db.refresh(f)
    assert f.status == FileStatus.CLASSIFIED
    assert Path(f.storage_path or "").parent == settings.processed_dir / "NET301" / "lecture"


def test_manual_classification(settings: Settings, db: Session, channel: Channel,
                               subjects: list[Subject]) -> None:
    path = make_pdf(incoming(settings, "m.pdf"), ["random"])
    f = make_file(db, channel, path, name="m.pdf", msg_id=1)
    Processor(settings, db).process_pending()
    db.refresh(f)
    Processor(settings, db).manual_classify(f, "CS101", "summary")
    db.refresh(f)
    cls = ClassificationRepository(db).get_for_file(f.id)
    assert cls is not None and cls.classifier_version == "manual" and cls.confidence == 1.0
    assert f.status == FileStatus.CLASSIFIED
    assert Path(f.storage_path or "").parent == settings.processed_dir / "CS101" / "summary"
