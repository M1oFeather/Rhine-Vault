from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from rhine_vault.api import create_app


def _stage_and_approve(client: TestClient, proposal: dict[str, Any], workspace_id: str) -> None:
    temporary_ids = [node["temporary_id"] for node in proposal["proposed_nodes"]]
    staging = client.post(
        f"/api/proposals/{proposal['proposal_id']}/stage",
        json={"workspace_id": workspace_id, "temporary_ids": temporary_ids},
    ).json()
    entry_ids = [entry["entry_id"] for entry in staging]
    approved = client.post(
        "/api/staging/approve",
        json={"workspace_id": workspace_id, "entry_ids": entry_ids},
    ).json()
    assert len(approved) == len(temporary_ids)


def test_novel_artifact_endpoint_enters_review_workflow(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "vault.db"))

    proposal = client.post(
        "/api/novel/artifacts",
        json={
            "workspace_id": "novel-demo",
            "artifact_type": "character",
            "title": "Ptilopsis character card",
            "content": 'Ptilopsis speaks calmly and must not use "hot-blooded slogans".',
            "tags": ["Rhine", "Ptilopsis"],
            "fields": {"voice": "calm and direct", "relationships": ["Rhine Lab"]},
        },
    ).json()

    node = proposal["proposed_nodes"][0]
    assert proposal["status"] == "pending_review"
    assert node["node_type"] == "CharacterCard"
    assert node["authority"] == "reference"
    assert node["tags"][:2] == ["novel", "character"]
    assert "Structured Fields" in node["content"]


def test_novel_chapter_generation_uses_approved_context_and_can_save_draft(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(database_path=tmp_path / "vault.db"))
    workspace_id = "novel-demo"
    proposal = client.post(
        "/api/novel/artifacts",
        json={
            "workspace_id": workspace_id,
            "artifact_type": "worldbuilding",
            "title": "Rhine Lab audit rule",
            "content": "Setting: Rhine Lab records must be traceable.",
            "tags": ["Rhine"],
        },
    ).json()
    _stage_and_approve(client, proposal, workspace_id)

    generated = client.post(
        "/api/novel/chapter/generate",
        json={
            "workspace_id": workspace_id,
            "query": "Rhine Lab records traceable",
            "project_title": "Rhine Archive",
            "chapter_title": "Laboratory Night Shift",
            "chapter_number": 2,
            "outline": "Ptilopsis reviews anomaly logs and finds the next clue.",
            "pov_character": "Ptilopsis",
            "tone": "calm and restrained",
            "target_words": 900,
            "extra_constraints": ["Do not bypass review workflow"],
            "save_as_proposal": True,
        },
    ).json()

    assert generated["kind"] == "novel-chapter-draft"
    assert generated["citations"]
    assert "Rhine Lab audit rule" in generated["markdown"]
    assert generated["proposal"]["proposed_nodes"][0]["node_type"] == "ChapterDraft"


def test_novel_review_reports_consistency_and_foreshadowing(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "vault.db"))
    workspace_id = "novel-demo"
    proposal = client.post(
        "/api/novel/artifacts",
        json={
            "workspace_id": workspace_id,
            "artifact_type": "character",
            "title": "Ptilopsis character card",
            "content": 'Setting: Ptilopsis must not use "hot-blooded slogans".',
            "tags": ["Ptilopsis"],
        },
    ).json()
    _stage_and_approve(client, proposal, workspace_id)

    consistency = client.post(
        "/api/novel/consistency/check",
        json={
            "workspace_id": workspace_id,
            "query": "Ptilopsis character",
            "manuscript": "Ptilopsis shouted hot-blooded slogans. TODO",
            "strictness": "strict",
        },
    ).json()
    assert consistency["issue_count"] >= 2
    assert {issue["code"] for issue in consistency["issues"]} >= {
        "DRAFT_MARKER",
        "FORBIDDEN_TERM_PRESENT",
    }

    foreshadowing = client.post(
        "/api/novel/foreshadowing/review",
        json={
            "workspace_id": workspace_id,
            "query": "Ptilopsis clue",
            "manuscript": "The terminal flashed an anomaly mark. This clue is deliberate.",
            "planned_payoffs": ["The anomaly mark pays off in chapter three"],
        },
    ).json()
    assert foreshadowing["kind"] == "novel-foreshadowing-report"
    assert foreshadowing["cues"]
    assert foreshadowing["planned_payoffs"]


def test_chapter_reverse_extraction_can_create_staging(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "vault.db"))

    result = client.post(
        "/api/novel/chapter/extract",
        json={
            "workspace_id": "novel-demo",
            "chapter_title": "Laboratory Night Shift",
            "chapter_text": (
                "Setting: Ptilopsis promises to log every anomaly. "
                "Foreshadowing: the terminal shows a blue mark."
            ),
            "tags": ["Rhine"],
            "stage": True,
        },
    ).json()

    proposal_node = result["proposal"]["proposed_nodes"][0]
    assert proposal_node["node_type"] == "ChapterKnowledge"
    assert "Candidate Facts" in proposal_node["content"]
    assert result["staging"]
    assert result["staging"][0]["proposed_node"]["title"] == (
        "Laboratory Night Shift extracted knowledge"
    )
