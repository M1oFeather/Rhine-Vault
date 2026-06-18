"""Deterministic proposal extraction rules for Phase 1.5."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from rhine_vault.domain.ids import validate_node_id
from rhine_vault.markdown.blocks import parse_markdown_blocks


@dataclass(frozen=True)
class ProposedNodeDraft:
    temporary_id: str
    title: str
    node_type: str
    content: str
    tags: tuple[str, ...]
    authority: str
    source_refs: tuple[dict[str, object], ...]
    rationale: str
    confidence: float


@dataclass(frozen=True)
class ProposedRelationDraft:
    source_temporary_id: str
    target_reference: str
    relation_type: str
    confidence: float
    rationale: str


def extract_conversation_nodes(
    *, session_id: str, messages: list[dict[str, str]]
) -> tuple[tuple[ProposedNodeDraft, ...], tuple[ProposedRelationDraft, ...]]:
    body = "\n".join(message["content"] for message in messages)
    source_ref: dict[str, object] = {
        "type": "conversation",
        "session_id": session_id,
        "message_ids": [message["message_id"] for message in messages],
        "message_range": f"{messages[0]['message_id']}..{messages[-1]['message_id']}",
    }
    drafts: list[ProposedNodeDraft] = []

    if re.search(r"Agent|staging|批准|发布", body, flags=re.IGNORECASE):
        drafts.append(
            ProposedNodeDraft(
                temporary_id="proposal.agent-staging-boundary",
                title="Agent staging boundary",
                node_type="Constraint",
                content=(
                    "Agent can submit or modify staging entries, but cannot directly "
                    "approve or publish formal knowledge."
                ),
                tags=("agent", "staging", "approval"),
                authority="canonical",
                source_refs=(source_ref,),
                rationale="Conversation explicitly states Agent approval and publishing limits.",
                confidence=0.92,
            )
        )

    if re.search(r"Obsidian|ExternalChange|外部", body, flags=re.IGNORECASE):
        drafts.append(
            ProposedNodeDraft(
                temporary_id="proposal.external-change-review",
                title="External changes require review",
                node_type="Constraint",
                content=(
                    "Obsidian or other external file changes must enter ExternalChange "
                    "review before affecting formal knowledge or indexes."
                ),
                tags=("external-change", "obsidian", "review"),
                authority="canonical",
                source_refs=(source_ref,),
                rationale="Conversation links Obsidian changes to ExternalChange review.",
                confidence=0.9,
            )
        )

    if not drafts:
        drafts.append(
            ProposedNodeDraft(
                temporary_id="proposal.conversation-summary",
                title="Conversation summary",
                node_type="Note",
                content=body.strip(),
                tags=("conversation",),
                authority="reference",
                source_refs=(source_ref,),
                rationale="Fallback deterministic summary for conversation capture.",
                confidence=0.5,
            )
        )

    relations: list[ProposedRelationDraft] = []
    if len(drafts) >= 2:
        relations.append(
            ProposedRelationDraft(
                source_temporary_id=drafts[0].temporary_id,
                target_reference=drafts[1].temporary_id,
                relation_type="related_to",
                confidence=0.72,
                rationale="Both candidates describe approval boundaries.",
            )
        )
    return tuple(drafts), tuple(relations)


def extract_document_nodes(
    *, locator: str, content_hash: str, markdown: str
) -> tuple[ProposedNodeDraft, ...]:
    blocks = parse_markdown_blocks(markdown)
    heading_indexes = [index for index, block in enumerate(blocks) if block.type == "heading"]
    if not heading_indexes:
        return (
            ProposedNodeDraft(
                temporary_id=f"proposal.{_slug(Path(locator).stem)}",
                title=Path(locator).stem or "Imported document",
                node_type="ImportedDocumentSection",
                content=markdown.strip(),
                tags=("document",),
                authority="reference",
                source_refs=(
                    {
                        "type": "document",
                        "path": locator,
                        "hash": content_hash,
                        "heading_path": [],
                        "line_range": [1, max(1, len(markdown.splitlines()))],
                    },
                ),
                rationale="Document has no headings; imported as one candidate section.",
                confidence=0.62,
            ),
        )

    drafts: list[ProposedNodeDraft] = []
    heading_path: list[tuple[int, str]] = []
    for position, block_index in enumerate(heading_indexes):
        heading = blocks[block_index]
        if heading.heading_level is None or heading.heading_text is None:
            continue
        heading_path = [
            (level, text) for level, text in heading_path if level < heading.heading_level
        ]
        heading_path.append((heading.heading_level, heading.heading_text))
        next_index = (
            heading_indexes[position + 1] if position + 1 < len(heading_indexes) else len(blocks)
        )
        section_blocks = blocks[block_index + 1 : next_index]
        content = "\n\n".join(section.text for section in section_blocks).strip()
        if not content:
            continue
        start_line = heading.start_line
        end_line = section_blocks[-1].end_line if section_blocks else heading.end_line
        title = heading.heading_text
        drafts.append(
            ProposedNodeDraft(
                temporary_id=f"proposal.doc.{_slug(title)}",
                title=title,
                node_type="ImportedDocumentSection",
                content=content,
                tags=("document",),
                authority="reference",
                source_refs=(
                    {
                        "type": "document",
                        "path": locator,
                        "hash": content_hash,
                        "heading_path": [text for _, text in heading_path],
                        "line_range": [start_line, end_line],
                    },
                ),
                rationale="Generated from Markdown heading section.",
                confidence=0.74,
            )
        )
    return tuple(drafts)


def extract_project_nodes(
    *, root: Path, selected_files: tuple[Path, ...]
) -> tuple[ProposedNodeDraft, ...]:
    source_refs: tuple[dict[str, object], ...] = tuple(
        {
            "type": "project_file",
            "path": str(path.relative_to(root)),
        }
        for path in selected_files
    )
    names = ", ".join(str(path.relative_to(root)) for path in selected_files[:8])
    drafts = [
        ProposedNodeDraft(
            temporary_id="proposal.project-overview",
            title="Project overview",
            node_type="ProjectOverview",
            content=f"Project scan selected {len(selected_files)} files. Key files: {names}.",
            tags=("project", "overview"),
            authority="reference",
            source_refs=source_refs,
            rationale="Generated from selected project file tree.",
            confidence=0.68,
        )
    ]
    if any(path.name.lower() in {"agents.md", "readme.md"} for path in selected_files):
        drafts.append(
            ProposedNodeDraft(
                temporary_id="proposal.project-constraints",
                title="Project architecture constraints",
                node_type="Constraint",
                content=(
                    "Project knowledge must preserve workspace_id boundaries, staging before "
                    "approval, and the separation between Source, Capture Proposal, and MemoryNode."
                ),
                tags=("project", "constraints"),
                authority="canonical",
                source_refs=source_refs,
                rationale="README/AGENTS-style files usually contain project constraints.",
                confidence=0.76,
            )
        )
    if any("src" in path.parts for path in selected_files):
        drafts.append(
            ProposedNodeDraft(
                temporary_id="proposal.project-modules",
                title="Project module map",
                node_type="ModuleMap",
                content=(
                    "The src tree contains implementation modules that should be curated "
                    "separately from raw Source Index records."
                ),
                tags=("project", "modules"),
                authority="reference",
                source_refs=source_refs,
                rationale="Generated from selected source tree paths.",
                confidence=0.66,
            )
        )
    return tuple(drafts)


def stable_node_id(workspace_id: str, title: str) -> str:
    cleaned = title.strip()
    if not cleaned:
        raise ValueError("title cannot be empty")
    slug = _slug(cleaned) or "node"
    if _needs_hash_suffix(cleaned):
        digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:10]
        slug = f"{slug}-{digest}"
    return validate_node_id(f"{workspace_id}.{slug}")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug


def _needs_hash_suffix(value: str) -> bool:
    return re.search(r"[^A-Za-z0-9 _-]", value) is not None
