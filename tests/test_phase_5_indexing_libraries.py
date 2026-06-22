from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rhine_vault.api import create_app
from rhine_vault.capture.service import CaptureService
from rhine_vault.storage.sqlite import SQLiteStore


def _approve_manual_node(
    store: SQLiteStore,
    *,
    workspace_id: str,
    title: str,
    content: str,
    node_type: str = "Note",
) -> dict[str, object]:
    capture = CaptureService(store)
    proposal = capture.create_manual_proposal(
        workspace_id=workspace_id,
        title=title,
        node_type=node_type,
        content=content,
        authority="canonical",
        tags=("phase5",),
    )
    staged = store.save_staging(
        workspace_id=workspace_id,
        proposal_id=proposal["proposal_id"],
        temporary_ids=(proposal["proposed_nodes"][0]["temporary_id"],),
    )
    return store.approve_staging(
        workspace_id=workspace_id,
        entry_ids=(staged[0]["entry_id"],),
        actor_id="user:reviewer",
    )[0]


def test_phase_5_processes_index_jobs_into_rebuildable_chunks(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / ".rhine" / "vault.db", vault_root=tmp_path)
    node = _approve_manual_node(
        store,
        workspace_id="demo-workspace",
        title="Chunked node",
        content="## API\n\nChunk indexing should be rebuildable and deterministic.",
    )

    initial_jobs = store.list_index_jobs("demo-workspace")
    processed = store.process_index_jobs("demo-workspace")
    chunks = store.list_index_chunks(
        workspace_id="demo-workspace",
        node_id=str(node["node_id"]),
    )
    rebuild_jobs = store.rebuild_derived_index("demo-workspace")
    rebuilt = store.process_index_jobs("demo-workspace")

    assert initial_jobs[0]["status"] == "queued"
    assert processed["processed"][0]["status"] == "succeeded"
    assert processed["processed"][0]["chunk_count"] >= 1
    assert chunks[0]["node_id"] == node["node_id"]
    assert chunks[0]["chunking_profile_id"] == "technical"
    assert "Chunk indexing" in chunks[0]["content"]
    assert rebuild_jobs[0]["operation"] == "rebuild"
    assert rebuilt["processed"][0]["status"] == "succeeded"


def test_phase_5_library_snapshot_and_lock_are_explicit(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / ".rhine" / "vault.db", vault_root=tmp_path)
    _approve_manual_node(
        store,
        workspace_id="library-neoforge-1-21-1",
        title="NeoForge registry rule",
        content="Use DeferredRegister for registry entries.",
    )

    snapshot = store.publish_library_snapshot(
        workspace_id="library-neoforge-1-21-1",
        version="1.0.0",
        git_tag="v1.0.0",
        commit_hash="abc123",
    )
    dependency = store.lock_workspace_dependency(
        project_workspace_id="demo-workspace",
        alias="neoforge",
        library_workspace_id="library-neoforge-1-21-1",
        version="1.0.0",
        version_requirement="~1.0.0",
    )
    dependencies = store.list_workspace_dependencies("demo-workspace")
    lock_file = tmp_path / "data" / "workspaces" / "demo-workspace" / "rhine-lock.yaml"

    assert snapshot["manifest"]["node_count"] == 1
    assert snapshot["manifest_hash"].startswith("sha256:")
    assert (tmp_path / snapshot["snapshot_path"]).is_file()
    assert dependency["manifest_hash"] == snapshot["manifest_hash"]
    assert dependencies == [dependency]
    assert "neoforge:" in lock_file.read_text(encoding="utf-8")
    assert "resolved_version: 1.0.0" in lock_file.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="already exists"):
        store.publish_library_snapshot(
            workspace_id="library-neoforge-1-21-1",
            version="1.0.0",
        )


def test_phase_5_library_upgrade_report_does_not_update_lock(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / ".rhine" / "vault.db", vault_root=tmp_path)
    _approve_manual_node(
        store,
        workspace_id="library-neoforge-1-21-1",
        title="NeoForge registry rule",
        content="Use DeferredRegister for registry entries.",
    )
    store.publish_library_snapshot(
        workspace_id="library-neoforge-1-21-1",
        version="1.0.0",
        git_tag="v1.0.0",
        commit_hash="commit-100",
    )
    dependency = store.lock_workspace_dependency(
        project_workspace_id="demo-workspace",
        alias="neoforge",
        library_workspace_id="library-neoforge-1-21-1",
        version="1.0.0",
        version_requirement="~1.0.0",
    )
    _approve_manual_node(
        store,
        workspace_id="library-neoforge-1-21-1",
        title="NeoForge registry rule",
        content="Use DeferredRegister plus RegistryObject wrappers.",
    )
    _approve_manual_node(
        store,
        workspace_id="library-neoforge-1-21-1",
        title="NeoForge event bus rule",
        content="Register mod event listeners on the mod event bus.",
    )
    store.publish_library_snapshot(
        workspace_id="library-neoforge-1-21-1",
        version="1.1.0",
        git_tag="v1.1.0",
        commit_hash="commit-110",
    )

    report = store.dependency_upgrade_report(
        project_workspace_id="demo-workspace",
        alias="neoforge",
    )
    dependencies = store.list_workspace_dependencies("demo-workspace")
    lock_file = tmp_path / "data" / "workspaces" / "demo-workspace" / "rhine-lock.yaml"
    explicit_same_report = store.dependency_upgrade_report(
        project_workspace_id="demo-workspace",
        alias="neoforge",
        target_version="1.0.0",
    )

    assert report["has_upgrade"] is True
    assert report["requires_approval"] is True
    assert report["applied"] is False
    assert report["current_version"] == "1.0.0"
    assert report["target_version"] == "1.1.0"
    assert report["summary"]["added"] == 1
    assert report["summary"]["changed"] == 1
    assert report["changes"]["added"][0]["title"] == "NeoForge event bus rule"
    assert report["changes"]["changed"][0]["fields"]["content_hash"]
    assert dependencies[0]["resolved_version"] == dependency["resolved_version"]
    assert "resolved_version: 1.0.0" in lock_file.read_text(encoding="utf-8")
    assert explicit_same_report["has_upgrade"] is False


def test_phase_5_fastapi_index_and_library_endpoints(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / ".rhine" / "vault.db"))
    client.post(
        "/api/workspaces",
        json={
            "workspace_id": "library-neoforge-1-21-1",
            "workspace_type": "library",
            "display_name": "NeoForge 1.21.1",
        },
    )
    proposal = client.post(
        "/api/manual",
        json={
            "workspace_id": "library-neoforge-1-21-1",
            "title": "Library API rule",
            "node_type": "Note",
            "content": "Library snapshots must be read as immutable published state.",
        },
    ).json()
    staged = client.post(
        f"/api/proposals/{proposal['proposal_id']}/stage",
        json={
            "workspace_id": "library-neoforge-1-21-1",
            "temporary_ids": [proposal["proposed_nodes"][0]["temporary_id"]],
        },
    ).json()
    client.post(
        "/api/staging/approve",
        json={
            "workspace_id": "library-neoforge-1-21-1",
            "entry_ids": [staged[0]["entry_id"]],
        },
    )

    processed = client.post(
        "/api/index-jobs/process",
        json={"workspace_id": "library-neoforge-1-21-1"},
    ).json()
    chunks = client.get("/api/index-chunks?workspace_id=library-neoforge-1-21-1").json()
    snapshot = client.post(
        "/api/libraries/library-neoforge-1-21-1/snapshots",
        json={"version": "1.0.0", "git_tag": "v1.0.0", "commit_hash": "abc123"},
    ).json()
    snapshots = client.get("/api/libraries/library-neoforge-1-21-1/snapshots").json()
    read_snapshot = client.get("/api/libraries/library-neoforge-1-21-1/snapshots/1.0.0").json()
    dependency = client.post(
        "/api/workspaces/demo-workspace/dependencies",
        json={
            "alias": "neoforge",
            "library_workspace_id": "library-neoforge-1-21-1",
            "version": "1.0.0",
            "version_requirement": "~1.0.0",
        },
    ).json()
    report = client.get(
        "/api/workspaces/demo-workspace/dependencies/neoforge/upgrade-report"
    ).json()

    assert processed["processed"][0]["status"] == "succeeded"
    assert chunks[0]["workspace_id"] == "library-neoforge-1-21-1"
    assert snapshot["manifest"]["node_count"] == 1
    assert snapshots[0]["version"] == "1.0.0"
    assert read_snapshot["manifest_hash"] == snapshot["manifest_hash"]
    assert dependency["alias"] == "neoforge"
    assert dependency["resolved_version"] == "1.0.0"
    assert report["has_upgrade"] is False
    assert report["applied"] is False


def test_phase_5_ui_surfaces_expose_indexing_and_library_controls() -> None:
    webui = Path("src/rhine_vault/api/static/index.html").read_text(encoding="utf-8")
    element_app = Path("ui/src/App.vue").read_text(encoding="utf-8")
    element_api = Path("ui/src/api.ts").read_text(encoding="utf-8")

    assert "show('phase5')" in webui
    assert "索引与 Library" in webui
    assert "/api/index-jobs/process" in webui
    assert "/api/index-chunks" in webui
    assert "/api/libraries/${libraryWorkspace}/snapshots" in webui
    assert "/upgrade-report" in webui

    assert "activity === 'library'" in element_app
    assert "索引与 Library" in element_app
    assert "runProcessIndexJobs" in element_app
    assert "runPublishLibrarySnapshot" in element_app
    assert "runDependencyUpgradeReport" in element_app

    assert "processIndexJobs" in element_api
    assert "publishLibrarySnapshot" in element_api
    assert "dependencyUpgradeReport" in element_api
