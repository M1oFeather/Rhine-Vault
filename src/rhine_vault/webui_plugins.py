"""Helpers for WebUI plugin-style workflows built on approved knowledge."""

from __future__ import annotations

from typing import Any

from rhine_vault.context import ContextBundle


def build_bot_adapter_payload(context_bundle: ContextBundle) -> dict[str, Any]:
    """Return a compact payload intended for external bot framework adapters."""

    citations = _context_node_ids(context_bundle)
    return {
        "integration": "bot-adapter",
        "contract_version": "0.1",
        "workspace_id": context_bundle.workspace_id,
        "query": context_bundle.question,
        "context_bundle": context_bundle.to_dict(),
        "citations": citations,
        "source_refs": list(context_bundle.supporting_references),
        "adapter_hints": {
            "runtime_owner": "external-bot-framework",
            "recommended_use": "send context_bundle to the bot-side model or command handler",
            "approval_policy": "only approved Rhine-Vault knowledge is included",
        },
    }


def render_knowledge_document(
    context_bundle: ContextBundle,
    *,
    title: str | None = None,
    audience: str = "developer",
) -> dict[str, Any]:
    """Render a human-checkable Markdown projection from approved context."""

    document_title = _clean_title(title) or f"Knowledge Brief: {context_bundle.question}"
    citations = _context_node_ids(context_bundle)
    lines: list[str] = [
        f"# {document_title}",
        "",
        f"- Workspace: `{context_bundle.workspace_id}`",
        f"- Audience: `{audience.strip() or 'developer'}`",
        f"- Source query: `{context_bundle.question}`",
        f"- Retrieval profile: `{context_bundle.retrieval_profile.get('profile_id', 'default')}`",
        "",
        "## Summary",
        "",
        (
            "This document is generated from approved Rhine-Vault knowledge. Treat it as a "
            "review surface: if a section is wrong, fix the underlying node and regenerate "
            "the document."
        ),
        "",
    ]

    if context_bundle.mandatory_constraints:
        lines.extend(["## Mandatory Constraints", ""])
        lines.extend(_render_nodes(context_bundle.mandatory_constraints))

    if context_bundle.relevant_context:
        lines.extend(["## Relevant Knowledge", ""])
        lines.extend(_render_nodes(context_bundle.relevant_context))

    if context_bundle.warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in context_bundle.warnings)
        lines.append("")

    lines.extend(["## Citations", ""])
    if citations:
        lines.extend(f"- `{node_id}`" for node_id in citations)
    else:
        lines.append("- No approved source was available for this query.")
    lines.append("")

    return {
        "kind": "knowledge-document",
        "format": "markdown",
        "title": document_title,
        "audience": audience.strip() or "developer",
        "markdown": "\n".join(lines),
        "citations": citations,
        "source_refs": list(context_bundle.supporting_references),
        "context_bundle": context_bundle.to_dict(),
    }


def _render_nodes(nodes: tuple[dict[str, Any], ...]) -> list[str]:
    lines: list[str] = []
    for node in nodes:
        node_id = str(node.get("node_id", "unknown"))
        title = str(node.get("title", node_id))
        authority = str(node.get("authority", "approved"))
        content = str(node.get("content", "")).strip()
        lines.extend(
            [
                f"### {title}",
                "",
                f"- Node: `{node_id}`",
                f"- Authority: `{authority}`",
                "",
                content or "_No content._",
                "",
            ]
        )
    return lines


def _context_node_ids(context_bundle: ContextBundle) -> list[str]:
    nodes = list(context_bundle.mandatory_constraints) + list(context_bundle.relevant_context)
    return [str(node["node_id"]) for node in nodes if "node_id" in node]


def _clean_title(title: str | None) -> str | None:
    if title is None:
        return None
    cleaned = " ".join(title.strip().split())
    return cleaned or None
