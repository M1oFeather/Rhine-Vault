from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from rhine_vault.api import create_app
from rhine_vault.capture.service import CaptureService
from rhine_vault.context import build_context_bundle
from rhine_vault.llm import FakeLLMProvider
from rhine_vault.storage.sqlite import SQLiteStore


def test_conversation_capture_to_fake_llm(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "vault.db")
    capture = CaptureService(store)
    proposal = capture.create_conversation_proposal(
        workspace_id="demo-workspace",
        session_id="s1",
        messages=[
            {
                "message_id": "m1",
                "role": "user",
                "content": "Agent can submit staging, but cannot approve formal knowledge.",
            },
            {
                "message_id": "m2",
                "role": "user",
                "content": "Obsidian changes must enter ExternalChange review.",
            },
        ],
    )

    assert len(proposal["proposed_nodes"]) >= 2
    assert proposal["proposed_relations"][0]["relation_type"] == "related_to"
    assert store.search(workspace_id="demo-workspace", query="Agent") == []

    first = proposal["proposed_nodes"][0]["temporary_id"]
    updated = store.update_proposed_node(
        workspace_id="demo-workspace",
        proposal_id=proposal["proposal_id"],
        temporary_id=first,
        patch={"title": "Agent must stay in staging"},
    )
    staged = store.save_staging(
        workspace_id="demo-workspace",
        proposal_id=proposal["proposal_id"],
        temporary_ids=tuple(node["temporary_id"] for node in updated["proposed_nodes"]),
    )
    approved = store.approve_staging(
        workspace_id="demo-workspace",
        entry_ids=tuple(entry["entry_id"] for entry in staged),
    )

    assert len(approved) == 2
    hits = store.search(workspace_id="demo-workspace", query="Agent staging")
    assert hits
    bundle = build_context_bundle(
        store=store,
        workspace_id="demo-workspace",
        question="What are the Agent architecture constraints?",
    )
    answer = FakeLLMProvider().answer(
        question="What are the Agent architecture constraints?",
        context_bundle=bundle,
    )
    assert answer["citations"]
    assert bundle.supporting_references[0]["session_id"] == "s1"


def test_document_import_approval_and_duplicate_hash(tmp_path: Path) -> None:
    document = tmp_path / "import.md"
    document.write_text(
        """# Alpha

Alpha keeps code atomic.

```python
print("alpha")
```

# Beta

- one
- two
""",
        encoding="utf-8",
    )
    store = SQLiteStore(tmp_path / "vault.db")
    capture = CaptureService(store)

    proposal = capture.create_document_proposal(
        workspace_id="demo-workspace",
        path=document,
    )
    duplicate = capture.create_document_proposal(
        workspace_id="demo-workspace",
        path=document,
    )

    assert len(proposal["proposed_nodes"]) == 2
    assert proposal["proposed_nodes"][0]["source_refs"][0]["line_range"] == [1, 7]
    assert proposal["source_ids"] != duplicate["source_ids"]
    assert duplicate["duplicate_of"] == proposal["source_ids"][0]
    assert (
        duplicate["proposed_nodes"][0]["source_refs"][0]["hash"]
        == (proposal["proposed_nodes"][0]["source_refs"][0]["hash"])
    )
    assert (
        proposal["proposed_nodes"][0]["source_refs"][0]["hash"]
        == (duplicate["proposed_nodes"][0]["source_refs"][0]["hash"])
    )

    staged = store.save_staging(
        workspace_id="demo-workspace",
        proposal_id=proposal["proposal_id"],
        temporary_ids=(proposal["proposed_nodes"][0]["temporary_id"],),
    )
    store.reject_proposal(
        workspace_id="demo-workspace",
        proposal_id=duplicate["proposal_id"],
    )
    store.approve_staging(
        workspace_id="demo-workspace",
        entry_ids=(staged[0]["entry_id"],),
    )

    assert store.search(workspace_id="demo-workspace", query="Alpha")
    assert not store.search(workspace_id="demo-workspace", query="Beta")


def test_project_scan_keeps_source_index_separate(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "README.md").write_text("# Demo\n\nArchitecture constraints.", encoding="utf-8")
    (project / "AGENTS.md").write_text("Agent must use staging.", encoding="utf-8")
    (project / "src" / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    (project / ".venv").mkdir()
    (project / ".venv" / "ignored.py").write_text("ignored", encoding="utf-8")

    store = SQLiteStore(tmp_path / "vault.db")
    capture = CaptureService(store)
    result = capture.scan_project(workspace_id="demo-workspace", root=project)

    assert "README.md" in result["file_tree"]
    assert ".venv/ignored.py" not in result["file_tree"]
    assert result["source_index"]
    assert not store.search(workspace_id="demo-workspace", query="Architecture")

    proposal = result["proposal"]
    staged = store.save_staging(
        workspace_id="demo-workspace",
        proposal_id=proposal["proposal_id"],
        temporary_ids=(proposal["proposed_nodes"][1]["temporary_id"],),
    )
    store.approve_staging(
        workspace_id="demo-workspace",
        entry_ids=(staged[0]["entry_id"],),
    )
    assert store.search(workspace_id="demo-workspace", query="workspace staging")


def test_fastapi_endpoints_and_ui(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))

    ui = client.get("/")
    assert ui.status_code == 200
    assert "Manual Node Editor" in ui.text

    proposal = client.post(
        "/api/manual",
        json={
            "workspace_id": "demo-workspace",
            "title": "Manual constraint",
            "node_type": "Constraint",
            "content": "Manual nodes must be reviewed before approval.",
            "authority": "canonical",
            "tags": ["manual"],
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
        json={
            "workspace_id": "demo-workspace",
            "entry_ids": [staged[0]["entry_id"]],
        },
    )

    search = client.post(
        "/api/search",
        json={"workspace_id": "demo-workspace", "query": "reviewed approval"},
    ).json()
    context = client.post(
        "/api/context",
        json={"workspace_id": "demo-workspace", "query": "manual approval"},
    ).json()
    llm = client.post(
        "/api/llm/fake",
        json={"workspace_id": "demo-workspace", "query": "manual approval"},
    ).json()

    assert search[0]["title"] == "Manual constraint"
    assert context["mandatory_constraints"]
    assert llm["citations"]
