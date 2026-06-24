"""Snapshot, import-plan and emergency read-only helpers."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from rhine_vault.markdown import parse_markdown_document
from rhine_vault.storage.sqlite import SQLiteStore

SNAPSHOT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SnapshotFile:
    path: str
    sha256: str
    size: int

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "sha256": self.sha256, "size": self.size}


def create_workspace_snapshot(
    *,
    store: SQLiteStore,
    workspace_id: str,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Create a portable read-only `.rhine` snapshot package for one workspace."""

    workspace_root = store.vault_root / "data" / "workspaces" / workspace_id
    snapshot_id = str(uuid4())
    created_at = _now()
    destination_dir = (
        Path(output_dir) if output_dir is not None else store.vault_root / ".rhine" / "snapshots"
    )
    destination_dir.mkdir(parents=True, exist_ok=True)
    package_path = destination_dir / f"{workspace_id}-{snapshot_id}.rhine"

    files: dict[str, bytes] = {}
    files["metadata.sqlite"] = store.database_path.read_bytes()
    if workspace_root.exists():
        for source_path in sorted(item for item in workspace_root.rglob("*") if item.is_file()):
            archive_path = (
                PurePosixPath("workspace")
                / workspace_id
                / source_path.relative_to(workspace_root).as_posix()
            )
            files[archive_path.as_posix()] = source_path.read_bytes()

    manifest = {
        "kind": "rhine-workspace-snapshot",
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "created_at": created_at,
        "workspace_ids": [workspace_id],
        "database_path": "metadata.sqlite",
        "file_count": len(files),
        "files": [
            _snapshot_file(path, content).to_dict() for path, content in sorted(files.items())
        ],
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode(
        "utf-8"
    )
    checksums = _checksums_text({**files, "manifest.json": manifest_bytes}).encode("utf-8")

    with zipfile.ZipFile(package_path, mode="w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr("manifest.json", manifest_bytes)
        package.writestr("checksums.sha256", checksums)
        for archive_name, content in sorted(files.items()):
            package.writestr(archive_name, content)

    return {
        "kind": "rhine-workspace-snapshot",
        "snapshot_id": snapshot_id,
        "workspace_id": workspace_id,
        "package_path": str(package_path),
        "manifest": manifest,
        "package_sha256": _file_hash(package_path),
    }


def build_import_plan(package_path: Path | str) -> dict[str, Any]:
    """Inspect a `.rhine` package and return a read-only import plan."""

    path = Path(package_path)
    if not path.is_file():
        raise FileNotFoundError(str(path))
    with zipfile.ZipFile(path, mode="r") as package:
        names = set(package.namelist())
        if "manifest.json" not in names:
            raise ValueError("snapshot package is missing manifest.json")
        if "checksums.sha256" not in names:
            raise ValueError("snapshot package is missing checksums.sha256")
        manifest = json.loads(package.read("manifest.json").decode("utf-8"))
        expected = _parse_checksums(package.read("checksums.sha256").decode("utf-8"))
        verified: list[dict[str, Any]] = []
        errors: list[str] = []
        for archive_path, expected_hash in expected.items():
            if archive_path not in names:
                errors.append(f"missing file: {archive_path}")
                continue
            content = package.read(archive_path)
            actual_hash = _bytes_hash(content)
            if actual_hash != expected_hash:
                errors.append(f"checksum mismatch: {archive_path}")
            verified.append(
                {
                    "path": archive_path,
                    "sha256": actual_hash,
                    "size": len(content),
                    "matches": actual_hash == expected_hash,
                }
            )
    return {
        "kind": "rhine-import-plan",
        "package_path": str(path),
        "schema_version": manifest.get("schema_version"),
        "snapshot_kind": manifest.get("kind"),
        "workspace_ids": manifest.get("workspace_ids", []),
        "file_count": len(verified),
        "verified": verified,
        "errors": errors,
        "can_import": not errors,
        "applied": False,
        "package_sha256": _file_hash(path),
    }


def apply_import_plan(
    *,
    store: SQLiteStore,
    package_path: Path | str,
    target_workspace_id: str | None = None,
    approve: bool = False,
    overwrite: bool = False,
    actor_id: str = "user:local",
) -> dict[str, Any]:
    """Apply a verified `.rhine` package through the normal review workflow."""

    plan = build_import_plan(package_path)
    if not plan["can_import"]:
        raise ValueError("snapshot package cannot be imported until verification errors are fixed")

    source_path = Path(package_path)
    with zipfile.ZipFile(source_path, mode="r") as package:
        manifest = json.loads(package.read("manifest.json").decode("utf-8"))
        workspace_ids = tuple(str(item) for item in manifest.get("workspace_ids", []))
        if not workspace_ids:
            raise ValueError("snapshot package does not declare a workspace")
        source_workspace_id = workspace_ids[0]
        workspace_id = target_workspace_id or source_workspace_id
        markdown_entries = _snapshot_markdown_entries(package, source_workspace_id)

    if not markdown_entries:
        raise ValueError("snapshot package does not contain Markdown nodes")

    store.register_workspace(
        workspace_id=workspace_id,
        workspace_type="project",
        display_name=f"Imported {source_workspace_id}",
    )
    existing_nodes = {
        str(node["node_id"]): node for node in store.list_memory_nodes(workspace_id=workspace_id)
    }
    imported_node_ids = [_node_id_from_markdown(text) for _, text in markdown_entries]
    if not overwrite:
        conflicts = sorted(node_id for node_id in imported_node_ids if node_id in existing_nodes)
        if conflicts:
            raise ValueError(f"import would overwrite existing nodes: {', '.join(conflicts)}")

    source = store.add_source(
        workspace_id=workspace_id,
        source_type="rhine_snapshot",
        origin="snapshot-import",
        locator=str(source_path),
        content_hash=str(plan.get("package_sha256") or _file_hash(source_path)),
        body=json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2),
        metadata={
            "snapshot_id": manifest.get("snapshot_id"),
            "source_workspace_id": source_workspace_id,
            "source_workspace_ids": list(workspace_ids),
            "source_package": str(source_path),
        },
    )
    proposed_nodes = tuple(
        _candidate_from_markdown(
            markdown=markdown,
            workspace_id=workspace_id,
            archive_path=archive_path,
            source_id=str(source["source_id"]),
            snapshot_id=str(manifest.get("snapshot_id", "")),
        )
        for archive_path, markdown in markdown_entries
    )
    proposal = store.add_proposal(
        workspace_id=workspace_id,
        source_ids=(str(source["source_id"]),),
        proposed_nodes=proposed_nodes,
        rationale="Verified `.rhine` snapshot import.",
        confidence=0.95,
    )
    staging: list[dict[str, Any]] = []
    approved_nodes: list[dict[str, Any]] = []
    if approve:
        temporary_ids = tuple(str(node["temporary_id"]) for node in proposed_nodes)
        staging = store.save_staging(
            workspace_id=workspace_id,
            proposal_id=str(proposal["proposal_id"]),
            temporary_ids=temporary_ids,
        )
        approved_nodes = store.approve_staging(
            workspace_id=workspace_id,
            entry_ids=tuple(str(entry["entry_id"]) for entry in staging),
            actor_id=actor_id,
        )
    return {
        "kind": "rhine-import-apply",
        "package_path": str(source_path),
        "target_workspace_id": workspace_id,
        "source_workspace_ids": list(workspace_ids),
        "imported_node_count": len(proposed_nodes),
        "overwrite": overwrite,
        "applied": approve,
        "proposal": proposal,
        "staging": staging,
        "approved_nodes": approved_nodes,
    }


def emergency_readonly_nodes(*, vault_root: Path | str, workspace_id: str) -> dict[str, Any]:
    """Read approved Markdown nodes without opening SQLite."""

    root = Path(vault_root)
    nodes_dir = root / "data" / "workspaces" / workspace_id / "nodes"
    nodes: list[dict[str, Any]] = []
    if nodes_dir.exists():
        for path in sorted(nodes_dir.glob("*.md")):
            markdown = path.read_text(encoding="utf-8")
            document = parse_markdown_document(markdown)
            frontmatter = document.frontmatter
            nodes.append(
                {
                    "node_id": str(frontmatter.get("node_id", "")),
                    "workspace_id": str(frontmatter.get("workspace_id", workspace_id)),
                    "title": str(frontmatter.get("title", path.stem)),
                    "node_type": str(frontmatter.get("node_type", "Note")),
                    "authority": str(frontmatter.get("authority", "approved")),
                    "status": str(frontmatter.get("status", "active")),
                    "revision": int(frontmatter.get("revision", 1)),
                    "markdown_path": str(path.relative_to(root)),
                    "content": _body_without_title(
                        document.body, str(frontmatter.get("title", ""))
                    ),
                }
            )
    return {
        "kind": "emergency-read-only",
        "workspace_id": workspace_id,
        "vault_root": str(root),
        "status": "read_only",
        "nodes": nodes,
        "node_count": len(nodes),
        "sqlite_required": False,
    }


def sqlite_health(database_path: Path | str) -> dict[str, Any]:
    path = Path(database_path)
    if not path.exists():
        return {"status": "missing", "path": str(path)}
    try:
        with sqlite3.connect(path) as connection:
            row = connection.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.DatabaseError as exc:
        return {"status": "corrupt", "path": str(path), "error": str(exc)}
    result = str(row[0]) if row else "unknown"
    return {
        "status": "healthy" if result == "ok" else "degraded",
        "path": str(path),
        "result": result,
    }


def _snapshot_file(path: str, content: bytes) -> SnapshotFile:
    return SnapshotFile(path=path, sha256=_bytes_hash(content), size=len(content))


def _checksums_text(files: dict[str, bytes]) -> str:
    return "".join(f"{_bytes_hash(content)}  {path}\n" for path, content in sorted(files.items()))


def _parse_checksums(text: str) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        digest, archive_path = line.split(maxsplit=1)
        checksums[archive_path.strip()] = digest
    return checksums


def _bytes_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _file_hash(path: Path) -> str:
    return _bytes_hash(path.read_bytes())


def _snapshot_markdown_entries(
    package: zipfile.ZipFile, source_workspace_id: str
) -> list[tuple[str, str]]:
    prefix = f"workspace/{source_workspace_id}/nodes/"
    entries: list[tuple[str, str]] = []
    for name in sorted(package.namelist()):
        if name.startswith(prefix) and name.endswith(".md"):
            entries.append((name, package.read(name).decode("utf-8")))
    return entries


def _candidate_from_markdown(
    *,
    markdown: str,
    workspace_id: str,
    archive_path: str,
    source_id: str,
    snapshot_id: str,
) -> dict[str, Any]:
    document = parse_markdown_document(markdown)
    frontmatter = document.frontmatter
    title = str(frontmatter.get("title") or Path(archive_path).stem)
    node_id = str(frontmatter.get("node_id") or Path(archive_path).stem)
    source_refs = list(_as_list(frontmatter.get("source_refs")))
    source_refs.append(
        {
            "type": "rhine_snapshot",
            "source_id": source_id,
            "snapshot_id": snapshot_id,
            "archive_path": archive_path,
        }
    )
    return {
        "temporary_id": f"proposal.import.{node_id}",
        "node_id": node_id,
        "title": title,
        "node_type": str(frontmatter.get("node_type", "Note")),
        "content": _body_without_title(document.body, title),
        "tags": list(_as_list(frontmatter.get("tags"))),
        "authority": str(frontmatter.get("authority", "approved")),
        "status": str(frontmatter.get("status", "active")),
        "source_refs": source_refs,
        "relations": list(_as_list(frontmatter.get("relations"))),
        "rationale": f"Imported from {archive_path} into {workspace_id}.",
        "confidence": 0.95,
    }


def _node_id_from_markdown(markdown: str) -> str:
    return str(parse_markdown_document(markdown).frontmatter.get("node_id", ""))


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _body_without_title(body: str, title: str) -> str:
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and lines[0].startswith("# "):
        lines.pop(0)
    content = "\n".join(lines).strip()
    return "" if content == title.strip() else content


def _now() -> str:
    return datetime.now(UTC).isoformat()
