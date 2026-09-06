"""Optional OpenAI Responses API adapter for structured grounded narratives."""

from __future__ import annotations

import json
from typing import Any

from src.agent.explainers import GeneratedNarrative


class LLMUnavailableError(RuntimeError):
    pass


class OpenAIExplanationProvider:
    def __init__(self, model: str, language: str = "ar", client: Any | None = None) -> None:
        if not model or not model.strip():
            raise ValueError("An explicit OpenAI model is required.")
        if language not in {"ar", "en"}:
            raise ValueError("language must be 'ar' or 'en'.")
        self.model = model
        self.language = language
        self._client = client

    def generate(self, payload: dict[str, Any]) -> tuple[GeneratedNarrative, ...]:
        try:
            from openai import OpenAI
            from pydantic import BaseModel, ConfigDict
        except ImportError as exc:
            raise LLMUnavailableError("Install requirements-llm.txt to enable OpenAI explanations.") from exc

        class NarrativeItem(BaseModel):
            model_config = ConfigDict(extra="forbid")
            rule_id: str
            issue: str
            why_flagged: str

        class NarrativeBatch(BaseModel):
            model_config = ConfigDict(extra="forbid")
            issues: list[NarrativeItem]

        client = self._client or OpenAI()
        language_instruction = "Write concise Modern Standard Arabic." if self.language == "ar" else "Write concise English."
        response = client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You explain deterministic invoice-validator findings. Use only the supplied verified evidence. "
                        "Do not add rules, citations, URLs, corrections, legal advice, approval, certification, or full-compliance claims. "
                        + language_instruction
                    ),
                },
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            text_format=NarrativeBatch,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise LLMUnavailableError("OpenAI response did not contain parsed structured output.")
        return tuple(GeneratedNarrative(item.rule_id, item.issue, item.why_flagged) for item in parsed.issues)
