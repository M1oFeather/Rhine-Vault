"""LLM provider abstraction for Phase 1.5."""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from rhine_vault.context import ContextBundle


class LLMProvider(Protocol):
    def answer(self, *, question: str, context_bundle: ContextBundle) -> dict[str, object]:
        """Answer a question using an explicit context bundle."""


@dataclass(frozen=True)
class FakeLLMProvider:
    def answer(self, *, question: str, context_bundle: ContextBundle) -> dict[str, object]:
        citations = [
            item["node_id"]
            for item in (
                list(context_bundle.mandatory_constraints) + list(context_bundle.relevant_context)
            )
        ]
        if citations:
            answer = f"FakeLLM answer for: {question}. Cited nodes: {', '.join(citations)}."
        else:
            answer = f"FakeLLM answer for: {question}. No approved source was available."
        return {
            "provider": "fake",
            "answer": answer,
            "citations": citations,
            "source_refs": context_bundle.supporting_references,
        }


@dataclass(frozen=True)
class OpenAICompatibleProvider:
    endpoint: str
    api_key: str
    model: str

    @classmethod
    def from_env(cls) -> OpenAICompatibleProvider:
        endpoint = os.getenv("RHINE_OPENAI_COMPATIBLE_ENDPOINT")
        api_key = os.getenv("RHINE_OPENAI_COMPATIBLE_API_KEY")
        model = os.getenv("RHINE_OPENAI_COMPATIBLE_MODEL", "gpt-4.1-mini")
        if not endpoint or not api_key:
            raise RuntimeError("OpenAI-compatible provider is not configured")
        return cls(endpoint=endpoint, api_key=api_key, model=model)

    def answer(self, *, question: str, context_bundle: ContextBundle) -> dict[str, object]:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Answer only from the provided Rhine-Vault context and cite node IDs."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"question": question, "context": context_bundle.to_dict()},
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        request = urllib.request.Request(
            self.endpoint.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        return {
            "provider": "openai-compatible",
            "answer": data["choices"][0]["message"]["content"],
            "citations": [],
            "source_refs": context_bundle.supporting_references,
        }
