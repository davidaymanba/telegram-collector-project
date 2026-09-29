"""Deterministic keyword classifier (`rules-v1`).

A match is *strong* when it is unambiguous:
- subject: its code or full name appears anywhere, or ≥2 distinct keywords match,
  or one keyword matches in the metadata (filename/caption/channel) — and no other subject
  is equally strong.
- content type: a type keyword appears in the metadata, or ≥2 hits in the body text.
  "answer model" wins over "exam" because answer sheets are usually titled with both.
Only when both are strong does the file get classified without AI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.database.enums import ClassificationStatus, ContentType
from app.processing.classifiers.base import (
    ClassificationInput,
    ClassificationOutcome,
    SubjectInfo,
)
from app.processing.text import normalize_for_match

VERSION = "rules-v1"
RULES_CONFIDENCE = 0.9

CONTENT_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    ContentType.ANSWER_MODEL: (
        "نموذج اجابة", "نموذج الاجابة", "نماذج اجابة", "الاجابة النموذجية", "اجابة", "الحل", "حلول",
        "حل", "answer", "answers", "answer key", "model answer", "solution", "solutions",
        "solved",
    ),
    ContentType.PREVIOUS_EXAM: (
        "امتحان", "امتحانات", "اختبار", "اختبارات", "نهائي", "ميدترم", "فاينال", "exam", "exams",
        "final", "finals", "midterm", "mid term", "quiz", "past paper", "previous exam",
    ),
    ContentType.ASSIGNMENT: (
        "تكليف", "تكاليف", "واجب", "واجبات", "شيت", "assignment", "assignments", "sheet",
        "homework", "hw", "task", "lab sheet",
    ),
    ContentType.SUMMARY: (
        "ملخص", "ملخصات", "تلخيص", "مراجعه", "مراجعه نهائيه", "summary", "summaries", "revision",
        "review", "cheat sheet", "notes",
    ),
    ContentType.LECTURE: (
        "محاضره", "محاضرات", "شرح", "lecture", "lectures", "lec", "chapter", "slides", "ch",
    ),
}
# Evaluated in this order when breaking ties.
TYPE_PRIORITY = [
    ContentType.ANSWER_MODEL, ContentType.PREVIOUS_EXAM, ContentType.ASSIGNMENT,
    ContentType.SUMMARY, ContentType.LECTURE,
]


def _pattern(term: str) -> re.Pattern[str]:
    norm = normalize_for_match(term)
    # Allow "DB101" to match "db 101" / "db-101"; boundaries work for Arabic and Latin alike.
    body = r"\s*".join(re.escape(part) for part in re.findall(r"[^\W\d_]+|\d+", norm))
    if not body:
        body = re.escape(norm)
    # Arabic definite article "ال" and conjunction "و" prefixes are allowed before Arabic terms.
    prefix = r"(?:و?ال|و|ب|ل)?" if re.match(r"[؀-ۿ]", norm) else ""
    return re.compile(rf"(?<![^\W\d_]){prefix}{body}(?![^\W\d_])", re.UNICODE)


@dataclass(slots=True)
class _Fields:
    meta: str
    text: str
    sources: dict[str, str] = field(default_factory=dict)

    @classmethod
    def build(cls, data: ClassificationInput) -> _Fields:
        sources = {
            "filename": normalize_for_match(data.filename),
            "caption": normalize_for_match(data.caption),
            "channel": normalize_for_match(data.channel_name),
        }
        return cls(meta=" | ".join(sources.values()), text=normalize_for_match(data.text),
                   sources=sources)

    def where(self, pattern: re.Pattern[str]) -> list[str]:
        found = [name for name, value in self.sources.items() if pattern.search(value)]
        if pattern.search(self.text):
            found.append("text")
        return found

    def text_hits(self, pattern: re.Pattern[str]) -> int:
        return len(pattern.findall(self.text))


@dataclass(slots=True)
class SubjectMatch:
    code: str
    score: float
    strong: bool
    evidence: list[str]


@dataclass(slots=True)
class TypeMatch:
    content_type: str
    score: float
    strong: bool
    evidence: list[str]
    in_meta: bool = False


def match_subjects(fields: _Fields, subjects: list[SubjectInfo]) -> list[SubjectMatch]:
    results: list[SubjectMatch] = []
    for subject in subjects:
        evidence: list[str] = []
        score = 0.0
        strong = False
        for label, term in (("code", subject.code), ("name_ar", subject.name_ar),
                            ("name_en", subject.name_en)):
            if not term or len(normalize_for_match(term)) < 2:
                continue
            places = fields.where(_pattern(term))
            if places:
                evidence.append(f"subject {label} '{term}' in {', '.join(places)}")
                score += 3 if label == "code" else 2.5
                strong = True
        meta_kw = 0
        kw_count = 0
        for kw in subject.keywords:
            if len(normalize_for_match(kw)) < 2:
                continue
            places = fields.where(_pattern(kw))
            if places:
                kw_count += 1
                meta_kw += any(p != "text" for p in places)
                evidence.append(f"keyword '{kw}' in {', '.join(places)}")
                score += 1.5 if any(p != "text" for p in places) else 1
        if kw_count >= 2 or meta_kw >= 1:
            strong = True
        if evidence:
            results.append(SubjectMatch(subject.code, score, strong, evidence))
    return sorted(results, key=lambda m: m.score, reverse=True)


def match_content_types(fields: _Fields) -> list[TypeMatch]:
    results: list[TypeMatch] = []
    for ctype in TYPE_PRIORITY:
        evidence: list[str] = []
        score = 0.0
        strong = False
        in_meta = False
        for kw in CONTENT_TYPE_KEYWORDS[ctype]:
            pattern = _pattern(kw)
            places = fields.where(pattern)
            # Channel names ("أرشيف الامتحانات") describe the channel, not this file.
            meta_places = [p for p in places if p in ("filename", "caption")]
            hits = fields.text_hits(pattern)
            if "channel" in places and not meta_places:
                evidence.append(f"type keyword '{kw}' in channel name")
                score += 0.5
            if meta_places:
                evidence.append(f"type keyword '{kw}' in {', '.join(meta_places)}")
                score += 3
                strong = in_meta = True
            if hits:
                evidence.append(f"type keyword '{kw}' ×{hits} in text")
                score += min(hits, 5) * 0.5
                if hits >= 2:
                    strong = True
        if evidence:
            results.append(TypeMatch(str(ctype), score, strong, evidence, in_meta))
    return results


def _pick_type(matches: list[TypeMatch]) -> TypeMatch | None:
    strong = [m for m in matches if m.strong]
    if not strong:
        return None
    # What the uploader wrote (filename/caption) outweighs words found in the body text.
    pool = [m for m in strong if m.in_meta] or strong
    # Answer model beats exam when both appear together ("نموذج إجابة امتحان ...").
    by_type = {m.content_type: m for m in pool}
    if ContentType.ANSWER_MODEL in by_type and any(m.in_meta for m in pool):
        return by_type[ContentType.ANSWER_MODEL]
    best = max(pool, key=lambda m: m.score)
    ties = [m for m in pool if m.score == best.score]
    if len(ties) > 1:
        return min(ties, key=lambda m: TYPE_PRIORITY.index(ContentType(m.content_type)))
    return best


@dataclass(slots=True)
class RuleResult:
    subject: SubjectMatch | None
    content_type: TypeMatch | None
    subject_candidates: list[SubjectMatch]
    type_candidates: list[TypeMatch]
    ambiguous_subject: bool

    @property
    def decided(self) -> bool:
        return bool(self.subject and self.subject.strong and self.content_type
                    and not self.ambiguous_subject)

    def evidence(self) -> list[str]:
        ev: list[str] = []
        if self.subject:
            ev.extend(self.subject.evidence)
        if self.content_type:
            ev.extend(self.content_type.evidence)
        return ev

    def outcome(self) -> ClassificationOutcome | None:
        if not self.decided:
            return None
        assert self.subject and self.content_type
        return ClassificationOutcome(
            status=ClassificationStatus.CLASSIFIED,
            subject_code=self.subject.code,
            content_type=self.content_type.content_type,
            confidence=RULES_CONFIDENCE,
            evidence=self.evidence()[:12],
            reason="Strong keyword match for subject and content type",
            classifier_version=VERSION,
        )

    def explain(self) -> str:
        if self.ambiguous_subject:
            codes = ", ".join(m.code for m in self.subject_candidates if m.strong)
            return f"Rules: ambiguous subject ({codes})"
        missing = []
        if not (self.subject and self.subject.strong):
            missing.append("subject")
        if not self.content_type:
            missing.append("content type")
        return "Rules: no strong match for " + " and ".join(missing) if missing else "Rules: decided"


def classify_rules(data: ClassificationInput) -> RuleResult:
    fields = _Fields.build(data)
    subjects = match_subjects(fields, data.subjects)
    types = match_content_types(fields)
    strong_subjects = [m for m in subjects if m.strong]
    ambiguous = False
    subject = strong_subjects[0] if strong_subjects else (subjects[0] if subjects else None)
    if len(strong_subjects) > 1 and strong_subjects[0].score - strong_subjects[1].score < 1.5:
        ambiguous = True
    return RuleResult(
        subject=subject,
        content_type=_pick_type(types),
        subject_candidates=subjects,
        type_candidates=types,
        ambiguous_subject=ambiguous,
    )
