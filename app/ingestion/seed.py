"""Realistic demo data so the dashboard can be explored before connecting Telegram.

Demo rows are tagged (`telegram_metadata.demo = true`, negative Telegram ids, `demo_` usernames)
and small real PDF files are written to storage so download/"Show in Finder" work too.
"""

from __future__ import annotations

import os
import random
from datetime import UTC, datetime, timedelta

import pymupdf
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.config.loaders import ConfigError, SubjectConfig, load_subjects
from app.database.enums import (
    CONTENT_TYPES,
    ChannelStatus,
    ClassificationStatus,
    FileStatus,
    ProcessingLogStatus,
    RunKind,
    RunTrigger,
)
from app.database.models import (
    Channel,
    Classification,
    CollectedFile,
    Message,
    ProcessingLog,
    ProcessingRun,
)
from app.ingestion.config_sync import import_subjects
from app.storage.paths import StorageLayout, write_private_text

DEMO_CHANNELS = [
    ("دفعة علوم الحاسب ٢٠٢٦", "demo_cs_batch"),
    ("ملخصات ومراجعات", "demo_summaries"),
    ("أرشيف الامتحانات", "demo_exams_archive"),
]
EXTRA_SUBJECTS = [
    SubjectConfig(code="MATH201", name_ar="الرياضيات المتقطعة", name_en="Discrete Mathematics",
                  keywords=["discrete", "رياضيات متقطعة", "graph theory", "logic"]),
    SubjectConfig(code="NET301", name_ar="شبكات الحاسب", name_en="Computer Networks",
                  keywords=["networks", "شبكات", "tcp", "osi"]),
    SubjectConfig(code="OS202", name_ar="نظم التشغيل", name_en="Operating Systems",
                  keywords=["operating systems", "نظم تشغيل", "scheduling"]),
]
TYPE_WORDS = {
    "lecture": ("محاضرة", "Lecture"),
    "previous_exam": ("امتحان نهائي", "Final Exam"),
    "assignment": ("تكليف", "Assignment"),
    "answer_model": ("نموذج إجابة", "Answer Key"),
    "summary": ("ملخص", "Summary"),
}


def _demo_pdf(path: os.PathLike[str], title: str, body: str) -> int:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 90), title, fontsize=18)
    page.insert_text((72, 130), body, fontsize=11)
    data = doc.tobytes()
    doc.close()
    with open(path, "wb") as fh:  # noqa: PTH123
        fh.write(data)
    os.chmod(path, 0o600)
    return len(data)


def clear_demo(session: Session) -> int:
    ids = list(session.scalars(select(Channel.id).where(Channel.username.like("demo\\_%"))))
    if ids:
        session.execute(delete(Channel).where(Channel.id.in_(ids)))
    session.execute(
        delete(ProcessingRun).where(ProcessingRun.metadata_json["demo"].as_boolean().is_(True))
    )
    session.flush()
    return len(ids)


def seed_demo(session: Session, settings: Settings, *, files: int = 140, reset: bool = False,
              seed: int = 7) -> dict[str, int]:
    rng = random.Random(seed)
    existing = session.scalar(select(Channel).where(Channel.username == DEMO_CHANNELS[0][1]))
    if existing is not None and not reset:
        return {"skipped": 1}
    if existing is not None:
        clear_demo(session)

    try:
        subjects = load_subjects(settings.subjects_config_path)
    except ConfigError:
        subjects = []
    import_subjects(session, [*subjects, *EXTRA_SUBJECTS])
    subject_codes = [s.code for s in [*subjects, *EXTRA_SUBJECTS]]
    names = {s.code: s for s in [*subjects, *EXTRA_SUBJECTS]}
    # One subject deliberately left without content → shows the "empty subjects" alert.
    content_subjects = subject_codes[:-1]

    layout = StorageLayout(settings)
    layout.ensure()
    now = datetime.now(UTC)

    channels: list[Channel] = []
    for i, (name, username) in enumerate(DEMO_CHANNELS):
        ch = Channel(name=name, username=username, telegram_id=-(1_000_000_000 + i),
                     enabled=i != 2, last_message_id=0,
                     status=ChannelStatus.ACTIVE if i != 2 else ChannelStatus.DISABLED,
                     last_run_at=now - timedelta(minutes=12 + 40 * i))
        session.add(ch)
        channels.append(ch)
    session.flush()

    runs: list[ProcessingRun] = []
    for d in range(30, -1, -1):
        for kind in (RunKind.COLLECT, RunKind.PROCESS):
            start = now - timedelta(days=d, hours=rng.randint(0, 5), minutes=rng.randint(0, 59))
            run = ProcessingRun(kind=kind, trigger=rng.choice(list(RunTrigger)), status="success",
                                started_at=start,
                                finished_at=start + timedelta(seconds=rng.randint(8, 240)),
                                metadata_json={"demo": True})
            session.add(run)
            runs.append(run)
    session.flush()

    statuses = ([FileStatus.CLASSIFIED] * 62 + [FileStatus.UNCLASSIFIED] * 14
                + [FileStatus.DUPLICATE] * 10 + [FileStatus.FAILED] * 4
                + [FileStatus.UNSUPPORTED] * 5 + [FileStatus.DOWNLOADED] * 5)
    exts = ["pdf"] * 7 + ["docx", "pptx", "jpg"]
    created = 0
    canonical: list[CollectedFile] = []
    msg_ids = dict.fromkeys((c.id for c in channels), 100)
    for n in range(files):
        # Weight recent days more heavily so the 30-day chart has a visible trend.
        days_ago = min(29, int(rng.expovariate(1 / 9)))
        when = now - timedelta(days=days_ago, hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
        ch = rng.choice(channels)
        msg_ids[ch.id] += rng.randint(1, 4)
        status = rng.choice(statuses)
        code = rng.choice(content_subjects)
        ctype = rng.choice(CONTENT_TYPES)
        subj = names[code]
        ar_word, en_word = TYPE_WORDS[ctype]
        ext = "doc" if status == FileStatus.UNSUPPORTED else rng.choice(exts)
        number = rng.randint(1, 12)
        filename = rng.choice([
            f"{code} {en_word} {number}.{ext}",
            f"{ar_word} {number} - {subj.name_ar}.{ext}",
            f"{subj.name_en} {en_word} {number}.{ext}",
        ])
        caption = rng.choice([
            f"{ar_word} {subj.name_ar} رقم {number} 📚",
            f"{en_word} {number} — {subj.name_en}",
            f"#{code} {ar_word}",
            None,
        ])
        msg = Message(channel_id=ch.id, telegram_message_id=msg_ids[ch.id], message_date=when,
                      caption=caption, media_type="photo" if ext == "jpg" else "document",
                      file_name=filename, file_size=rng.randint(40_000, 9_000_000),
                      telegram_metadata={"demo": True}, created_at=when, updated_at=when)
        session.add(msg)
        session.flush()
        f = CollectedFile(message_id=msg.id, telegram_document_id=-(5_000_000 + n),
                          original_filename=filename, mime_type="application/pdf"
                          if ext == "pdf" else None, extension=ext, size_bytes=msg.file_size,
                          status=status, created_at=when, updated_at=when)
        session.add(f)
        session.flush()
        run = min(runs, key=lambda r: abs((r.started_at - when).total_seconds()))

        if status == FileStatus.DUPLICATE and canonical:
            f.duplicate_of_file_id = rng.choice(canonical).id
            f.sha256 = None
        elif status == FileStatus.UNSUPPORTED:
            f.error_message = "Unsupported file type '.doc' — legacy Office format"
        elif status == FileStatus.FAILED:
            f.error_message = rng.choice([
                "ExtractionError: PDF is password protected",
                "Download failed: TimeoutError: connection reset",
            ])
        else:
            if status == FileStatus.CLASSIFIED:
                target = layout.processed_path(code, ctype, f.id, filename + ".pdf")
            elif status == FileStatus.UNCLASSIFIED:
                target = layout.unclassified_path(f.id, filename + ".pdf")
            else:
                target = layout.incoming_path(f"demo_{f.id}", filename + ".pdf")
            target.parent.mkdir(parents=True, exist_ok=True)
            body = f"{subj.name_en} - {en_word} {number}\nDemo content generated by TUC."
            f.size_bytes = _demo_pdf(target, f"{code} {en_word} {number}", body)
            f.storage_path = str(target)
            f.sha256 = f"{rng.getrandbits(256):064x}"
            canonical.append(f)
            if status != FileStatus.DOWNLOADED:
                tp = layout.text_path(f.id)
                write_private_text(tp, f"{subj.name_ar}\n{subj.name_en}\n{ar_word} {number}\n"
                                       f"{caption or ''}\nهذا نص تجريبي مستخرج من الملف.")
                f.extracted_text_path = str(tp)

        if status in (FileStatus.CLASSIFIED, FileStatus.UNCLASSIFIED):
            ok = status == FileStatus.CLASSIFIED
            by_ai = ok and rng.random() < 0.3
            session.add(Classification(
                file_id=f.id,
                subject_code=code if ok else None,
                content_type=ctype if ok else None,
                confidence=round(rng.uniform(0.74, 0.97), 2) if by_ai else 0.9 if ok else None,
                evidence=[f"subject code '{code}' in filename", f"type keyword '{en_word}' in caption"]
                if ok else [],
                status=ClassificationStatus.CLASSIFIED if ok else ClassificationStatus.UNCLASSIFIED,
                reason=("Classified by AI" if by_ai else "Strong keyword match for subject and "
                        "content type") if ok else "AI provider is disabled",
                classifier_version=("openai-v1" if by_ai else "rules-v1") if ok else "rules-v1",
                created_at=when, updated_at=when,
            ))
        for stage, st in (("download", ProcessingLogStatus.SUCCESS),
                          ("extract", ProcessingLogStatus.SUCCESS),
                          ("classify", ProcessingLogStatus.SUCCESS)):
            if status in (FileStatus.DUPLICATE, FileStatus.UNSUPPORTED) and stage != "download":
                break
            session.add(ProcessingLog(
                file_id=f.id, run_id=run.id, stage=stage,
                status=ProcessingLogStatus.FAILED if status == FileStatus.FAILED
                and stage == "extract" else st,
                message=f"demo {stage}", created_at=when + timedelta(seconds=len(stage)),
                error_message=f.error_message if status == FileStatus.FAILED
                and stage == "extract" else None,
            ))
            if status == FileStatus.FAILED and stage == "extract":
                break
        key = {"classified": "classified", "unclassified": "unclassified", "duplicate": "duplicate",
               "failed": "failed", "unsupported": "unsupported"}.get(status.value, "new")
        setattr(run, f"{key}_count", getattr(run, f"{key}_count") + 1)
        created += 1

    for ch in channels:
        ch.last_message_id = msg_ids[ch.id]
    session.flush()
    return {"files": created, "channels": len(channels), "runs": len(runs)}
