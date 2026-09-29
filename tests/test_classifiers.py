from __future__ import annotations

import pytest

from app.config import AIProvider, Settings
from app.database.enums import ClassificationStatus
from app.processing.classifiers.base import ClassificationInput, SubjectInfo
from app.processing.classifiers.openai_classifier import (
    RESPONSE_SCHEMA,
    AIAnswer,
    OpenAIClassifier,
    build_payload,
    parse_answer,
    validate_answer,
)
from app.processing.classifiers.rules import classify_rules
from app.processing.classifiers.service import AI_DISABLED_REASON, Classifier
from tests.fakes import FakeOpenAI

SUBJECTS = [
    SubjectInfo("DB101", "قواعد البيانات", "Database", ["database", "sql", "قواعد بيانات", "ERD"]),
    SubjectInfo("CS101", "مقدمة علوم الحاسب", "Introduction to Computer Science",
                ["intro to cs", "مقدمة حاسب", "algorithms"]),
]


def inp(filename: str = "", caption: str = "", channel: str = "", text: str = "",
        subjects: list[SubjectInfo] | None = None) -> ClassificationInput:
    return ClassificationInput(filename, caption, channel, text,
                               SUBJECTS if subjects is None else subjects)


# ------------------------------------------------------------------ rules
@pytest.mark.parametrize("data, subject, ctype", [
    (inp("DB101 Lecture 3.pdf"), "DB101", "lecture"),
    (inp("db-101_lec2.pdf"), "DB101", "lecture"),
    (inp("محاضرة 1.pdf", caption="قواعد البيانات"), "DB101", "lecture"),
    (inp("الإمتحان النهائي - قواعد البيانات.pdf"), "DB101", "previous_exam"),
    (inp("Final exam.pdf", caption="Introduction to Computer Science 2025"), "CS101",
     "previous_exam"),
    (inp("نموذج إجابة امتحان قواعد البيانات.pdf"), "DB101", "answer_model"),
    (inp("CS101 midterm solution.pdf"), "CS101", "answer_model"),
    (inp("sheet 3.pdf", caption="#CS101"), "CS101", "assignment"),
    (inp("ملخص قواعد البيانات.pdf"), "DB101", "summary"),
    (inp("summary.pdf", caption="SQL and ERD notes"), "DB101", "summary"),
])
def test_rules_decide(data: ClassificationInput, subject: str, ctype: str) -> None:
    outcome = classify_rules(data).outcome()
    assert outcome is not None, classify_rules(data).explain()
    assert (outcome.subject_code, outcome.content_type) == (subject, ctype)
    assert outcome.classifier_version == "rules-v1"
    assert outcome.evidence


@pytest.mark.parametrize("data", [
    inp("scan_0001.pdf"),                                    # nothing at all
    inp("lecture 4.pdf"),                                    # type but no subject
    inp("DB101.pdf"),                                        # subject but no type
    inp("lecture.pdf", caption="DB101 + CS101 combined"),     # ambiguous subject
    inp("notes.pdf", text="one mention of sql here"),         # weak keyword in text only
])
def test_rules_undecided(data: ClassificationInput) -> None:
    result = classify_rules(data)
    assert result.outcome() is None
    assert result.explain().startswith("Rules:")


def test_rules_body_words_dont_override_metadata_type() -> None:
    body = "حل المعادلة ... حل التمرين ... الحل النهائي"
    outcome = classify_rules(inp("DB101 lecture 2.pdf", text=body)).outcome()
    assert outcome is not None and outcome.content_type == "lecture"


def test_rules_type_from_repeated_text() -> None:
    text = "Database course. Assignment 1: ... Assignment deadline ... submit the assignment"
    outcome = classify_rules(inp("DB101.pdf", text=text)).outcome()
    assert outcome is not None and outcome.content_type == "assignment"


def test_rules_word_boundaries() -> None:
    # "sql" inside "mysqladmin" or "ERD" inside "nerdy" must not match.
    result = classify_rules(inp("mysqladmin nerdy lecture.pdf"))
    assert result.subject is None


# ------------------------------------------------------------------ openai validation
def test_schema_is_strict() -> None:
    assert RESPONSE_SCHEMA["additionalProperties"] is False
    assert set(RESPONSE_SCHEMA["required"]) == {"subject_code", "content_type", "confidence",
                                                "evidence"}
    assert RESPONSE_SCHEMA["properties"]["subject_code"]["type"] == ["string", "null"]


def _validate(**kw: object):
    answer = AIAnswer(**{"subject_code": "DB101", "content_type": "lecture", "confidence": 0.9,
                         "evidence": ["filename mentions SQL"], **kw})  # type: ignore[arg-type]
    return validate_answer(answer, allowed_subjects={"DB101", "CS101"}, min_confidence=0.7,
                           min_evidence=1)


def test_validation_accepts_good_answer() -> None:
    out = _validate()
    assert out.status == ClassificationStatus.CLASSIFIED and out.classifier_version == "openai-v1"


@pytest.mark.parametrize("kw, reason", [
    ({"subject_code": None}, "could not determine the subject"),
    ({"subject_code": "PHY999"}, "unknown subject"),
    ({"content_type": None}, "content type"),
    ({"content_type": "video"}, "invalid content type"),
    ({"confidence": None}, "no valid confidence"),
    ({"confidence": 1.7}, "no valid confidence"),
    ({"confidence": 0.5}, "below threshold"),
    ({"evidence": []}, "evidence"),
])
def test_validation_rejects(kw: dict[str, object], reason: str) -> None:
    out = _validate(**kw)
    assert out.status == ClassificationStatus.UNCLASSIFIED
    assert reason in (out.reason or "")
    if kw.get("subject_code") == "PHY999":
        assert out.subject_code is None  # invented subject never stored


def test_parse_answer() -> None:
    a = parse_answer('{"subject_code": "DB101", "content_type": "lecture", "confidence": 1, '
                     '"evidence": [" x ", ""]}')
    assert a.confidence == 1.0 and a.evidence == ["x"]
    with pytest.raises(ValueError):
        parse_answer("[]")
    with pytest.raises(ValueError):
        parse_answer("not json")


def test_payload_is_truncated_and_lists_allowed_values() -> None:
    payload = build_payload(inp("f.pdf", text="x" * 10_000), 100)
    assert len(payload["text"]) == 100
    assert [s["code"] for s in payload["allowed_subjects"]] == ["DB101", "CS101"]
    assert "answer_model" in payload["allowed_content_types"]


def test_openai_request_uses_structured_outputs(settings: Settings) -> None:
    fake = FakeOpenAI({"subject_code": "CS101", "content_type": "summary", "confidence": 0.88,
                       "evidence": ["caption says algorithms summary"]})
    out = OpenAIClassifier(settings, fake).classify(inp("x.pdf"))
    assert out.subject_code == "CS101" and out.classified
    req = fake.responses.requests[0]
    fmt = req["text"]["format"]
    assert fmt["type"] == "json_schema" and fmt["strict"] is True
    assert fmt["schema"] is RESPONSE_SCHEMA
    assert req["model"] == settings.openai_model


def test_openai_failure_is_unclassified(settings: Settings) -> None:
    out = OpenAIClassifier(settings, FakeOpenAI(TimeoutError("slow"))).classify(inp("x.pdf"))
    assert not out.classified and "AI request failed" in (out.reason or "")


# ------------------------------------------------------------------ service
def test_service_rules_first_no_ai_call(settings: Settings) -> None:
    settings.ai_provider = AIProvider.OPENAI
    fake = FakeOpenAI(RuntimeError("must not be called"))
    out = Classifier(settings, fake).classify(inp("DB101 Lecture 1.pdf"))
    assert out.classifier_version == "rules-v1" and out.classified
    assert fake.responses.requests == []


def test_service_ai_disabled(settings: Settings) -> None:
    out = Classifier(settings).classify(inp("scan.pdf"))
    assert out.status == ClassificationStatus.UNCLASSIFIED
    assert out.reason == AI_DISABLED_REASON


def test_service_falls_back_to_ai(settings: Settings) -> None:
    from pydantic import SecretStr

    settings.ai_provider = AIProvider.OPENAI
    settings.openai_api_key = SecretStr("sk-test")
    fake = FakeOpenAI({"subject_code": "DB101", "content_type": "lecture", "confidence": 0.8,
                       "evidence": ["ERD diagrams on page 1"]})
    out = Classifier(settings, fake).classify(inp("scan.pdf", text="ERD"))
    assert out.classified and out.classifier_version == "openai-v1"
    assert len(fake.responses.requests) == 1


def test_service_ai_without_key(settings: Settings) -> None:
    settings.ai_provider = AIProvider.OPENAI
    out = Classifier(settings).classify(inp("scan.pdf"))
    assert "not configured" in (out.reason or "")


def test_service_without_subjects(settings: Settings) -> None:
    out = Classifier(settings).classify(inp("DB101 lecture.pdf", subjects=[]))
    assert not out.classified and "No subjects" in (out.reason or "")
