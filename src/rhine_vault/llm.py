"""LLM provider abstraction for Phase 1.5 and Phase 2 UI workflows."""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse, urlunparse

from rhine_vault.context import ContextBundle

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"


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
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int = 30

    @classmethod
    def from_env(cls) -> OpenAICompatibleProvider:
        base_url, api_key, model = _environment_openai_settings()
        if not api_key:
            raise RuntimeError("OpenAI-compatible provider is not configured")
        return cls(base_url=base_url, api_key=api_key, model=model)

    @classmethod
    def from_values(
        cls,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> OpenAICompatibleProvider:
        env_base_url, env_api_key, env_model = _environment_openai_settings()
        configured_base_url = _clean_optional(base_url) or env_base_url
        configured_api_key = _clean_optional(api_key) or env_api_key
        configured_model = _clean_optional(model) or env_model
        if not configured_api_key:
            raise RuntimeError("OpenAI-compatible provider is not configured")
        return cls(
            base_url=configured_base_url,
            api_key=configured_api_key,
            model=configured_model,
        )

    @classmethod
    def environment_status(cls) -> dict[str, object]:
        base_url, api_key, model = _environment_openai_settings()
        return {
            "provider": "openai-compatible",
            "configured": bool(api_key),
            "base_url": base_url,
            "model": model,
            "api_key_configured": bool(api_key),
        }

    @property
    def chat_completions_url(self) -> str:
        return _chat_completions_url(self.base_url)

    def answer(
        self,
        *,
        question: str,
        context_bundle: ContextBundle,
        thinking_enabled: bool = False,
        reasoning_effort: str | None = None,
    ) -> dict[str, object]:
        payload = _chat_completion_payload(
            model=self.model,
            question=question,
            context_bundle=context_bundle,
        )
        _apply_reasoning_options(
            payload,
            thinking_enabled=thinking_enabled,
            reasoning_effort=reasoning_effort,
        )
        data = self._post_chat_completions(payload)
        return {
            "provider": "openai-compatible",
            "model": self.model,
            "base_url": _redact_url(self.base_url),
            "answer": _extract_chat_completion_content(data),
            "reasoning": _extract_chat_completion_reasoning(data),
            "citations": _context_node_ids(context_bundle),
            "source_refs": context_bundle.supporting_references,
        }

    def chat(
        self,
        *,
        messages: list[dict[str, str]],
        thinking_enabled: bool = False,
        reasoning_effort: str | None = None,
    ) -> dict[str, object]:
        """Send a normal multi-turn chat request without Rhine-Vault retrieval context."""

        payload = {
            "model": self.model,
            "messages": [_chat_message(message) for message in messages],
            "stream": False,
        }
        _apply_reasoning_options(
            payload,
            thinking_enabled=thinking_enabled,
            reasoning_effort=reasoning_effort,
        )
        data = self._post_chat_completions(payload)
        return {
            "provider": "openai-compatible",
            "mode": "chat",
            "model": self.model,
            "base_url": _redact_url(self.base_url),
            "answer": _extract_chat_completion_content(data),
            "reasoning": _extract_chat_completion_reasoning(data),
        }

    def ping(
        self,
        *,
        message: str = "你好",
        thinking_enabled: bool = False,
        reasoning_effort: str | None = None,
    ) -> dict[str, object]:
        """Send a minimal chat-completions request without Rhine-Vault retrieval context."""

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Reply normally and briefly. This is a provider connectivity test.",
                },
                {"role": "user", "content": message},
            ],
            "stream": False,
        }
        _apply_reasoning_options(
            payload,
            thinking_enabled=thinking_enabled,
            reasoning_effort=reasoning_effort,
        )
        data = self._post_chat_completions(payload)
        return {
            "provider": "openai-compatible",
            "mode": "ping",
            "model": self.model,
            "base_url": _redact_url(self.base_url),
            "request_message": message,
            "answer": _extract_chat_completion_content(data),
            "reasoning": _extract_chat_completion_reasoning(data),
        }

    def _post_chat_completions(self, payload: dict[str, object]) -> dict[str, object]:
        request = urllib.request.Request(
            self.chat_completions_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        if not isinstance(data, dict):
            raise RuntimeError("OpenAI-compatible response is invalid")
        return data


def _environment_openai_settings() -> tuple[str, str, str]:
    base_url = (
        os.getenv("RHINE_OPENAI_BASE_URL")
        or os.getenv("RHINE_OPENAI_COMPATIBLE_BASE_URL")
        or os.getenv("RHINE_OPENAI_COMPATIBLE_ENDPOINT")
        or os.getenv("OPENAI_BASE_URL")
        or DEFAULT_OPENAI_BASE_URL
    )
    api_key = (
        os.getenv("RHINE_OPENAI_API_KEY")
        or os.getenv("RHINE_OPENAI_COMPATIBLE_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ""
    )
    model = (
        os.getenv("RHINE_OPENAI_MODEL")
        or os.getenv("RHINE_OPENAI_COMPATIBLE_MODEL")
        or DEFAULT_OPENAI_MODEL
    )
    return base_url.strip(), api_key.strip(), model.strip()


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _chat_completions_url(base_url: str) -> str:
    cleaned = base_url.strip().rstrip("/")
    if not cleaned:
        cleaned = DEFAULT_OPENAI_BASE_URL
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError("OpenAI-compatible base URL must be an http(s) URL")
    if parsed.username or parsed.password:
        raise RuntimeError("OpenAI-compatible base URL must not include credentials")
    if cleaned.endswith("/chat/completions"):
        return cleaned
    if cleaned.endswith("/v1"):
        return f"{cleaned}/chat/completions"
    if not parsed.path or parsed.path == "/":
        return f"{cleaned}/v1/chat/completions"
    return f"{cleaned}/chat/completions"


def _chat_completion_payload(
    *,
    model: str,
    question: str,
    context_bundle: ContextBundle,
) -> dict[str, object]:
    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are answering inside Rhine-Vault. Answer only from the provided "
                    "approved context bundle. Cite MemoryNode node_id values when relevant. "
                    "If the bundle has no supporting context, say that no approved source "
                    "is available."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"question": question, "context_bundle": context_bundle.to_dict()},
                    ensure_ascii=False,
                ),
            },
        ],
        "stream": False,
    }


def _chat_message(message: dict[str, str]) -> dict[str, str]:
    role = message.get("role", "").strip()
    content = message.get("content", "").strip()
    if role not in {"system", "user", "assistant"}:
        raise RuntimeError("OpenAI-compatible chat message role is invalid")
    if not content:
        raise RuntimeError("OpenAI-compatible chat message content cannot be empty")
    return {"role": role, "content": content}


def _apply_reasoning_options(
    payload: dict[str, object],
    *,
    thinking_enabled: bool,
    reasoning_effort: str | None,
) -> None:
    if thinking_enabled:
        payload["thinking"] = {"type": "enabled"}
    cleaned_effort = _clean_optional(reasoning_effort)
    if cleaned_effort:
        payload["reasoning_effort"] = cleaned_effort


def _extract_chat_completion_content(data: dict[str, object]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("OpenAI-compatible response did not include choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise RuntimeError("OpenAI-compatible response choice is invalid")
    message = first.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("OpenAI-compatible response did not include a message")
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                text_parts.append(item["text"])
        if text_parts:
            return "".join(text_parts)
    raise RuntimeError("OpenAI-compatible response message did not include text content")


def _extract_chat_completion_reasoning(data: dict[str, object]) -> str | None:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if not isinstance(message, dict):
        return None
    for key in ("reasoning_content", "reasoning"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _context_node_ids(context_bundle: ContextBundle) -> list[str]:
    items = list(context_bundle.mandatory_constraints) + list(context_bundle.relevant_context)
    return [str(item["node_id"]) for item in items if "node_id" in item]


def _redact_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if not parsed.username and not parsed.password:
        return base_url
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return urlunparse(
        (
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )
