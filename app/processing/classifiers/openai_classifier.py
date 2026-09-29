"""OpenAI fallback classifier using the Responses API with a strict JSON schema."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from app.config import Settings
from app.database.enums import CONTENT_TYPES, ClassificationStatus
from app.processing.classifiers.base import (
    ClassificationInput,
    ClassificationOutcome,
    unclassified,
)

VERSION = "openai-v1"

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "subject_code": {"type": ["string", "null"]},
        "content_type": {"type": ["string", "null"]},
        "confidence": {"type": ["number", "null"]},
        "evidence": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["subject_code", "content_type", "confidence", "evidence"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You classify university course files collected from Telegram.
Return the subject_code and content_type ONLY if the provided data clearly supports them.
Rules:
- subject_code MUST be one of allowed_subjects[].code, or null.
- content_type MUST be one of allowed_content_types, or null.
- Never invent subjects or types. When unsure, return null.
- evidence: short verbatim quotes or facts from the input that justify the answer.
- confidence: 0..1, your calibrated probability that BOTH fields are correct."""


class ResponsesClient(Protocol):
    """The slice of `openai.OpenAI` we use; lets tests inject a fake."""

    @property
    def responses(self) -> Any: ...


@dataclass(slots=True)
class AIAnswer:
    subject_code: str | None
    content_type: str | None
    confidence: float | None
    evidence: list[str]


def build_payload(data: ClassificationInput, max_chars: int) -> dict[str, Any]:
    return {
        "filename": data.filename,
        "caption": data.caption,
        "channel_name": data.channel_name,
        "text": data.text[:max_chars],
        "allowed_subjects": [
            {"code": s.code, "name_ar": s.name_ar, "name_en": s.name_en, "keywords": s.keywords}
            for s in data.subjects
        ],
        "allowed_content_types": list(CONTENT_TYPES),
    }


def parse_answer(raw: str) -> AIAnswer:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Response is not a JSON object")
    evidence = data.get("evidence")
    if not isinstance(evidence, list):
        raise ValueError("evidence must be an array")
    conf = data.get("confidence")
    return AIAnswer(
        subject_code=data.get("subject_code") or None,
        content_type=data.get("content_type") or None,
        confidence=float(conf) if isinstance(conf, int | float) else None,
        evidence=[str(e).strip() for e in evidence if str(e).strip()],
    )


def validate_answer(
    answer: AIAnswer,
    *,
    allowed_subjects: set[str],
    min_confidence: float,
    min_evidence: int,
    version: str = VERSION,
) -> ClassificationOutcome:
    """Strict gate: anything not provably valid ends up `unclassified` with a reason."""
    common: dict[str, Any] = {
        "subject_code": answer.subject_code, "content_type": answer.content_type,
        "confidence": answer.confidence, "evidence": answer.evidence,
    }
    if not answer.subject_code:
        return unclassified("AI could not determine the subject", version, **common)
    if answer.subject_code not in allowed_subjects:
        return unclassified(f"AI returned unknown subject '{answer.subject_code}'", version,
                            **{**common, "subject_code": None})
    if not answer.content_type:
        return unclassified("AI could not determine the content type", version, **common)
    if answer.content_type not in CONTENT_TYPES:
        return unclassified(f"AI returned invalid content type '{answer.content_type}'", version,
                            **{**common, "content_type": None})
    if answer.confidence is None or not 0 <= answer.confidence <= 1:
        return unclassified("AI returned no valid confidence", version, **common)
    if answer.confidence < min_confidence:
        return unclassified(
            f"AI confidence {answer.confidence:.2f} below threshold {min_confidence:.2f}",
            version, **common,
        )
    if len(answer.evidence) < min_evidence:
        return unclassified(
            f"AI gave {len(answer.evidence)} evidence item(s); {min_evidence} required",
            version, **common,
        )
    return ClassificationOutcome(
        status=ClassificationStatus.CLASSIFIED,
        subject_code=answer.subject_code,
        content_type=answer.content_type,
        confidence=answer.confidence,
        evidence=answer.evidence[:12],
        reason="Classified by AI",
        classifier_version=version,
    )


class OpenAIClassifier:
    def __init__(self, settings: Settings, client: ResponsesClient | None = None) -> None:
        self.settings = settings
        if client is None:
            from openai import OpenAI

            key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
            client = OpenAI(api_key=key, timeout=60, max_retries=2)
        self.client = client

    def ask(self, data: ClassificationInput) -> AIAnswer:
        payload = build_payload(data, self.settings.max_classification_chars)
        response = self.client.responses.create(
            model=self.settings.openai_model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            text={"format": {"type": "json_schema", "name": "file_classification",
                             "schema": RESPONSE_SCHEMA, "strict": True}},
        )
        return parse_answer(response.output_text)

    def classify(self, data: ClassificationInput) -> ClassificationOutcome:
        try:
            answer = self.ask(data)
        except Exception as exc:
            return unclassified(f"AI request failed: {type(exc).__name__}: {str(exc)[:300]}",
                                VERSION)
        return validate_answer(
            answer,
            allowed_subjects={s.code for s in data.subjects},
            min_confidence=self.settings.classification_min_confidence,
            min_evidence=self.settings.classification_min_evidence_items,
        )

    def ping(self) -> str:
        """Tiny request used by the dashboard's 'test connection' button."""
        response = self.client.responses.create(
            model=self.settings.openai_model, input="Reply with the single word: ok",
            max_output_tokens=16,
        )
        return str(response.output_text).strip()
