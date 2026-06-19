"""Context Bundle v0 construction."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from rhine_vault.storage.sqlite import SQLiteStore


@dataclass(frozen=True)
class ContextBundle:
    workspace_id: str
    question: str
    mandatory_constraints: tuple[dict[str, Any], ...]
    relevant_context: tuple[dict[str, Any], ...]
    supporting_references: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]
    retrieval_profile: dict[str, Any] = field(default_factory=dict)
    explain_trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_context_bundle(
    *, store: SQLiteStore, workspace_id: str, question: str, limit: int = 5
) -> ContextBundle:
    from rhine_vault.retrieval import RetrievalOverrides, retrieve_context_bundle

    return retrieve_context_bundle(
        store=store,
        workspace_id=workspace_id,
        query=question,
        overrides=RetrievalOverrides(result_limit=limit),
    )


def _looks_like_constraint(content: str) -> bool:
    lowered = content.lower()
    return any(term in lowered for term in ("must", "cannot", "不得", "必须", "禁止"))
