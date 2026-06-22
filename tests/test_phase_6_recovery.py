from __future__ import annotations

import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from rhine_vault.api import create_app
from rhine_vault.capture.service import CaptureService
from rhine_vault.recovery import (
    build_import_plan,
    create_workspace_snapshot,
    emergency_readonly_nodes,
)
from rhine_vault.storage.sqlite import SQLiteStore


def _approve_manual_node(
    store: SQLiteStore, *, workspace_id: str = "demo-workspace"
) -> dict[str, object]:
    capture = CaptureService(store)
    proposal = capture.create_manual_proposal(
        workspace_id=workspace_id,
        title="Recovery rule",
        node_type="Constraint",
        content="Recovery snapshots must verify checksums before import.",
        authority="canonical",
        tags=("recovery",),
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


def test_phase_6_workspace_snapshot_and_import_plan(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / ".rhine" / "vault.db", vault_root=tmp_path)
    _approve_manual_node(store)

    snapshot = create_workspace_snapshot(store=store, workspace_id="demo-workspace")
    package_path = Path(snapshot["package_path"])
    plan = build_import_plan(package_path)

    assert package_path.suffix == ".rhine"
    assert snapshot["manifest"]["workspace_ids"] == ["demo-workspace"]
    assert snapshot["manifest"]["database_path"] == "metadata.sqlite"
    assert plan["can_import"] is True
    assert plan["applied"] is False
    assert plan["workspace_ids"] == ["demo-workspace"]
    with zipfile.ZipFile(package_path) as package:
        names = set(package.namelist())
    assert "manifest.json" in names
    assert "checksums.sha256" in names
    assert "metadata.sqlite" in names
    assert any(name.startswith("workspace/demo-workspace/nodes/") for name in names)


def test_phase_6_import_plan_detects_tampered_package(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / ".rhine" / "vault.db", vault_root=tmp_path)
    _approve_manual_node(store)
    snapshot = create_workspace_snapshot(store=store, workspace_id="demo-workspace")
    package_path = Path(snapshot["package_path"])
    tampered_path = tmp_path / "tampered.rhine"

    with zipfile.ZipFile(package_path) as source_package:
        package_entries = {name: source_package.read(name) for name in source_package.namelist()}
    node_path = next(
        name for name in package_entries if name.startswith("workspace/demo-workspace/nodes/")
    )
    package_entries[node_path] = b"tampered"
    with zipfile.ZipFile(tampered_path, mode="w") as target_package:
        for name, content in package_entries.items():
            target_package.writestr(name, content)

    plan = build_import_plan(tampered_path)

    assert plan["can_import"] is False
    assert any("checksum mismatch" in error for error in plan["errors"])


def test_phase_6_emergency_readonly_reads_markdown_without_sqlite(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / ".rhine" / "vault.db", vault_root=tmp_path)
    node = _approve_manual_node(store)
    store.database_path.unlink()

    emergency = emergency_readonly_nodes(vault_root=tmp_path, workspace_id="demo-workspace")

    assert emergency["status"] == "read_only"
    assert emergency["sqlite_required"] is False
    assert emergency["nodes"][0]["node_id"] == node["node_id"]
    assert "verify checksums" in emergency["nodes"][0]["content"]


def test_phase_6_fastapi_recovery_endpoints(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / ".rhine" / "vault.db"))
    proposal = client.post(
        "/api/manual",
        json={
            "workspace_id": "demo-workspace",
            "title": "API recovery rule",
            "node_type": "Constraint",
            "content": "API recovery endpoints must not restore automatically.",
        },
    ).json()
    staged = client.post(
        f"/api/proposals/{proposal['proposal_id']}/stage",
        json={
            "workspace_id": "demo-workspace",
            "temporary_ids": [proposal["proposed_nodes"][0]["temporary_id"]],
        },
    ).json()
    client.post(
        "/api/staging/approve",
        json={"workspace_id": "demo-workspace", "entry_ids": [staged[0]["entry_id"]]},
    )

    health = client.get("/api/health").json()
    snapshot = client.post(
        "/api/recovery/snapshots/workspace",
        json={"workspace_id": "demo-workspace"},
    ).json()
    plan = client.post(
        "/api/recovery/import-plan",
        json={"package_path": snapshot["package_path"]},
    ).json()
    emergency = client.get("/api/recovery/emergency-readonly?workspace_id=demo-workspace").json()

    assert health["phase"] == "Phase 6"
    assert health["recovery"]["sqlite"]["status"] == "healthy"
    assert snapshot["kind"] == "rhine-workspace-snapshot"
    assert plan["can_import"] is True
    assert plan["applied"] is False
    assert emergency["node_count"] == 1


def test_phase_6_workflow_state_endpoint_collects_review_surfaces(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / ".rhine" / "vault.db"))
    proposal = client.post(
        "/api/manual",
        json={
            "workspace_id": "demo-workspace",
            "title": "Workflow state rule",
            "node_type": "Note",
            "content": "Workflow state should collect review surfaces for the WebUI.",
        },
    ).json()

    pending = client.get("/api/workflow/state?workspace_id=demo-workspace").json()
    staged = client.post(
        f"/api/proposals/{proposal['proposal_id']}/stage",
        json={
            "workspace_id": "demo-workspace",
            "temporary_ids": [proposal["proposed_nodes"][0]["temporary_id"]],
        },
    ).json()
    client.post(
        "/api/staging/approve",
        json={"workspace_id": "demo-workspace", "entry_ids": [staged[0]["entry_id"]]},
    )
    approved = client.get("/api/workflow/state?workspace_id=demo-workspace").json()

    assert pending["counts"]["proposals"] == 1
    assert pending["counts"]["pending_staging"] == 0
    assert approved["counts"]["nodes"] == 1
    assert approved["counts"]["changesets"] >= 1
    assert approved["nodes"][0]["title"] == "Workflow state rule"


def test_phase_6_webui_exposes_recovery_workflow_and_vector_backend_controls() -> None:
    webui = Path("src/rhine_vault/api/static/index.html").read_text(encoding="utf-8")

    for expected in (
        "show('workflow')",
        "show('nodes')",
        "show('recovery')",
        "/api/workflow/state",
        "/api/recovery/snapshots/workspace",
        "/api/recovery/import-plan",
        "/api/recovery/emergency-readonly",
        "/api/vector/backends",
        "loadVectorBackends",
        "toggleOutput",
    ):
        assert expected in webui
