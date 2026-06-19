"""SQLite persistence for capture and formal workflow slices."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from rhine_vault.domain.ids import validate_actor_id, validate_node_id, validate_workspace_id
from rhine_vault.markdown import parse_markdown_document
from rhine_vault.workflow import (
    build_node_diff,
    commit_paths,
    markdown_path_for_node,
    render_node_markdown,
    validate_candidate_node,
)


@dataclass(frozen=True)
class SearchHit:
    node_id: str
    workspace_id: str
    title: str
    node_type: str
    content: str
    authority: str
    status: str
    tags: tuple[str, ...]
    relations: tuple[dict[str, Any], ...]
    source_refs: tuple[dict[str, Any], ...]
    revision: int
    score: float


class SQLiteStore:
    def __init__(self, database_path: Path | str, vault_root: Path | str | None = None) -> None:
        self.database_path = Path(database_path)
        self.vault_root = Path(vault_root) if vault_root is not None else self._infer_vault_root()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _infer_vault_root(self) -> Path:
        if self.database_path.parent.name == ".rhine":
            return self.database_path.parent.parent
        return self.database_path.parent

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                PRAGMA foreign_keys = ON;
                CREATE TABLE IF NOT EXISTS sources (
                    source_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    locator TEXT,
                    content_hash TEXT,
                    metadata_json TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS proposals (
                    proposal_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    source_ids_json TEXT NOT NULL,
                    proposed_nodes_json TEXT NOT NULL,
                    proposed_relations_json TEXT NOT NULL,
                    rationale TEXT,
                    confidence REAL NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS staging_entries (
                    entry_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    proposal_id TEXT NOT NULL,
                    proposed_node_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memory_nodes (
                    node_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    node_type TEXT NOT NULL,
                    authority TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    content TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    source_refs_json TEXT NOT NULL,
                    relations_json TEXT NOT NULL DEFAULT '[]',
                    revision INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_nodes_fts
                USING fts5(node_id UNINDEXED, workspace_id UNINDEXED, title, content);
                CREATE TABLE IF NOT EXISTS source_index (
                    record_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    preview TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS changesets (
                    changeset_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    staging_entry_ids_json TEXT NOT NULL,
                    node_ids_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    base_revision INTEGER,
                    target_revision INTEGER,
                    diff_json TEXT NOT NULL,
                    git_commit TEXT,
                    git_status TEXT NOT NULL,
                    git_message TEXT,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    approved_at TEXT
                );
                CREATE TABLE IF NOT EXISTS node_revisions (
                    revision_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    base_revision INTEGER,
                    changeset_id TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    node_snapshot_json TEXT NOT NULL,
                    markdown_path TEXT NOT NULL,
                    git_commit TEXT,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(workspace_id, node_id, revision)
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    result TEXT NOT NULL,
                    node_id TEXT,
                    staging_entry_id TEXT,
                    changeset_id TEXT,
                    before_hash TEXT,
                    after_hash TEXT,
                    error TEXT,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS index_jobs (
                    job_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    operation TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    error_message TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS external_changes (
                    change_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    node_id TEXT,
                    base_revision INTEGER,
                    status TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    base_hash TEXT,
                    diff_json TEXT NOT NULL,
                    snapshot TEXT NOT NULL,
                    detected_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversation_sessions (
                    session_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    message_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            _ensure_column(connection, "staging_entries", "base_revision", "INTEGER")
            _ensure_column(connection, "staging_entries", "validation_json", "TEXT")
            _ensure_column(connection, "staging_entries", "diff_json", "TEXT")
            _ensure_column(
                connection,
                "memory_nodes",
                "status",
                "TEXT NOT NULL DEFAULT 'active'",
            )
            _ensure_column(
                connection,
                "memory_nodes",
                "relations_json",
                "TEXT NOT NULL DEFAULT '[]'",
            )

    def create_conversation_session(
        self, *, workspace_id: str, title: str | None = None
    ) -> dict[str, Any]:
        validate_workspace_id(workspace_id)
        now = _now()
        session = {
            "session_id": str(uuid4()),
            "workspace_id": workspace_id,
            "title": _clean_title(title) or "Untitled conversation",
            "status": "open",
            "created_at": now,
            "updated_at": now,
        }
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO conversation_sessions VALUES (?, ?, ?, ?, ?, ?)",
                (
                    session["session_id"],
                    workspace_id,
                    session["title"],
                    session["status"],
                    session["created_at"],
                    session["updated_at"],
                ),
            )
        return session

    def list_conversation_sessions(self, workspace_id: str) -> list[dict[str, Any]]:
        validate_workspace_id(workspace_id)
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM conversation_sessions
                WHERE workspace_id = ?
                ORDER BY updated_at DESC
                """,
                (workspace_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_conversation_message(
        self,
        *,
        workspace_id: str,
        session_id: str,
        role: str,
        content: str,
    ) -> dict[str, Any]:
        validate_workspace_id(workspace_id)
        clean_role = _clean_role(role)
        clean_content = content.strip()
        if not clean_content:
            raise ValueError("content cannot be empty")
        now = _now()
        with self.connect() as connection:
            session = connection.execute(
                """
                SELECT * FROM conversation_sessions
                WHERE workspace_id = ? AND session_id = ?
                """,
                (workspace_id, session_id),
            ).fetchone()
            if session is None:
                raise KeyError(session_id)
            ordinal_row = connection.execute(
                """
                SELECT COALESCE(MAX(ordinal), 0) + 1 AS next_ordinal
                FROM conversation_messages
                WHERE workspace_id = ? AND session_id = ?
                """,
                (workspace_id, session_id),
            ).fetchone()
            ordinal = int(ordinal_row["next_ordinal"])
            message = {
                "message_id": str(uuid4()),
                "workspace_id": workspace_id,
                "session_id": session_id,
                "role": clean_role,
                "content": clean_content,
                "ordinal": ordinal,
                "created_at": now,
            }
            connection.execute(
                "INSERT INTO conversation_messages VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    message["message_id"],
                    workspace_id,
                    session_id,
                    clean_role,
                    clean_content,
                    ordinal,
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE conversation_sessions
                SET updated_at = ?
                WHERE workspace_id = ? AND session_id = ?
                """,
                (now, workspace_id, session_id),
            )
        return message

    def list_conversation_messages(
        self, *, workspace_id: str, session_id: str
    ) -> list[dict[str, Any]]:
        validate_workspace_id(workspace_id)
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM conversation_messages
                WHERE workspace_id = ? AND session_id = ?
                ORDER BY ordinal
                """,
                (workspace_id, session_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_source(
        self,
        *,
        workspace_id: str,
        source_type: str,
        origin: str,
        body: str,
        locator: str | None = None,
        content_hash: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        validate_workspace_id(workspace_id)
        duplicate_of = self._find_duplicate_source(
            workspace_id=workspace_id,
            source_type=source_type,
            locator=locator,
            content_hash=content_hash,
        )
        effective_metadata = dict(metadata or {})
        if duplicate_of is not None:
            effective_metadata["duplicate_of"] = duplicate_of
        source = {
            "source_id": str(uuid4()),
            "workspace_id": workspace_id,
            "source_type": source_type,
            "origin": origin,
            "locator": locator,
            "content_hash": content_hash,
            "metadata": effective_metadata,
            "body": body,
            "created_at": _now(),
        }
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source["source_id"],
                    workspace_id,
                    source_type,
                    origin,
                    locator,
                    content_hash,
                    json.dumps(effective_metadata, ensure_ascii=False),
                    body,
                    source["created_at"],
                ),
            )
        return source

    def add_proposal(
        self,
        *,
        workspace_id: str,
        source_ids: tuple[str, ...],
        proposed_nodes: tuple[dict[str, Any], ...],
        proposed_relations: tuple[dict[str, Any], ...] = (),
        rationale: str | None = None,
        confidence: float = 0.7,
    ) -> dict[str, Any]:
        validate_workspace_id(workspace_id)
        proposal = {
            "proposal_id": str(uuid4()),
            "workspace_id": workspace_id,
            "source_ids": source_ids,
            "proposed_nodes": proposed_nodes,
            "proposed_relations": proposed_relations,
            "rationale": rationale,
            "confidence": confidence,
            "status": "pending_review",
            "created_at": _now(),
        }
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO proposals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal["proposal_id"],
                    workspace_id,
                    json.dumps(source_ids),
                    json.dumps(proposed_nodes, ensure_ascii=False),
                    json.dumps(proposed_relations, ensure_ascii=False),
                    rationale,
                    confidence,
                    proposal["status"],
                    proposal["created_at"],
                ),
            )
        return proposal

    def get_proposal(self, proposal_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM proposals WHERE proposal_id = ?", (proposal_id,)
            ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        return _proposal_from_row(row)

    def list_proposals(self, workspace_id: str) -> list[dict[str, Any]]:
        validate_workspace_id(workspace_id)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM proposals WHERE workspace_id = ? ORDER BY created_at",
                (workspace_id,),
            ).fetchall()
        return [_proposal_from_row(row) for row in rows]

    def update_proposed_node(
        self,
        *,
        workspace_id: str,
        proposal_id: str,
        temporary_id: str,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        validate_workspace_id(workspace_id)
        proposal = self.get_proposal(proposal_id)
        if proposal["workspace_id"] != workspace_id:
            raise ValueError("proposal belongs to a different workspace")
        nodes = []
        for node in proposal["proposed_nodes"]:
            if node["temporary_id"] == temporary_id:
                node = {**node, **patch}
            nodes.append(node)
        with self.connect() as connection:
            connection.execute(
                "UPDATE proposals SET proposed_nodes_json = ? WHERE proposal_id = ?",
                (json.dumps(nodes, ensure_ascii=False), proposal_id),
            )
        return self.get_proposal(proposal_id)

    def save_staging(
        self,
        *,
        workspace_id: str,
        proposal_id: str,
        temporary_ids: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        validate_workspace_id(workspace_id)
        proposal = self.get_proposal(proposal_id)
        if proposal["workspace_id"] != workspace_id:
            raise ValueError("proposal belongs to a different workspace")
        selected = [
            node for node in proposal["proposed_nodes"] if node["temporary_id"] in temporary_ids
        ]
        entries = []
        with self.connect() as connection:
            for node in selected:
                entry = {
                    "entry_id": str(uuid4()),
                    "workspace_id": proposal["workspace_id"],
                    "proposal_id": proposal_id,
                    "proposed_node": node,
                    "status": "pending",
                    "created_at": _now(),
                }
                node_id = validate_node_id(node["node_id"])
                existing = connection.execute(
                    """
                    SELECT * FROM memory_nodes
                    WHERE workspace_id = ? AND node_id = ?
                    """,
                    (workspace_id, node_id),
                ).fetchone()
                before = None if existing is None else _memory_node_from_row(existing)
                base_revision = None if before is None else int(before["revision"])
                validation = validate_candidate_node(node)
                diff = build_node_diff(before=before, after=node)
                connection.execute(
                    """
                    INSERT INTO staging_entries (
                        entry_id,
                        workspace_id,
                        proposal_id,
                        proposed_node_json,
                        status,
                        created_at,
                        base_revision,
                        validation_json,
                        diff_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry["entry_id"],
                        entry["workspace_id"],
                        proposal_id,
                        json.dumps(node, ensure_ascii=False),
                        entry["status"],
                        entry["created_at"],
                        base_revision,
                        json.dumps(validation, ensure_ascii=False),
                        json.dumps(diff, ensure_ascii=False),
                    ),
                )
                entry["base_revision"] = base_revision
                entry["validation"] = validation
                entry["diff"] = diff
                entries.append(entry)
            connection.execute(
                "UPDATE proposals SET status = ? WHERE proposal_id = ?",
                ("staged", proposal_id),
            )
        return entries

    def list_staging(
        self, workspace_id: str, status: str | None = "pending"
    ) -> list[dict[str, Any]]:
        validate_workspace_id(workspace_id)
        where = "WHERE workspace_id = ?"
        parameters: tuple[str, ...] = (workspace_id,)
        if status is not None:
            where += " AND status = ?"
            parameters = (workspace_id, status)
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM staging_entries {where} ORDER BY created_at", parameters
            ).fetchall()
        return [_staging_from_row(row) for row in rows]

    def update_staging_node(
        self,
        *,
        workspace_id: str,
        entry_id: str,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        validate_workspace_id(workspace_id)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM staging_entries WHERE entry_id = ?",
                (entry_id,),
            ).fetchone()
            if row is None:
                raise KeyError(entry_id)
            if row["workspace_id"] != workspace_id:
                raise ValueError("staging entry belongs to a different workspace")
            if row["status"] != "pending":
                raise ValueError("only pending staging entries can be revised")
            node = {**json.loads(row["proposed_node_json"]), **patch}
            node_id = validate_node_id(node["node_id"])
            existing = connection.execute(
                """
                SELECT * FROM memory_nodes
                WHERE workspace_id = ? AND node_id = ?
                """,
                (workspace_id, node_id),
            ).fetchone()
            before = None if existing is None else _memory_node_from_row(existing)
            validation = validate_candidate_node(node)
            diff = build_node_diff(before=before, after=node)
            connection.execute(
                """
                UPDATE staging_entries
                SET proposed_node_json = ?, validation_json = ?, diff_json = ?
                WHERE entry_id = ?
                """,
                (
                    json.dumps(node, ensure_ascii=False),
                    json.dumps(validation, ensure_ascii=False),
                    json.dumps(diff, ensure_ascii=False),
                    entry_id,
                ),
            )
        return self.get_staging_entry(workspace_id=workspace_id, entry_id=entry_id)

    def get_staging_entry(self, *, workspace_id: str, entry_id: str) -> dict[str, Any]:
        validate_workspace_id(workspace_id)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM staging_entries WHERE entry_id = ?",
                (entry_id,),
            ).fetchone()
        if row is None:
            raise KeyError(entry_id)
        if row["workspace_id"] != workspace_id:
            raise ValueError("staging entry belongs to a different workspace")
        return _staging_from_row(row)

    def approve_staging(
        self, *, workspace_id: str, entry_ids: tuple[str, ...], actor_id: str = "user:local"
    ) -> list[dict[str, Any]]:
        validate_workspace_id(workspace_id)
        validate_actor_id(actor_id)
        approved = []
        markdown_paths: list[Path] = []
        changeset_ids: list[str] = []
        with self.connect() as connection:
            for entry_id in entry_ids:
                entry = connection.execute(
                    "SELECT * FROM staging_entries WHERE entry_id = ?", (entry_id,)
                ).fetchone()
                if entry is None:
                    raise KeyError(entry_id)
                if entry["workspace_id"] != workspace_id:
                    raise ValueError("staging entry belongs to a different workspace")
                if entry["status"] != "pending":
                    raise ValueError("staging entry is not pending")
                node = json.loads(entry["proposed_node_json"])
                node_id = validate_node_id(node["node_id"])
                validation = validate_candidate_node(node)
                before_row = connection.execute(
                    """
                    SELECT * FROM memory_nodes
                    WHERE workspace_id = ? AND node_id = ?
                    """,
                    (workspace_id, node_id),
                ).fetchone()
                before = None if before_row is None else _memory_node_from_row(before_row)
                base_revision = (
                    None if entry["base_revision"] is None else int(entry["base_revision"])
                )
                current_revision = None if before is None else int(before["revision"])
                diff = build_node_diff(before=before, after=node)
                connection.execute(
                    """
                    UPDATE staging_entries
                    SET validation_json = ?, diff_json = ?
                    WHERE entry_id = ?
                    """,
                    (
                        json.dumps(validation, ensure_ascii=False),
                        json.dumps(diff, ensure_ascii=False),
                        entry_id,
                    ),
                )
                if validation:
                    self._add_audit_event(
                        connection,
                        workspace_id=workspace_id,
                        actor_id=actor_id,
                        action="staging.validate",
                        result="blocked",
                        node_id=node_id,
                        staging_entry_id=entry_id,
                        error="validation failed",
                        metadata={"issues": validation},
                    )
                    raise ValueError("staging validation failed")
                if current_revision != base_revision:
                    self._add_audit_event(
                        connection,
                        workspace_id=workspace_id,
                        actor_id=actor_id,
                        action="staging.approve",
                        result="blocked",
                        node_id=node_id,
                        staging_entry_id=entry_id,
                        error="REVISION_CONFLICT",
                        metadata={
                            "base_revision": base_revision,
                            "current_revision": current_revision,
                        },
                    )
                    raise ValueError("REVISION_CONFLICT")
                now = _now()
                target_revision = 1 if current_revision is None else current_revision + 1
                changeset_id = str(uuid.uuid4())
                node_snapshot = self._node_dict_from_values(
                    entry["workspace_id"],
                    node,
                    now,
                    revision=target_revision,
                    created_at=None if before is None else str(before["created_at"]),
                )
                markdown_path = markdown_path_for_node(
                    vault_root=self.vault_root,
                    workspace_id=workspace_id,
                    node_id=node_id,
                )
                markdown_path.parent.mkdir(parents=True, exist_ok=True)
                markdown_text = render_node_markdown(node_snapshot, revision=target_revision)
                content_hash = _text_hash(markdown_text)
                previous_revision = connection.execute(
                    """
                    SELECT content_hash FROM node_revisions
                    WHERE workspace_id = ? AND node_id = ?
                    ORDER BY revision DESC
                    LIMIT 1
                    """,
                    (workspace_id, node_id),
                ).fetchone()
                before_hash = (
                    None if previous_revision is None else previous_revision["content_hash"]
                )
                markdown_path.write_text(markdown_text, encoding="utf-8")
                markdown_paths.append(markdown_path)
                connection.execute(
                    """
                    INSERT OR REPLACE INTO memory_nodes (
                        node_id,
                        workspace_id,
                        title,
                        node_type,
                        authority,
                        status,
                        content,
                        tags_json,
                        source_refs_json,
                        relations_json,
                        revision,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        node_id,
                        entry["workspace_id"],
                        node["title"],
                        node["node_type"],
                        node.get("authority", "approved"),
                        node.get("status", "active"),
                        node["content"],
                        json.dumps(node.get("tags", []), ensure_ascii=False),
                        json.dumps(node.get("source_refs", []), ensure_ascii=False),
                        json.dumps(node.get("relations", []), ensure_ascii=False),
                        target_revision,
                        now if before is None else before["created_at"],
                        now,
                    ),
                )
                connection.execute("DELETE FROM memory_nodes_fts WHERE node_id = ?", (node_id,))
                connection.execute(
                    "INSERT INTO memory_nodes_fts VALUES (?, ?, ?, ?)",
                    (node_id, entry["workspace_id"], node["title"], node["content"]),
                )
                connection.execute(
                    "UPDATE staging_entries SET status = ? WHERE entry_id = ?",
                    ("approved", entry_id),
                )
                connection.execute(
                    """
                    INSERT INTO changesets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        changeset_id,
                        workspace_id,
                        json.dumps([entry_id]),
                        json.dumps([node_id]),
                        "applied",
                        base_revision,
                        target_revision,
                        json.dumps(diff, ensure_ascii=False),
                        None,
                        "pending",
                        None,
                        actor_id,
                        now,
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO node_revisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        workspace_id,
                        node_id,
                        target_revision,
                        base_revision,
                        changeset_id,
                        content_hash,
                        json.dumps(node_snapshot, ensure_ascii=False),
                        str(markdown_path.relative_to(self.vault_root)),
                        None,
                        actor_id,
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO index_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        workspace_id,
                        node_id,
                        target_revision,
                        "upsert",
                        "queued",
                        0,
                        None,
                        now,
                    ),
                )
                self._add_audit_event(
                    connection,
                    workspace_id=workspace_id,
                    actor_id=actor_id,
                    action="staging.approve",
                    result="succeeded",
                    node_id=node_id,
                    staging_entry_id=entry_id,
                    changeset_id=changeset_id,
                    before_hash=before_hash,
                    after_hash=content_hash,
                    metadata={"revision": target_revision},
                )
                changeset_ids.append(changeset_id)
                approved.append(node_snapshot)
        git_result = commit_paths(
            repo_root=self.vault_root,
            paths=tuple(markdown_paths),
            message=_commit_message(workspace_id=workspace_id, changeset_ids=tuple(changeset_ids)),
        )
        with self.connect() as connection:
            for changeset_id in changeset_ids:
                connection.execute(
                    """
                    UPDATE changesets
                    SET git_commit = ?, git_status = ?, git_message = ?
                    WHERE changeset_id = ?
                    """,
                    (
                        git_result.commit,
                        git_result.status,
                        git_result.message,
                        changeset_id,
                    ),
                )
                connection.execute(
                    """
                    UPDATE node_revisions
                    SET git_commit = ?
                    WHERE changeset_id = ?
                    """,
                    (git_result.commit, changeset_id),
                )
                self._add_audit_event(
                    connection,
                    workspace_id=workspace_id,
                    actor_id=actor_id,
                    action="git.commit",
                    result="succeeded" if git_result.status == "committed" else "blocked",
                    changeset_id=changeset_id,
                    error=None if git_result.status == "committed" else git_result.message,
                    metadata={"git_status": git_result.status, "commit": git_result.commit},
                )
        return approved

    def list_changesets(self, workspace_id: str) -> list[dict[str, Any]]:
        validate_workspace_id(workspace_id)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM changesets WHERE workspace_id = ? ORDER BY created_at",
                (workspace_id,),
            ).fetchall()
        return [_changeset_from_row(row) for row in rows]

    def list_node_revisions(self, *, workspace_id: str, node_id: str) -> list[dict[str, Any]]:
        validate_workspace_id(workspace_id)
        validate_node_id(node_id)
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM node_revisions
                WHERE workspace_id = ? AND node_id = ?
                ORDER BY revision
                """,
                (workspace_id, node_id),
            ).fetchall()
        return [_node_revision_from_row(row) for row in rows]

    def rollback_node(
        self,
        *,
        workspace_id: str,
        node_id: str,
        revision: int,
        actor_id: str = "user:local",
    ) -> dict[str, Any]:
        validate_workspace_id(workspace_id)
        validate_node_id(node_id)
        validate_actor_id(actor_id)
        now = _now()
        changeset_id = str(uuid.uuid4())
        with self.connect() as connection:
            current_row = connection.execute(
                """
                SELECT * FROM memory_nodes
                WHERE workspace_id = ? AND node_id = ?
                """,
                (workspace_id, node_id),
            ).fetchone()
            if current_row is None:
                raise KeyError(node_id)
            target_row = connection.execute(
                """
                SELECT * FROM node_revisions
                WHERE workspace_id = ? AND node_id = ? AND revision = ?
                """,
                (workspace_id, node_id, revision),
            ).fetchone()
            if target_row is None:
                raise KeyError(f"{node_id}@{revision}")
            current = _memory_node_from_row(current_row)
            target_snapshot = json.loads(target_row["node_snapshot_json"])
            base_revision = int(current["revision"])
            current_revision_row = connection.execute(
                """
                SELECT content_hash FROM node_revisions
                WHERE workspace_id = ? AND node_id = ? AND revision = ?
                """,
                (workspace_id, node_id, base_revision),
            ).fetchone()
            before_hash = (
                None if current_revision_row is None else current_revision_row["content_hash"]
            )
            target_revision = base_revision + 1
            rollback_node = {
                **target_snapshot,
                "revision": target_revision,
                "created_at": current["created_at"],
                "updated_at": now,
            }
            diff = build_node_diff(before=current, after=rollback_node)
            markdown_path = markdown_path_for_node(
                vault_root=self.vault_root,
                workspace_id=workspace_id,
                node_id=node_id,
            )
            markdown_path.parent.mkdir(parents=True, exist_ok=True)
            markdown_text = render_node_markdown(rollback_node, revision=target_revision)
            content_hash = _text_hash(markdown_text)
            markdown_path.write_text(markdown_text, encoding="utf-8")
            connection.execute(
                """
                INSERT OR REPLACE INTO memory_nodes (
                    node_id,
                    workspace_id,
                    title,
                    node_type,
                    authority,
                    status,
                    content,
                    tags_json,
                    source_refs_json,
                    relations_json,
                    revision,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node_id,
                    workspace_id,
                    rollback_node["title"],
                    rollback_node["node_type"],
                    rollback_node.get("authority", "approved"),
                    rollback_node.get("status", "active"),
                    rollback_node["content"],
                    json.dumps(rollback_node.get("tags", []), ensure_ascii=False),
                    json.dumps(rollback_node.get("source_refs", []), ensure_ascii=False),
                    json.dumps(rollback_node.get("relations", []), ensure_ascii=False),
                    target_revision,
                    current["created_at"],
                    now,
                ),
            )
            connection.execute("DELETE FROM memory_nodes_fts WHERE node_id = ?", (node_id,))
            connection.execute(
                "INSERT INTO memory_nodes_fts VALUES (?, ?, ?, ?)",
                (node_id, workspace_id, rollback_node["title"], rollback_node["content"]),
            )
            connection.execute(
                """
                INSERT INTO changesets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    changeset_id,
                    workspace_id,
                    json.dumps([]),
                    json.dumps([node_id]),
                    "applied",
                    base_revision,
                    target_revision,
                    json.dumps(
                        {
                            **diff,
                            "change_type": "rollback",
                            "restored_from_revision": revision,
                        },
                        ensure_ascii=False,
                    ),
                    None,
                    "pending",
                    None,
                    actor_id,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO node_revisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    workspace_id,
                    node_id,
                    target_revision,
                    base_revision,
                    changeset_id,
                    content_hash,
                    json.dumps(rollback_node, ensure_ascii=False),
                    str(markdown_path.relative_to(self.vault_root)),
                    None,
                    actor_id,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO index_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    workspace_id,
                    node_id,
                    target_revision,
                    "upsert",
                    "queued",
                    0,
                    None,
                    now,
                ),
            )
            self._add_audit_event(
                connection,
                workspace_id=workspace_id,
                actor_id=actor_id,
                action="node.rollback",
                result="succeeded",
                node_id=node_id,
                changeset_id=changeset_id,
                before_hash=before_hash,
                after_hash=content_hash,
                metadata={
                    "restored_from_revision": revision,
                    "previous_revision": base_revision,
                    "new_revision": target_revision,
                },
            )
        git_result = commit_paths(
            repo_root=self.vault_root,
            paths=(markdown_path,),
            message=f"node({node_id}): rollback to revision {revision}",
        )
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE changesets
                SET git_commit = ?, git_status = ?, git_message = ?
                WHERE changeset_id = ?
                """,
                (git_result.commit, git_result.status, git_result.message, changeset_id),
            )
            connection.execute(
                """
                UPDATE node_revisions
                SET git_commit = ?
                WHERE changeset_id = ?
                """,
                (git_result.commit, changeset_id),
            )
            self._add_audit_event(
                connection,
                workspace_id=workspace_id,
                actor_id=actor_id,
                action="git.commit",
                result="succeeded" if git_result.status == "committed" else "blocked",
                changeset_id=changeset_id,
                error=None if git_result.status == "committed" else git_result.message,
                metadata={"git_status": git_result.status, "commit": git_result.commit},
            )
        return rollback_node

    def list_audit_events(self, workspace_id: str) -> list[dict[str, Any]]:
        validate_workspace_id(workspace_id)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_events WHERE workspace_id = ? ORDER BY created_at",
                (workspace_id,),
            ).fetchall()
        return [_audit_event_from_row(row) for row in rows]

    def list_index_jobs(self, workspace_id: str) -> list[dict[str, Any]]:
        validate_workspace_id(workspace_id)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM index_jobs WHERE workspace_id = ? ORDER BY created_at",
                (workspace_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def detect_external_changes(self, workspace_id: str) -> list[dict[str, Any]]:
        validate_workspace_id(workspace_id)
        nodes_dir = self.vault_root / "data" / "workspaces" / workspace_id / "nodes"
        if not nodes_dir.exists():
            return []
        detected: list[dict[str, Any]] = []
        with self.connect() as connection:
            for path in sorted(nodes_dir.glob("*.md")):
                snapshot = path.read_text(encoding="utf-8")
                node_id = _extract_frontmatter_value(snapshot, "node_id")
                if node_id is None:
                    continue
                latest = connection.execute(
                    """
                    SELECT revision, content_hash FROM node_revisions
                    WHERE workspace_id = ? AND node_id = ?
                    ORDER BY revision DESC
                    LIMIT 1
                    """,
                    (workspace_id, node_id),
                ).fetchone()
                if latest is None:
                    continue
                content_hash = _text_hash(snapshot)
                if content_hash == latest["content_hash"]:
                    continue
                existing = connection.execute(
                    """
                    SELECT * FROM external_changes
                    WHERE workspace_id = ? AND path = ? AND content_hash = ?
                    """,
                    (workspace_id, str(path.relative_to(self.vault_root)), content_hash),
                ).fetchone()
                if existing is not None:
                    detected.append(_external_change_from_row(existing))
                    continue
                diff = {
                    "change_type": "external_update",
                    "fields": {
                        "markdown": {
                            "before_hash": latest["content_hash"],
                            "after_hash": content_hash,
                        }
                    },
                }
                change_id = str(uuid.uuid4())
                now = _now()
                connection.execute(
                    """
                    INSERT INTO external_changes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        change_id,
                        workspace_id,
                        str(path.relative_to(self.vault_root)),
                        node_id,
                        latest["revision"],
                        "detected",
                        content_hash,
                        latest["content_hash"],
                        json.dumps(diff, ensure_ascii=False),
                        snapshot,
                        now,
                    ),
                )
                self._add_audit_event(
                    connection,
                    workspace_id=workspace_id,
                    actor_id="system:watcher",
                    action="external_change.detect",
                    result="succeeded",
                    node_id=node_id,
                    metadata={"path": str(path.relative_to(self.vault_root))},
                )
                detected.append(
                    {
                        "change_id": change_id,
                        "workspace_id": workspace_id,
                        "path": str(path.relative_to(self.vault_root)),
                        "node_id": node_id,
                        "base_revision": latest["revision"],
                        "status": "detected",
                        "content_hash": content_hash,
                        "base_hash": latest["content_hash"],
                        "diff": diff,
                        "snapshot": snapshot,
                        "detected_at": now,
                    }
                )
        return detected

    def list_external_changes(self, workspace_id: str) -> list[dict[str, Any]]:
        validate_workspace_id(workspace_id)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM external_changes WHERE workspace_id = ? ORDER BY detected_at",
                (workspace_id,),
            ).fetchall()
        return [_external_change_from_row(row) for row in rows]

    def approve_external_change(
        self, *, workspace_id: str, change_id: str, actor_id: str = "user:local"
    ) -> dict[str, Any]:
        validate_workspace_id(workspace_id)
        validate_actor_id(actor_id)
        markdown_paths: list[Path] = []
        changeset_id = str(uuid.uuid4())
        approved_snapshot: dict[str, Any]
        with self.connect() as connection:
            change_row = connection.execute(
                "SELECT * FROM external_changes WHERE change_id = ?", (change_id,)
            ).fetchone()
            if change_row is None:
                raise KeyError(change_id)
            change = _external_change_from_row(change_row)
            if change["workspace_id"] != workspace_id:
                raise ValueError("external change belongs to a different workspace")
            if change["status"] != "detected":
                raise ValueError("external change is not pending review")
            node_id = validate_node_id(str(change["node_id"]))
            current_row = connection.execute(
                """
                SELECT * FROM memory_nodes
                WHERE workspace_id = ? AND node_id = ?
                """,
                (workspace_id, node_id),
            ).fetchone()
            if current_row is None:
                raise ValueError("external change node is not approved")
            current = _memory_node_from_row(current_row)
            base_revision = int(change["base_revision"])
            current_revision = int(current["revision"])
            if current_revision != base_revision:
                self._add_audit_event(
                    connection,
                    workspace_id=workspace_id,
                    actor_id=actor_id,
                    action="external_change.approve",
                    result="blocked",
                    node_id=node_id,
                    error="REVISION_CONFLICT",
                    metadata={
                        "change_id": change_id,
                        "base_revision": base_revision,
                        "current_revision": current_revision,
                    },
                )
                raise ValueError("REVISION_CONFLICT")

            candidate = _node_from_external_markdown(
                markdown=change["snapshot"],
                current=current,
                workspace_id=workspace_id,
                node_id=node_id,
            )
            validation = validate_candidate_node(candidate)
            if validation:
                self._add_audit_event(
                    connection,
                    workspace_id=workspace_id,
                    actor_id=actor_id,
                    action="external_change.validate",
                    result="blocked",
                    node_id=node_id,
                    error="validation failed",
                    metadata={"change_id": change_id, "issues": validation},
                )
                raise ValueError("external change validation failed")

            now = _now()
            target_revision = current_revision + 1
            node_snapshot = self._node_dict_from_values(
                workspace_id,
                candidate,
                now,
                revision=target_revision,
                created_at=str(current["created_at"]),
            )
            approved_snapshot = node_snapshot
            diff = build_node_diff(before=current, after=candidate)
            diff["external_change_id"] = change_id
            markdown_path = self.vault_root / str(change["path"])
            markdown_path.parent.mkdir(parents=True, exist_ok=True)
            markdown_text = render_node_markdown(node_snapshot, revision=target_revision)
            content_hash = _text_hash(markdown_text)
            markdown_path.write_text(markdown_text, encoding="utf-8")
            markdown_paths.append(markdown_path)

            connection.execute(
                """
                INSERT OR REPLACE INTO memory_nodes (
                    node_id,
                    workspace_id,
                    title,
                    node_type,
                    authority,
                    status,
                    content,
                    tags_json,
                    source_refs_json,
                    relations_json,
                    revision,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node_id,
                    workspace_id,
                    candidate["title"],
                    candidate["node_type"],
                    candidate.get("authority", "approved"),
                    candidate.get("status", "active"),
                    candidate["content"],
                    json.dumps(candidate.get("tags", []), ensure_ascii=False),
                    json.dumps(candidate.get("source_refs", []), ensure_ascii=False),
                    json.dumps(candidate.get("relations", []), ensure_ascii=False),
                    target_revision,
                    current["created_at"],
                    now,
                ),
            )
            connection.execute("DELETE FROM memory_nodes_fts WHERE node_id = ?", (node_id,))
            connection.execute(
                "INSERT INTO memory_nodes_fts VALUES (?, ?, ?, ?)",
                (node_id, workspace_id, candidate["title"], candidate["content"]),
            )
            connection.execute(
                """
                INSERT INTO changesets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    changeset_id,
                    workspace_id,
                    json.dumps([]),
                    json.dumps([node_id]),
                    "applied",
                    base_revision,
                    target_revision,
                    json.dumps(diff, ensure_ascii=False),
                    None,
                    "pending",
                    None,
                    actor_id,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO node_revisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    workspace_id,
                    node_id,
                    target_revision,
                    base_revision,
                    changeset_id,
                    content_hash,
                    json.dumps(node_snapshot, ensure_ascii=False),
                    str(markdown_path.relative_to(self.vault_root)),
                    None,
                    actor_id,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO index_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    workspace_id,
                    node_id,
                    target_revision,
                    "upsert",
                    "queued",
                    0,
                    None,
                    now,
                ),
            )
            connection.execute(
                "UPDATE external_changes SET status = ? WHERE change_id = ?",
                ("approved", change_id),
            )
            self._add_audit_event(
                connection,
                workspace_id=workspace_id,
                actor_id=actor_id,
                action="external_change.approve",
                result="succeeded",
                node_id=node_id,
                changeset_id=changeset_id,
                before_hash=change["base_hash"],
                after_hash=content_hash,
                metadata={"change_id": change_id, "revision": target_revision},
            )

        git_result = commit_paths(
            repo_root=self.vault_root,
            paths=tuple(markdown_paths),
            message=f"external-change({workspace_id}): approve {change_id}",
        )
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE changesets
                SET git_commit = ?, git_status = ?, git_message = ?
                WHERE changeset_id = ?
                """,
                (
                    git_result.commit,
                    git_result.status,
                    git_result.message,
                    changeset_id,
                ),
            )
            connection.execute(
                "UPDATE node_revisions SET git_commit = ? WHERE changeset_id = ?",
                (git_result.commit, changeset_id),
            )
            self._add_audit_event(
                connection,
                workspace_id=workspace_id,
                actor_id=actor_id,
                action="git.commit",
                result="succeeded" if git_result.status == "committed" else "blocked",
                changeset_id=changeset_id,
                error=None if git_result.status == "committed" else git_result.message,
                metadata={"git_status": git_result.status, "commit": git_result.commit},
            )
        return approved_snapshot

    def reject_external_change(
        self, *, workspace_id: str, change_id: str, actor_id: str = "user:local"
    ) -> dict[str, Any]:
        validate_workspace_id(workspace_id)
        validate_actor_id(actor_id)
        with self.connect() as connection:
            change_row = connection.execute(
                "SELECT * FROM external_changes WHERE change_id = ?", (change_id,)
            ).fetchone()
            if change_row is None:
                raise KeyError(change_id)
            change = _external_change_from_row(change_row)
            if change["workspace_id"] != workspace_id:
                raise ValueError("external change belongs to a different workspace")
            if change["status"] != "detected":
                raise ValueError("external change is not pending review")
            node_id = validate_node_id(str(change["node_id"]))
            current_row = connection.execute(
                """
                SELECT * FROM memory_nodes
                WHERE workspace_id = ? AND node_id = ?
                """,
                (workspace_id, node_id),
            ).fetchone()
            if current_row is None:
                raise ValueError("external change node is not approved")
            current = _memory_node_from_row(current_row)
            markdown_path = self.vault_root / str(change["path"])
            markdown_path.parent.mkdir(parents=True, exist_ok=True)
            markdown_path.write_text(
                render_node_markdown(current, revision=int(current["revision"])),
                encoding="utf-8",
            )
            connection.execute(
                "UPDATE external_changes SET status = ? WHERE change_id = ?",
                ("rejected", change_id),
            )
            self._add_audit_event(
                connection,
                workspace_id=workspace_id,
                actor_id=actor_id,
                action="external_change.reject",
                result="succeeded",
                node_id=node_id,
                before_hash=change["content_hash"],
                after_hash=change["base_hash"],
                metadata={"change_id": change_id, "path": change["path"]},
            )
            updated = connection.execute(
                "SELECT * FROM external_changes WHERE change_id = ?", (change_id,)
            ).fetchone()
        if updated is None:
            raise KeyError(change_id)
        return _external_change_from_row(updated)

    def _add_audit_event(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        actor_id: str,
        action: str,
        result: str,
        node_id: str | None = None,
        staging_entry_id: str | None = None,
        changeset_id: str | None = None,
        before_hash: str | None = None,
        after_hash: str | None = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO audit_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                workspace_id,
                actor_id,
                action,
                result,
                node_id,
                staging_entry_id,
                changeset_id,
                before_hash,
                after_hash,
                error,
                json.dumps(metadata or {}, ensure_ascii=False),
                _now(),
            ),
        )

    def reject_proposal(self, *, workspace_id: str, proposal_id: str) -> dict[str, Any]:
        validate_workspace_id(workspace_id)
        proposal = self.get_proposal(proposal_id)
        if proposal["workspace_id"] != workspace_id:
            raise ValueError("proposal belongs to a different workspace")
        with self.connect() as connection:
            connection.execute(
                "UPDATE proposals SET status = ? WHERE proposal_id = ?",
                ("rejected", proposal_id),
            )
        return self.get_proposal(proposal_id)

    def _find_duplicate_source(
        self,
        *,
        workspace_id: str,
        source_type: str,
        locator: str | None,
        content_hash: str | None,
    ) -> str | None:
        if content_hash is None:
            return None
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT source_id FROM sources
                WHERE workspace_id = ?
                  AND source_type = ?
                  AND COALESCE(locator, '') = COALESCE(?, '')
                  AND content_hash = ?
                ORDER BY created_at
                LIMIT 1
                """,
                (workspace_id, source_type, locator, content_hash),
            ).fetchone()
        return None if row is None else str(row["source_id"])

    def add_source_index(
        self,
        *,
        workspace_id: str,
        source_id: str,
        path: str,
        content_hash: str,
        preview: str,
    ) -> None:
        validate_workspace_id(workspace_id)
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO source_index VALUES (?, ?, ?, ?, ?, ?)",
                (str(uuid4()), workspace_id, source_id, path, content_hash, preview),
            )

    def list_source_index(self, workspace_id: str) -> list[dict[str, Any]]:
        validate_workspace_id(workspace_id)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM source_index WHERE workspace_id = ? ORDER BY path",
                (workspace_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_workspaces(self) -> list[dict[str, Any]]:
        queries = (
            "SELECT workspace_id FROM memory_nodes",
            "SELECT workspace_id FROM proposals",
            "SELECT workspace_id FROM staging_entries",
            "SELECT workspace_id FROM sources",
        )
        workspace_ids: set[str] = set()
        with self.connect() as connection:
            for query in queries:
                workspace_ids.update(
                    str(row["workspace_id"]) for row in connection.execute(query).fetchall()
                )
        return [
            {
                "workspace_id": workspace_id,
                "vault_root": str(self.vault_root),
            }
            for workspace_id in sorted(workspace_ids)
        ]

    def list_memory_nodes(self, workspace_id: str) -> list[dict[str, Any]]:
        validate_workspace_id(workspace_id)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM memory_nodes WHERE workspace_id = ? ORDER BY title",
                (workspace_id,),
            ).fetchall()
        return [_memory_node_from_row(row) for row in rows]

    def search(self, *, workspace_id: str, query: str, limit: int = 10) -> list[SearchHit]:
        validate_workspace_id(workspace_id)
        with self.connect() as connection:
            try:
                rows = connection.execute(
                    """
                    SELECT n.*, bm25(memory_nodes_fts) AS score
                    FROM memory_nodes_fts
                    JOIN memory_nodes n ON n.node_id = memory_nodes_fts.node_id
                    WHERE memory_nodes_fts.workspace_id = ?
                      AND memory_nodes_fts MATCH ?
                    ORDER BY score
                    LIMIT ?
                    """,
                    (workspace_id, _fts_query(query), limit),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = connection.execute(
                    """
                    SELECT *, 1.0 AS score FROM memory_nodes
                    WHERE workspace_id = ? AND (title LIKE ? OR content LIKE ?)
                    LIMIT ?
                    """,
                    (workspace_id, f"%{query}%", f"%{query}%", limit),
                ).fetchall()
        return [_hit_from_row(row) for row in rows]

    def _node_dict_from_values(
        self,
        workspace_id: str,
        node: dict[str, Any],
        timestamp: str,
        *,
        revision: int = 1,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        return {
            "node_id": node["node_id"],
            "workspace_id": workspace_id,
            "title": node["title"],
            "node_type": node["node_type"],
            "authority": node.get("authority", "approved"),
            "status": node.get("status", "active"),
            "content": node["content"],
            "tags": node.get("tags", []),
            "source_refs": node.get("source_refs", []),
            "relations": node.get("relations", []),
            "revision": revision,
            "created_at": timestamp if created_at is None else created_at,
            "updated_at": timestamp,
        }


def _proposal_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "proposal_id": row["proposal_id"],
        "workspace_id": row["workspace_id"],
        "source_ids": tuple(json.loads(row["source_ids_json"])),
        "proposed_nodes": json.loads(row["proposed_nodes_json"]),
        "proposed_relations": json.loads(row["proposed_relations_json"]),
        "rationale": row["rationale"],
        "confidence": row["confidence"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def _staging_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "entry_id": row["entry_id"],
        "workspace_id": row["workspace_id"],
        "proposal_id": row["proposal_id"],
        "proposed_node": json.loads(row["proposed_node_json"]),
        "status": row["status"],
        "created_at": row["created_at"],
        "base_revision": row["base_revision"],
        "validation": json.loads(row["validation_json"] or "[]"),
        "diff": json.loads(row["diff_json"] or "{}"),
    }


def _memory_node_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "node_id": row["node_id"],
        "workspace_id": row["workspace_id"],
        "title": row["title"],
        "node_type": row["node_type"],
        "authority": row["authority"],
        "status": row["status"],
        "content": row["content"],
        "tags": json.loads(row["tags_json"]),
        "source_refs": json.loads(row["source_refs_json"]),
        "relations": json.loads(row["relations_json"]),
        "revision": row["revision"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _changeset_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "changeset_id": row["changeset_id"],
        "workspace_id": row["workspace_id"],
        "staging_entry_ids": json.loads(row["staging_entry_ids_json"]),
        "node_ids": json.loads(row["node_ids_json"]),
        "status": row["status"],
        "base_revision": row["base_revision"],
        "target_revision": row["target_revision"],
        "diff": json.loads(row["diff_json"]),
        "git_commit": row["git_commit"],
        "git_status": row["git_status"],
        "git_message": row["git_message"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "approved_at": row["approved_at"],
    }


def _node_revision_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "revision_id": row["revision_id"],
        "workspace_id": row["workspace_id"],
        "node_id": row["node_id"],
        "revision": row["revision"],
        "base_revision": row["base_revision"],
        "changeset_id": row["changeset_id"],
        "content_hash": row["content_hash"],
        "node_snapshot": json.loads(row["node_snapshot_json"]),
        "markdown_path": row["markdown_path"],
        "git_commit": row["git_commit"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
    }


def _audit_event_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "event_id": row["event_id"],
        "workspace_id": row["workspace_id"],
        "actor_id": row["actor_id"],
        "action": row["action"],
        "result": row["result"],
        "node_id": row["node_id"],
        "staging_entry_id": row["staging_entry_id"],
        "changeset_id": row["changeset_id"],
        "before_hash": row["before_hash"],
        "after_hash": row["after_hash"],
        "error": row["error"],
        "metadata": json.loads(row["metadata_json"]),
        "created_at": row["created_at"],
    }


def _external_change_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "change_id": row["change_id"],
        "workspace_id": row["workspace_id"],
        "path": row["path"],
        "node_id": row["node_id"],
        "base_revision": row["base_revision"],
        "status": row["status"],
        "content_hash": row["content_hash"],
        "base_hash": row["base_hash"],
        "diff": json.loads(row["diff_json"]),
        "snapshot": row["snapshot"],
        "detected_at": row["detected_at"],
    }


def _node_from_external_markdown(
    *,
    markdown: str,
    current: dict[str, Any],
    workspace_id: str,
    node_id: str,
) -> dict[str, Any]:
    document = parse_markdown_document(markdown)
    frontmatter = document.frontmatter
    if str(frontmatter.get("workspace_id", workspace_id)) != workspace_id:
        raise ValueError("external markdown belongs to a different workspace")
    if str(frontmatter.get("node_id", node_id)) != node_id:
        raise ValueError("external markdown belongs to a different node")

    body = _content_from_rendered_markdown_body(document.body, str(frontmatter.get("title", "")))
    return {
        "node_id": node_id,
        "workspace_id": workspace_id,
        "title": str(frontmatter.get("title") or current["title"]),
        "node_type": str(frontmatter.get("node_type") or current["node_type"]),
        "authority": str(frontmatter.get("authority") or current["authority"]),
        "status": str(frontmatter.get("status") or current.get("status", "active")),
        "content": body if body else current["content"],
        "tags": _frontmatter_list(frontmatter.get("tags"), current["tags"]),
        "source_refs": _frontmatter_list(frontmatter.get("source_refs"), current["source_refs"]),
        "relations": _frontmatter_list(frontmatter.get("relations"), current.get("relations", [])),
    }


def _content_from_rendered_markdown_body(body: str, title: str) -> str:
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and lines[0].startswith("# "):
        lines.pop(0)
        if lines and not lines[0].strip():
            lines.pop(0)
    content = "\n".join(lines).strip()
    if content == title.strip():
        return ""
    return content


def _frontmatter_list(value: Any, fallback: list[Any]) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip().startswith("["):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return fallback
        return parsed if isinstance(parsed, list) else fallback
    return fallback


def _hit_from_row(row: sqlite3.Row) -> SearchHit:
    return SearchHit(
        node_id=row["node_id"],
        workspace_id=row["workspace_id"],
        title=row["title"],
        node_type=row["node_type"],
        content=row["content"],
        authority=row["authority"],
        status=row["status"],
        tags=tuple(json.loads(row["tags_json"])),
        relations=tuple(json.loads(row["relations_json"])),
        source_refs=tuple(json.loads(row["source_refs_json"])),
        revision=int(row["revision"]),
        score=float(row["score"]),
    )


def _fts_query(query: str) -> str:
    terms = [term.replace('"', "") for term in query.split() if term.strip()]
    return " OR ".join(f'"{term}"' for term in terms) or '""'


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _commit_message(*, workspace_id: str, changeset_ids: tuple[str, ...]) -> str:
    summary = changeset_ids[0] if len(changeset_ids) == 1 else f"{len(changeset_ids)} changesets"
    return f"changeset({workspace_id}): approve {summary}"


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    if column not in {row["name"] for row in rows}:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _extract_frontmatter_value(markdown: str, key: str) -> str | None:
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    prefix = f"{key}:"
    for line in lines[1:]:
        if line.strip() == "---":
            return None
        if line.startswith(prefix):
            value = line.removeprefix(prefix).strip()
            return value or None
    return None


def _clean_title(title: str | None) -> str:
    return "" if title is None else title.strip()


def _clean_role(role: str) -> str:
    cleaned = role.strip().lower()
    if cleaned not in {"user", "assistant", "system"}:
        raise ValueError("role must be user, assistant, or system")
    return cleaned
