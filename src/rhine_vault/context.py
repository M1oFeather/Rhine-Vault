"""Context Bundle v0 construction."""

from __future__ import annotations

from dataclasses import asdict, dataclass
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_context_bundle(
    *, store: SQLiteStore, workspace_id: str, question: str, limit: int = 5
) -> ContextBundle:
    hits = store.search(workspace_id=workspace_id, query=question, limit=limit)
    mandatory: list[dict[str, Any]] = []
    relevant: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    warnings: list[str] = []
    for hit in hits:
        item = {
            "node_id": hit.node_id,
            "title": hit.title,
            "authority": hit.authority,
            "content": hit.content,
            "source_refs": hit.source_refs,
        }
        if hit.authority == "canonical" or _looks_like_constraint(hit.content):
            mandatory.append(item)
        else:
            relevant.append(item)
        references.extend(hit.source_refs)
    if not hits:
        warnings.append("No approved MemoryNode matched the question.")
    return ContextBundle(
        workspace_id=workspace_id,
        question=question,
        mandatory_constraints=tuple(mandatory),
        relevant_context=tuple(relevant),
        supporting_references=tuple(references),
        warnings=tuple(warnings),
    )


def _looks_like_constraint(content: str) -> bool:
    lowered = content.lower()
    return any(term in lowered for term in ("must", "cannot", "不得", "必须", "禁止"))
