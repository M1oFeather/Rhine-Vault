"""Capture, review, and approval orchestration for Phase 1.5."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from rhine_vault.capture.rules import (
    ProposedNodeDraft,
    extract_conversation_nodes,
    extract_document_nodes,
    extract_project_nodes,
    stable_node_id,
)
from rhine_vault.document_loaders import load_document_text
from rhine_vault.domain.ids import validate_workspace_id
from rhine_vault.storage.sqlite import SQLiteStore


class CaptureService:
    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def create_manual_proposal(
        self,
        *,
        workspace_id: str,
        title: str,
        node_type: str,
        content: str,
        authority: str = "approved",
        tags: tuple[str, ...] = (),
        relations: tuple[dict[str, Any], ...] = (),
    ) -> dict[str, Any]:
        validate_workspace_id(workspace_id)
        clean_title = _require_non_blank(title, "title")
        clean_node_type = _require_non_blank(node_type, "node_type")
        source = self.store.add_source(
            workspace_id=workspace_id,
            source_type="manual",
            origin="manual-editor",
            body=content,
            metadata={"title": clean_title, "node_type": clean_node_type},
        )
        node = _node_from_draft(
            workspace_id,
            ProposedNodeDraft(
                temporary_id=f"proposal.manual.{stable_node_id(workspace_id, clean_title)}",
                title=clean_title,
                node_type=clean_node_type,
                content=content,
                tags=tags,
                authority=authority,
                source_refs=({"type": "manual", "source_id": source["source_id"]},),
                rationale="Created from manual editor input.",
                confidence=1.0,
            ),
        )
        node["relations"] = list(relations)
        return self.store.add_proposal(
            workspace_id=workspace_id,
            source_ids=(source["source_id"],),
            proposed_nodes=(node,),
            rationale="Manual input proposal.",
            confidence=1.0,
        )

    def create_conversation_proposal(
        self,
        *,
        workspace_id: str,
        session_id: str,
        messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        validate_workspace_id(workspace_id)
        if not messages:
            raise ValueError("messages cannot be empty")
        body = "\n".join(f"{message['role']}: {message['content']}" for message in messages)
        source = self.store.add_source(
            workspace_id=workspace_id,
            source_type="conversation",
            origin=f"conversation:{session_id}",
            body=body,
            metadata={
                "session_id": session_id,
                "message_ids": [message["message_id"] for message in messages],
                "message_range": f"{messages[0]['message_id']}..{messages[-1]['message_id']}",
            },
        )
        drafts, relations = extract_conversation_nodes(session_id=session_id, messages=messages)
        return self.store.add_proposal(
            workspace_id=workspace_id,
            source_ids=(source["source_id"],),
            proposed_nodes=tuple(_node_from_draft(workspace_id, draft) for draft in drafts),
            proposed_relations=tuple(relation.__dict__ for relation in relations),
            rationale="Deterministic conversation extraction.",
            confidence=0.86,
        )

    def create_chat_session_proposal(self, *, workspace_id: str, session_id: str) -> dict[str, Any]:
        validate_workspace_id(workspace_id)
        stored_messages = self.store.list_conversation_messages(
            workspace_id=workspace_id,
            session_id=session_id,
        )
        if not stored_messages:
            raise ValueError("conversation session has no messages")
        messages = [
            {
                "message_id": message["message_id"],
                "role": message["role"],
                "content": message["content"],
            }
            for message in stored_messages
        ]
        return self.create_conversation_proposal(
            workspace_id=workspace_id,
            session_id=session_id,
            messages=messages,
        )

    def create_document_proposal(self, *, workspace_id: str, path: Path) -> dict[str, Any]:
        validate_workspace_id(workspace_id)
        loaded = load_document_text(path)
        text = loaded.text
        if not text.strip():
            raise ValueError("document loader produced no text")
        content_hash = _sha256(text)
        source = self.store.add_source(
            workspace_id=workspace_id,
            source_type="document",
            origin="document-import",
            locator=str(path),
            content_hash=content_hash,
            body=text,
            metadata={
                "path": str(path),
                "hash": content_hash,
                "source_format": loaded.source_format,
                **loaded.metadata,
            },
        )
        drafts = extract_document_nodes(locator=str(path), content_hash=content_hash, markdown=text)
        proposal = self.store.add_proposal(
            workspace_id=workspace_id,
            source_ids=(source["source_id"],),
            proposed_nodes=tuple(_node_from_draft(workspace_id, draft) for draft in drafts),
            rationale="Document section import.",
            confidence=0.74,
        )
        if "duplicate_of" in source["metadata"]:
            proposal["duplicate_of"] = source["metadata"]["duplicate_of"]
        return proposal

    def scan_project(
        self,
        *,
        workspace_id: str,
        root: Path,
        include_paths: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        validate_workspace_id(workspace_id)
        selected_files = _select_project_files(root, include_paths)
        body = "\n".join(str(path.relative_to(root)) for path in selected_files)
        source = self.store.add_source(
            workspace_id=workspace_id,
            source_type="project_file",
            origin="project-scan",
            locator=str(root),
            content_hash=_sha256(body),
            body=body,
            metadata={"root": str(root), "selected_count": len(selected_files)},
        )
        for path in selected_files:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            self.store.add_source_index(
                workspace_id=workspace_id,
                source_id=source["source_id"],
                path=str(path.relative_to(root)),
                content_hash=_sha256(text),
                preview=text[:500],
            )
        drafts = extract_project_nodes(root=root, selected_files=tuple(selected_files))
        proposal = self.store.add_proposal(
            workspace_id=workspace_id,
            source_ids=(source["source_id"],),
            proposed_nodes=tuple(_node_from_draft(workspace_id, draft) for draft in drafts),
            rationale="Controlled project scan proposal.",
            confidence=0.69,
        )
        return {
            "proposal": proposal,
            "file_tree": [str(path.relative_to(root)) for path in selected_files],
            "source_index": self.store.list_source_index(workspace_id),
        }


def _node_from_draft(workspace_id: str, draft: ProposedNodeDraft) -> dict[str, Any]:
    return {
        "temporary_id": draft.temporary_id,
        "node_id": stable_node_id(workspace_id, draft.title),
        "title": draft.title,
        "node_type": draft.node_type,
        "content": draft.content,
        "tags": list(draft.tags),
        "authority": draft.authority,
        "source_refs": list(draft.source_refs),
        "rationale": draft.rationale,
        "confidence": draft.confidence,
    }


def _require_non_blank(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} cannot be empty")
    return cleaned


def _select_project_files(root: Path, include_paths: tuple[str, ...]) -> list[Path]:
    ignored = {".git", ".venv", "__pycache__", "reference-packages", ".mypy_cache", ".ruff_cache"}
    ignored.update(_read_ignore_file(root))
    candidates: list[Path] = []
    if include_paths:
        for item in include_paths:
            path = (root / item).resolve()
            if path.is_file() and root.resolve() in path.parents:
                candidates.append(path)
            elif path.is_dir() and root.resolve() in path.parents:
                candidates.extend(_walk_project_files(path, ignored))
    else:
        for name in ("README.md", "AGENTS.md", "pyproject.toml"):
            path = root / name
            if path.exists():
                candidates.append(path)
        for directory in ("docs", "src"):
            path = root / directory
            if path.exists():
                candidates.extend(_walk_project_files(path, ignored))
    return sorted(set(candidates))[:80]


def _walk_project_files(root: Path, ignored: set[str]) -> list[Path]:
    allowed_suffixes = {".md", ".txt", ".toml", ".yaml", ".yml", ".py"}
    files: list[Path] = []
    for path in root.rglob("*"):
        if any(part in ignored for part in path.parts):
            continue
        if any(path.match(pattern) for pattern in ignored if "*" in pattern):
            continue
        if path.is_file() and path.suffix.lower() in allowed_suffixes:
            files.append(path)
    return files


def _read_ignore_file(root: Path) -> set[str]:
    ignore_file = root / ".gitignore"
    if not ignore_file.exists():
        return set()
    patterns = set()
    for line in ignore_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            patterns.add(stripped.rstrip("/"))
    return patterns


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
