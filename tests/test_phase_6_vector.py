from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from rhine_vault.api import create_app
from rhine_vault.capture.service import CaptureService
from rhine_vault.retrieval import RetrievalOverrides, retrieve_lab
from rhine_vault.storage.sqlite import SQLiteStore
from rhine_vault.vector import search_index_chunks
from rhine_vault.vector_backends import vector_backend_capabilities


def _approve_manual_node(
    store: SQLiteStore,
    *,
    title: str,
    content: str,
    workspace_id: str = "demo-workspace",
    tags: tuple[str, ...] = ("vector",),
) -> dict[str, object]:
    capture = CaptureService(store)
    proposal = capture.create_manual_proposal(
        workspace_id=workspace_id,
        title=title,
        node_type="Note",
        content=content,
        authority="approved",
        tags=tags,
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


def test_phase_6_hash_vector_search_uses_rebuildable_chunks(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / ".rhine" / "vault.db", vault_root=tmp_path)
    node = _approve_manual_node(
        store,
        title="NeoForge registry",
        content="DeferredRegister creates registry entries for NeoForge mods.",
    )
    _approve_manual_node(
        store,
        title="Persona sample",
        content="The character speaks softly and keeps short runtime memory.",
    )
    store.process_index_jobs("demo-workspace")

    result = search_index_chunks(
        chunks=store.list_index_chunks(workspace_id="demo-workspace"),
        workspace_id="demo-workspace",
        query="DeferredRegister registry entries",
    )

    assert result["provider_id"] == "hash-local-v1"
    assert result["source"] == "index_chunks"
    assert result["hits"][0]["node_id"] == node["node_id"]
    assert result["hits"][0]["score"] > 0


def test_phase_6_retrieval_lab_vector_channel_is_explicit(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / ".rhine" / "vault.db", vault_root=tmp_path)
    node = _approve_manual_node(
        store,
        title="Vector retrieval note",
        content="Vector retrieval is derived from approved chunk indexes.",
    )
    store.process_index_jobs("demo-workspace")

    disabled = retrieve_lab(
        store=store,
        workspace_id="demo-workspace",
        query="approved chunk indexes",
        overrides=RetrievalOverrides(profile_id="semantic-knowledge-base"),
    )
    enabled = retrieve_lab(
        store=store,
        workspace_id="demo-workspace",
        query="approved chunk indexes",
        overrides=RetrievalOverrides(
            profile_id="semantic-knowledge-base",
            enable_vector=True,
        ),
    )

    assert disabled["explain_trace"]["vector_channel"]["enabled"] is False
    assert enabled["explain_trace"]["vector_channel"]["enabled"] is True
    assert enabled["channel_candidates"]["vector"][0]["node_id"] == node["node_id"]
    assert "vector" in enabled["fused_ranking"][0]["channels"]


def test_phase_6_vector_backend_capabilities_do_not_activate_chroma() -> None:
    capabilities = vector_backend_capabilities()
    backends = {backend["backend_id"]: backend for backend in capabilities["backends"]}

    assert capabilities["active_backend"] == "local-hash"
    assert backends["local-hash"]["enabled"] is True
    assert backends["local-hash"]["formal_authority"] is False
    assert backends["chroma"]["enabled"] is False
    assert backends["chroma"]["production_ready"] is False
    assert "ChromaDB is evaluated" in " ".join(capabilities["constraints"])


def test_phase_6_fastapi_vector_search_and_retrieval_toggle(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / ".rhine" / "vault.db"))
    proposal = client.post(
        "/api/manual",
        json={
            "workspace_id": "demo-workspace",
            "title": "API vector note",
            "node_type": "Note",
            "content": "API vector search uses rebuildable chunk data.",
            "tags": ["vector"],
        },
    ).json()
    staged = client.post(
        f"/api/proposals/{proposal['proposal_id']}/stage",
        json={
            "workspace_id": "demo-workspace",
            "temporary_ids": [proposal["proposed_nodes"][0]["temporary_id"]],
        },
    ).json()
    approved = client.post(
        "/api/staging/approve",
        json={"workspace_id": "demo-workspace", "entry_ids": [staged[0]["entry_id"]]},
    ).json()[0]
    client.post("/api/index-jobs/process", json={"workspace_id": "demo-workspace"})

    vector = client.post(
        "/api/vector/search",
        json={
            "workspace_id": "demo-workspace",
            "query": "rebuildable chunk data",
            "result_limit": 5,
        },
    ).json()
    lab = client.post(
        "/api/retrieval/lab",
        json={
            "workspace_id": "demo-workspace",
            "query": "rebuildable chunk data",
            "profile_id": "semantic-knowledge-base",
            "enable_vector": True,
            "result_limit": 5,
        },
    ).json()

    assert vector["hits"][0]["node_id"] == approved["node_id"]
    assert lab["explain_trace"]["vector_channel"]["enabled"] is True
    assert lab["channel_candidates"]["vector"][0]["node_id"] == approved["node_id"]


def test_phase_6_fastapi_vector_backend_probe_is_read_only(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / ".rhine" / "vault.db"))

    response = client.get("/api/vector/backends")
    payload = response.json()
    backends = {backend["backend_id"]: backend for backend in payload["backends"]}

    assert response.status_code == 200
    assert payload["active_backend"] == "local-hash"
    assert backends["chroma"]["enabled"] is False


def test_phase_6_element_ui_exposes_full_management_surfaces() -> None:
    element_app = Path("ui/src/App.vue").read_text(encoding="utf-8")
    element_api = Path("ui/src/api.ts").read_text(encoding="utf-8")

    for activity in (
        "activity === 'capture'",
        "activity === 'nodes'",
        "activity === 'review'",
        "activity === 'recovery'",
    ):
        assert activity in element_app

    for action in (
        "openActivity",
        "perform",
        "submitManualProposal",
        "submitAndStageManualProposal",
        "captureChatAsProposal",
        "runStageProposal",
        "runApproveStaging",
        "refreshNodes",
        "selectNode",
        "runRollbackNode",
        "runCreateWorkspaceSnapshot",
        "runBuildImportPlan",
        "runEmergencyReadonly",
        "runVectorBackendProbe",
        "runStateCollapsed",
        "sidebarCollapsed",
        "vectorBackendState",
    ):
        assert action in element_app

    for api_helper in (
        "captureConversation",
        "createManualProposal",
        "listNodes",
        "approveStaging",
        "createWorkspaceSnapshot",
        "buildImportPlan",
        "emergencyReadonly",
        "vectorBackends",
    ):
        assert api_helper in element_api
