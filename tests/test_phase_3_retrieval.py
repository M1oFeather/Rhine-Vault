from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from rhine_vault.api import create_app
from rhine_vault.capture.service import CaptureService
from rhine_vault.retrieval import RetrievalOverrides, retrieve_context_bundle, retrieve_lab
from rhine_vault.storage.sqlite import SQLiteStore


def _approve_manual(
    store: SQLiteStore,
    capture: CaptureService,
    *,
    title: str,
    content: str,
    node_type: str = "Note",
    authority: str = "approved",
    tags: tuple[str, ...] = (),
    patch: dict[str, object] | None = None,
) -> dict[str, object]:
    proposal = capture.create_manual_proposal(
        workspace_id="demo-workspace",
        title=title,
        node_type=node_type,
        content=content,
        authority=authority,
        tags=tags,
    )
    if patch:
        proposal = store.update_proposed_node(
            workspace_id="demo-workspace",
            proposal_id=proposal["proposal_id"],
            temporary_id=proposal["proposed_nodes"][0]["temporary_id"],
            patch=patch,
        )
    staged = store.save_staging(
        workspace_id="demo-workspace",
        proposal_id=proposal["proposal_id"],
        temporary_ids=(proposal["proposed_nodes"][0]["temporary_id"],),
    )
    return store.approve_staging(
        workspace_id="demo-workspace",
        entry_ids=(staged[0]["entry_id"],),
    )[0]


def test_phase_3_retrieval_ranking_profile_and_explain_trace(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "vault.db")
    capture = CaptureService(store)
    support = _approve_manual(
        store,
        capture,
        title="Source reference layer",
        content="Reference material is kept in a supporting layer.",
    )
    rule = _approve_manual(
        store,
        capture,
        title="Approval rule",
        content="Agents must use approved MemoryNode sources.",
        node_type="Constraint",
        authority="canonical",
        tags=("approval",),
        patch={
            "relations": [
                {
                    "target": support["node_id"],
                    "type": "depends_on",
                    "description": "uses source policy",
                }
            ]
        },
    )

    lab = retrieve_lab(
        store=store,
        workspace_id="demo-workspace",
        query="Approval rule MemoryNode",
        overrides=RetrievalOverrides(profile_id="technical-documentation"),
    )
    bundle = retrieve_context_bundle(
        store=store,
        workspace_id="demo-workspace",
        query="Approval rule MemoryNode",
        overrides=RetrievalOverrides(profile_id="technical-documentation"),
    )

    assert lab["profile"]["profile_id"] == "technical-documentation"
    assert lab["channel_candidates"]["exact"]
    assert lab["channel_candidates"]["metadata"]
    assert lab["channel_candidates"]["fts"]
    assert lab["explain_trace"]["vector_channel"]["enabled"] is False
    assert lab["fused_ranking"][0]["node_id"] == rule["node_id"]
    assert lab["relation_expansion"][0]["node_id"] == support["node_id"]
    assert bundle.mandatory_constraints[0]["node_id"] == rule["node_id"]
    assert bundle.relevant_context[0]["node_id"] == support["node_id"]
    assert bundle.relevant_context[0]["source_channels"] == ["relation_expansion"]
    assert bundle.explain_trace["fused_ranking"][0]["channels"]["exact"]["rank"] == 1


def test_phase_3_retrieval_filtering_conflicts_and_relation_depth(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "vault.db")
    capture = CaptureService(store)
    rule = _approve_manual(
        store,
        capture,
        title="Conflict rule",
        content="Conflict rules must not be selected silently.",
        node_type="Constraint",
        authority="canonical",
    )
    conflicting = _approve_manual(
        store,
        capture,
        title="Conflicting rule",
        content="Conflict rules can disagree and require warning.",
        node_type="Constraint",
        patch={
            "relations": [
                {
                    "target": rule["node_id"],
                    "type": "conflicts_with",
                    "description": "unresolved conflict",
                }
            ]
        },
    )
    deprecated = _approve_manual(
        store,
        capture,
        title="Deprecated conflict note",
        content="Deprecated conflict note should be warning-only.",
        patch={"status": "deprecated"},
    )

    lab = retrieve_lab(
        store=store,
        workspace_id="demo-workspace",
        query="conflict rule deprecated",
        overrides=RetrievalOverrides(
            profile_id="technical-documentation",
            relation_depth=0,
        ),
    )

    assert lab["relation_expansion"] == []
    assert any(item["status"] == "deprecated" for item in lab["filtered"])
    assert any(item["reason"] == "blocked by conflict_strategy=block" for item in lab["filtered"])
    assert any("conflicts with" in warning for warning in lab["context_bundle"]["warnings"])
    selected_ids = {
        item["node_id"]
        for item in lab["context_bundle"]["mandatory_constraints"]
        + lab["context_bundle"]["relevant_context"]
    }
    assert len({rule["node_id"], conflicting["node_id"]} & selected_ids) == 1
    assert all(
        item["node_id"] != deprecated["node_id"]
        for item in lab["context_bundle"]["mandatory_constraints"]
        + lab["context_bundle"]["relevant_context"]
    )


def test_phase_3_fastapi_retrieval_lab_endpoint(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))
    proposal = client.post(
        "/api/manual",
        json={
            "workspace_id": "demo-workspace",
            "title": "API retrieval rule",
            "node_type": "Constraint",
            "content": "API retrieval must explain ranking.",
            "authority": "canonical",
            "tags": ["retrieval"],
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

    profiles = client.get("/api/retrieval/profiles?workspace_id=demo-workspace").json()
    lab = client.post(
        "/api/retrieval/lab",
        json={
            "workspace_id": "demo-workspace",
            "query": "retrieval ranking",
            "profile_id": "technical-documentation",
            "result_limit": 5,
        },
    ).json()

    assert profiles["default_profile_id"] == "technical-documentation"
    assert {profile["profile_id"] for profile in profiles["profiles"]} == {
        "technical-documentation",
        "worldbuilding",
        "semantic-knowledge-base",
    }
    assert lab["context_bundle"]["mandatory_constraints"][0]["title"] == "API retrieval rule"
    assert lab["explain_trace"]["profile_id"] == "technical-documentation"
    assert lab["fused_ranking"][0]["channels"]
