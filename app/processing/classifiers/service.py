"""Two-stage classification: rules first, OpenAI only for what the rules could not settle."""

from __future__ import annotations

from app.config import AIProvider, Settings
from app.processing.classifiers.base import (
    ClassificationInput,
    ClassificationOutcome,
    unclassified,
)
from app.processing.classifiers.openai_classifier import OpenAIClassifier, ResponsesClient
from app.processing.classifiers.rules import VERSION as RULES_VERSION
from app.processing.classifiers.rules import classify_rules

AI_DISABLED_REASON = "AI provider is disabled"


class Classifier:
    def __init__(self, settings: Settings, openai_client: ResponsesClient | None = None) -> None:
        self.settings = settings
        self._openai_client = openai_client
        self._ai: OpenAIClassifier | None = None

    @property
    def ai(self) -> OpenAIClassifier:
        if self._ai is None:
            self._ai = OpenAIClassifier(self.settings, self._openai_client)
        return self._ai

    def classify(self, data: ClassificationInput) -> ClassificationOutcome:
        if not data.subjects:
            return unclassified("No subjects defined — add subjects before classifying",
                                RULES_VERSION)
        rules = classify_rules(data)
        if (outcome := rules.outcome()) is not None:
            return outcome
        if self.settings.ai_provider != AIProvider.OPENAI:
            return unclassified(
                AI_DISABLED_REASON, RULES_VERSION,
                subject_code=rules.subject.code if rules.subject else None,
                content_type=rules.content_type.content_type if rules.content_type else None,
                evidence=rules.evidence()[:12],
            )
        if not self.settings.openai_configured:
            return unclassified("OpenAI API key is not configured", RULES_VERSION,
                                evidence=rules.evidence()[:12])
        result = self.ai.classify(data)
        if not result.classified and result.reason:
            result.reason = f"{result.reason} ({rules.explain()})"
        return result
