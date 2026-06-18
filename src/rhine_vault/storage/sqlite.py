"""Minimal SQLite persistence for the Phase 1.5 vertical slice."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from rhine_vault.domain.ids import validate_node_id, validate_workspace_id


@dataclass(frozen=True)
class SearchHit:
    node_id: str
    workspace_id: str
    title: str
    content: str
    authority: str
    source_refs: tuple[dict[str, Any], ...]
    score: float


class SQLiteStore:
    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

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
                    content TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    source_refs_json TEXT NOT NULL,
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
                """
            )

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
                connection.execute(
                    "INSERT INTO staging_entries VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        entry["entry_id"],
                        entry["workspace_id"],
                        proposal_id,
                        json.dumps(node, ensure_ascii=False),
                        entry["status"],
                        entry["created_at"],
                    ),
                )
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

    def approve_staging(
        self, *, workspace_id: str, entry_ids: tuple[str, ...]
    ) -> list[dict[str, Any]]:
        validate_workspace_id(workspace_id)
        approved = []
        with self.connect() as connection:
            for entry_id in entry_ids:
                entry = connection.execute(
                    "SELECT * FROM staging_entries WHERE entry_id = ?", (entry_id,)
                ).fetchone()
                if entry is None:
                    raise KeyError(entry_id)
                if entry["workspace_id"] != workspace_id:
                    raise ValueError("staging entry belongs to a different workspace")
                node = json.loads(entry["proposed_node_json"])
                node_id = validate_node_id(node["node_id"])
                now = _now()
                connection.execute(
                    """
                    INSERT OR REPLACE INTO memory_nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        node_id,
                        entry["workspace_id"],
                        node["title"],
                        node["node_type"],
                        node.get("authority", "approved"),
                        node["content"],
                        json.dumps(node.get("tags", []), ensure_ascii=False),
                        json.dumps(node.get("source_refs", []), ensure_ascii=False),
                        1,
                        now,
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
                approved.append(self._node_dict_from_values(entry["workspace_id"], node, now))
        return approved

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
        self, workspace_id: str, node: dict[str, Any], timestamp: str
    ) -> dict[str, Any]:
        return {
            "node_id": node["node_id"],
            "workspace_id": workspace_id,
            "title": node["title"],
            "node_type": node["node_type"],
            "authority": node.get("authority", "approved"),
            "content": node["content"],
            "tags": node.get("tags", []),
            "source_refs": node.get("source_refs", []),
            "revision": 1,
            "created_at": timestamp,
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
    }


def _hit_from_row(row: sqlite3.Row) -> SearchHit:
    return SearchHit(
        node_id=row["node_id"],
        workspace_id=row["workspace_id"],
        title=row["title"],
        content=row["content"],
        authority=row["authority"],
        source_refs=tuple(json.loads(row["source_refs_json"])),
        score=float(row["score"]),
    )


def _fts_query(query: str) -> str:
    terms = [term.replace('"', "") for term in query.split() if term.strip()]
    return " OR ".join(f'"{term}"' for term in terms) or '""'


def _now() -> str:
    return datetime.now(UTC).isoformat()
