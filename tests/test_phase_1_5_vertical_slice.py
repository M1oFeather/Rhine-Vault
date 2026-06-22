from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from rhine_vault.api import create_app
from rhine_vault.capture.rules import stable_node_id
from rhine_vault.capture.service import CaptureService
from rhine_vault.context import ContextBundle, build_context_bundle
from rhine_vault.llm import FakeLLMProvider, OpenAICompatibleProvider
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


def test_chat_session_capture_persists_messages_and_creates_proposal(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "vault.db")
    capture = CaptureService(store)

    session = store.create_conversation_session(
        workspace_id="demo-workspace",
        title="Design chat",
    )
    first = store.add_conversation_message(
        workspace_id="demo-workspace",
        session_id=session["session_id"],
        role="user",
        content="Rhine-Vault needs chat-like knowledge capture.",
    )
    second = store.add_conversation_message(
        workspace_id="demo-workspace",
        session_id=session["session_id"],
        role="assistant",
        content="Captured chat must keep session and message range provenance.",
    )

    messages = store.list_conversation_messages(
        workspace_id="demo-workspace",
        session_id=session["session_id"],
    )
    proposal = capture.create_chat_session_proposal(
        workspace_id="demo-workspace",
        session_id=session["session_id"],
    )

    assert [message["ordinal"] for message in messages] == [1, 2]
    assert messages[0]["message_id"] == first["message_id"]
    assert messages[1]["message_id"] == second["message_id"]
    assert proposal["source_ids"]
    assert proposal["proposed_nodes"]
    assert proposal["proposed_nodes"][0]["source_refs"][0]["session_id"] == session["session_id"]
    assert (
        proposal["proposed_nodes"][0]["source_refs"][0]["message_range"]
        == f"{first['message_id']}..{second['message_id']}"
    )


def test_openai_compatible_provider_uses_standard_chat_completion_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {"choices": [{"message": {"content": "Use demo-workspace.node-1."}}]}
            ).encode("utf-8")

    def fake_urlopen(request: Any, timeout: int) -> FakeResponse:
        captured["timeout"] = timeout
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    bundle = ContextBundle(
        workspace_id="demo-workspace",
        question="What is approved?",
        mandatory_constraints=(
            {
                "node_id": "demo-workspace.node-1",
                "title": "Approved rule",
                "authority": "canonical",
                "content": "Only approved nodes are searchable.",
                "source_refs": [],
            },
        ),
        relevant_context=(),
        supporting_references=(),
        warnings=(),
    )

    result = OpenAICompatibleProvider(
        base_url="https://api.example.test/v1",
        api_key="test-key",
        model="test-model",
    ).answer(question="What is approved?", context_bundle=bundle)

    assert captured["url"] == "https://api.example.test/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["payload"]["model"] == "test-model"
    assert captured["payload"]["messages"][0]["role"] == "system"
    assert captured["payload"]["messages"][1]["role"] == "user"
    assert result["answer"] == "Use demo-workspace.node-1."
    assert result["citations"] == ["demo-workspace.node-1"]


def test_openai_compatible_provider_ping_uses_plain_chat_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"choices": [{"message": {"content": "你好, 我在线。"}}]}).encode(
                "utf-8"
            )

    def fake_urlopen(request: Any, timeout: int) -> FakeResponse:
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = OpenAICompatibleProvider(
        base_url="https://api.example.test",
        api_key="test-key",
        model="test-model",
    ).ping(message="你好")

    assert captured["url"] == "https://api.example.test/v1/chat/completions"
    assert captured["payload"]["messages"][1] == {"role": "user", "content": "你好"}
    assert "context_bundle" not in json.dumps(captured["payload"], ensure_ascii=False)
    assert result["mode"] == "ping"
    assert result["answer"] == "你好, 我在线。"


def test_openai_compatible_provider_chat_extracts_reasoning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "reasoning_content": "先识别用户意图。",
                                "content": "你好, 我可以继续聊。",
                            }
                        }
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(request: Any, timeout: int) -> FakeResponse:
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = OpenAICompatibleProvider(
        base_url="https://api.example.test",
        api_key="test-key",
        model="test-model",
    ).chat(
        messages=[{"role": "user", "content": "你好"}],
        thinking_enabled=True,
        reasoning_effort="high",
    )

    assert captured["url"] == "https://api.example.test/v1/chat/completions"
    assert captured["payload"]["messages"] == [{"role": "user", "content": "你好"}]
    assert captured["payload"]["thinking"] == {"type": "enabled"}
    assert captured["payload"]["reasoning_effort"] == "high"
    assert result["mode"] == "chat"
    assert result["answer"] == "你好, 我可以继续聊。"
    assert result["reasoning"] == "先识别用户意图。"


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
        == proposal["proposed_nodes"][0]["source_refs"][0]["hash"]
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


def test_manual_titles_are_required_and_non_ascii_ids_are_stable(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))
    empty = client.post(
        "/api/manual",
        json={
            "workspace_id": "demo-workspace",
            "title": "   ",
            "node_type": "Constraint",
            "content": "No title should not create an untitled node.",
        },
    )

    assert empty.status_code == 422

    node_id = stable_node_id("demo-workspace", "审批规则")
    assert node_id.startswith("demo-workspace.node-")
    assert node_id == stable_node_id("demo-workspace", "审批规则")
    assert not node_id.endswith("untitled")


def test_phase_2_formal_approval_records_revision_audit_and_index_job(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / ".rhine" / "vault.db", vault_root=tmp_path)
    capture = CaptureService(store)
    proposal = capture.create_manual_proposal(
        workspace_id="demo-workspace",
        title="Formal approval",
        node_type="Constraint",
        content="Approval must create workflow records.",
    )
    staged = store.save_staging(
        workspace_id="demo-workspace",
        proposal_id=proposal["proposal_id"],
        temporary_ids=(proposal["proposed_nodes"][0]["temporary_id"],),
    )

    assert staged[0]["validation"] == []
    assert staged[0]["diff"]["change_type"] == "create"

    approved = store.approve_staging(
        workspace_id="demo-workspace",
        entry_ids=(staged[0]["entry_id"],),
        actor_id="user:reviewer",
    )

    node_id = approved[0]["node_id"]
    changesets = store.list_changesets("demo-workspace")
    revisions = store.list_node_revisions(workspace_id="demo-workspace", node_id=node_id)
    audit_events = store.list_audit_events("demo-workspace")
    index_jobs = store.list_index_jobs("demo-workspace")
    markdown_path = tmp_path / "data" / "workspaces" / "demo-workspace" / "nodes"

    assert changesets[0]["status"] == "applied"
    assert changesets[0]["diff"]["change_type"] == "create"
    assert changesets[0]["git_status"] == "skipped"
    assert revisions[0]["revision"] == 1
    assert revisions[0]["created_by"] == "user:reviewer"
    assert any(event["action"] == "staging.approve" for event in audit_events)
    assert any(event["action"] == "git.commit" for event in audit_events)
    assert index_jobs[0]["operation"] == "upsert"
    node_markdown = next(markdown_path.glob("*.md"))
    assert node_markdown.read_text(encoding="utf-8").startswith("---")

    node_markdown.write_text(
        node_markdown.read_text(encoding="utf-8") + "\nExternal edit not approved.\n",
        encoding="utf-8",
    )
    external_changes = store.detect_external_changes("demo-workspace")

    assert external_changes[0]["status"] == "detected"
    assert external_changes[0]["node_id"] == node_id
    assert external_changes[0]["diff"]["change_type"] == "external_update"
    assert not store.search(workspace_id="demo-workspace", query="External edit")


def test_phase_2_base_revision_conflict_is_blocked(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "vault.db")
    capture = CaptureService(store)
    first = capture.create_manual_proposal(
        workspace_id="demo-workspace",
        title="Conflict target",
        node_type="Constraint",
        content="Initial content.",
    )
    staged_first = store.save_staging(
        workspace_id="demo-workspace",
        proposal_id=first["proposal_id"],
        temporary_ids=(first["proposed_nodes"][0]["temporary_id"],),
    )
    second = capture.create_manual_proposal(
        workspace_id="demo-workspace",
        title="Conflict target",
        node_type="Constraint",
        content="Concurrent content.",
    )
    staged_second = store.save_staging(
        workspace_id="demo-workspace",
        proposal_id=second["proposal_id"],
        temporary_ids=(second["proposed_nodes"][0]["temporary_id"],),
    )

    store.approve_staging(
        workspace_id="demo-workspace",
        entry_ids=(staged_first[0]["entry_id"],),
    )

    with pytest.raises(ValueError, match="REVISION_CONFLICT"):
        store.approve_staging(
            workspace_id="demo-workspace",
            entry_ids=(staged_second[0]["entry_id"],),
        )


def test_phase_2_rollback_creates_new_revision(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / ".rhine" / "vault.db", vault_root=tmp_path)
    capture = CaptureService(store)
    first = capture.create_manual_proposal(
        workspace_id="demo-workspace",
        title="Rollback target",
        node_type="Constraint",
        content="Revision one.",
    )
    staged_first = store.save_staging(
        workspace_id="demo-workspace",
        proposal_id=first["proposal_id"],
        temporary_ids=(first["proposed_nodes"][0]["temporary_id"],),
    )
    approved_first = store.approve_staging(
        workspace_id="demo-workspace",
        entry_ids=(staged_first[0]["entry_id"],),
    )
    second = capture.create_manual_proposal(
        workspace_id="demo-workspace",
        title="Rollback target",
        node_type="Constraint",
        content="Revision two.",
    )
    staged_second = store.save_staging(
        workspace_id="demo-workspace",
        proposal_id=second["proposal_id"],
        temporary_ids=(second["proposed_nodes"][0]["temporary_id"],),
    )
    store.approve_staging(
        workspace_id="demo-workspace",
        entry_ids=(staged_second[0]["entry_id"],),
    )

    rolled_back = store.rollback_node(
        workspace_id="demo-workspace",
        node_id=approved_first[0]["node_id"],
        revision=1,
        actor_id="user:reviewer",
    )

    revisions = store.list_node_revisions(
        workspace_id="demo-workspace",
        node_id=approved_first[0]["node_id"],
    )
    changesets = store.list_changesets("demo-workspace")
    audit_events = store.list_audit_events("demo-workspace")

    assert rolled_back["revision"] == 3
    assert rolled_back["content"] == "Revision one."
    assert [revision["revision"] for revision in revisions] == [1, 2, 3]
    assert changesets[-1]["diff"]["change_type"] == "rollback"
    assert changesets[-1]["diff"]["restored_from_revision"] == 1
    assert any(event["action"] == "node.rollback" for event in audit_events)


def test_phase_2_external_change_review_approve_and_reject(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / ".rhine" / "vault.db", vault_root=tmp_path)
    capture = CaptureService(store)
    proposal = capture.create_manual_proposal(
        workspace_id="demo-workspace",
        title="External target",
        node_type="Constraint",
        content="Approved content.",
    )
    staged = store.save_staging(
        workspace_id="demo-workspace",
        proposal_id=proposal["proposal_id"],
        temporary_ids=(proposal["proposed_nodes"][0]["temporary_id"],),
    )
    approved = store.approve_staging(
        workspace_id="demo-workspace",
        entry_ids=(staged[0]["entry_id"],),
    )
    node_id = approved[0]["node_id"]
    markdown_path = next(
        (tmp_path / "data" / "workspaces" / "demo-workspace" / "nodes").glob("*.md")
    )

    markdown_path.write_text(
        markdown_path.read_text(encoding="utf-8").replace(
            "Approved content.",
            "Externally approved content.",
        ),
        encoding="utf-8",
    )
    detected = store.detect_external_changes("demo-workspace")
    external = store.approve_external_change(
        workspace_id="demo-workspace",
        change_id=detected[0]["change_id"],
        actor_id="user:reviewer",
    )

    revisions = store.list_node_revisions(workspace_id="demo-workspace", node_id=node_id)
    changesets = store.list_changesets("demo-workspace")
    audit_events = store.list_audit_events("demo-workspace")
    index_jobs = store.list_index_jobs("demo-workspace")

    assert external["revision"] == 2
    assert external["content"] == "Externally approved content."
    assert revisions[-1]["revision"] == 2
    assert revisions[-1]["base_revision"] == 1
    assert changesets[-1]["diff"]["external_change_id"] == detected[0]["change_id"]
    assert store.list_external_changes("demo-workspace")[0]["status"] == "approved"
    assert store.search(workspace_id="demo-workspace", query="Externally approved")
    assert index_jobs[-1]["revision"] == 2
    assert any(event["action"] == "external_change.approve" for event in audit_events)

    markdown_path.write_text(
        markdown_path.read_text(encoding="utf-8").replace(
            "Externally approved content.",
            "RejectedOnlyToken content.",
        ),
        encoding="utf-8",
    )
    rejected_change = store.detect_external_changes("demo-workspace")[-1]
    rejected = store.reject_external_change(
        workspace_id="demo-workspace",
        change_id=rejected_change["change_id"],
        actor_id="user:reviewer",
    )

    assert rejected["status"] == "rejected"
    assert "RejectedOnlyToken content." not in markdown_path.read_text(encoding="utf-8")
    assert not store.search(workspace_id="demo-workspace", query="RejectedOnlyToken")
    assert any(
        event["action"] == "external_change.reject"
        for event in store.list_audit_events("demo-workspace")
    )


def test_fastapi_conversation_session_flow(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))

    session = client.post(
        "/api/conversation-sessions",
        json={"workspace_id": "demo-workspace", "title": "UI chat"},
    ).json()
    message = client.post(
        f"/api/conversation-sessions/{session['session_id']}/messages",
        json={
            "workspace_id": "demo-workspace",
            "role": "user",
            "content": "Chat capture is core.",
        },
    ).json()
    messages = client.get(
        f"/api/conversation-sessions/{session['session_id']}/messages?workspace_id=demo-workspace"
    ).json()
    proposal = client.post(
        f"/api/conversation-sessions/{session['session_id']}/capture",
        json={"workspace_id": "demo-workspace"},
    ).json()

    assert message["ordinal"] == 1
    assert messages[0]["content"] == "Chat capture is core."
    assert proposal["source_ids"]
    assert proposal["proposed_nodes"][0]["source_refs"][0]["session_id"] == session["session_id"]


def test_fastapi_openai_compatible_llm_uses_request_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"choices": [{"message": {"content": "Configured answer"}}]}).encode(
                "utf-8"
            )

    def fake_urlopen(request: Any, timeout: int) -> FakeResponse:
        captured["timeout"] = timeout
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = TestClient(create_app(tmp_path / "api.db"))

    status = client.get("/api/llm/openai-compatible/status").json()
    answer = client.post(
        "/api/llm/openai-compatible",
        json={
            "workspace_id": "demo-workspace",
            "query": "manual approval",
            "base_url": "https://api.example.test",
            "api_key": "request-key",
            "model": "request-model",
        },
    ).json()

    assert status["base_url"] == "https://api.openai.com/v1"
    assert status["api_key_configured"] is False
    assert captured["url"] == "https://api.example.test/v1/chat/completions"
    assert captured["payload"]["model"] == "request-model"
    assert answer["provider"] == "openai-compatible"
    assert answer["model"] == "request-model"
    assert answer["answer"] == "Configured answer"


def test_fastapi_openai_compatible_ping_uses_request_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"choices": [{"message": {"content": "pong"}}]}).encode("utf-8")

    def fake_urlopen(request: Any, timeout: int) -> FakeResponse:
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = TestClient(create_app(tmp_path / "api.db"))

    answer = client.post(
        "/api/llm/openai-compatible/ping",
        json={
            "base_url": "https://api.example.test",
            "api_key": "request-key",
            "model": "request-model",
            "message": "你好",
        },
    ).json()

    assert captured["url"] == "https://api.example.test/v1/chat/completions"
    assert captured["payload"]["model"] == "request-model"
    assert captured["payload"]["messages"][1] == {"role": "user", "content": "你好"}
    assert answer["mode"] == "ping"
    assert answer["answer"] == "pong"


def test_fastapi_openai_compatible_chat_uses_request_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "reasoning_content": "Think briefly.",
                                "content": "chat pong",
                            }
                        }
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(request: Any, timeout: int) -> FakeResponse:
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = TestClient(create_app(tmp_path / "api.db"))

    answer = client.post(
        "/api/llm/openai-compatible/chat",
        json={
            "workspace_id": "demo-workspace",
            "base_url": "https://api.example.test",
            "api_key": "request-key",
            "model": "request-model",
            "messages": [{"role": "user", "content": "你好"}],
            "thinking_enabled": True,
            "reasoning_effort": "high",
        },
    ).json()

    assert captured["url"] == "https://api.example.test/v1/chat/completions"
    assert captured["payload"]["model"] == "request-model"
    assert captured["payload"]["messages"] == [{"role": "user", "content": "你好"}]
    assert captured["payload"]["thinking"] == {"type": "enabled"}
    assert captured["payload"]["reasoning_effort"] == "high"
    assert answer["mode"] == "chat"
    assert answer["answer"] == "chat pong"
    assert answer["reasoning"] == "Think briefly."


def test_openai_compatible_provider_rejects_invalid_base_urls() -> None:
    with pytest.raises(RuntimeError, match="http"):
        _ = OpenAICompatibleProvider(
            base_url="file:///tmp/provider.sock",
            api_key="test-key",
            model="test-model",
        ).chat_completions_url

    with pytest.raises(RuntimeError, match="credentials"):
        _ = OpenAICompatibleProvider(
            base_url="https://user:secret@api.example.test",
            api_key="test-key",
            model="test-model",
        ).chat_completions_url


def test_fastapi_external_change_review_flow(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))
    proposal = client.post(
        "/api/manual",
        json={
            "workspace_id": "demo-workspace",
            "title": "API external target",
            "node_type": "Constraint",
            "content": "API approved content.",
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
    markdown_path = next(
        (tmp_path / "data" / "workspaces" / "demo-workspace" / "nodes").glob("*.md")
    )
    markdown_path.write_text(
        markdown_path.read_text(encoding="utf-8").replace(
            "API approved content.",
            "API external approved content.",
        ),
        encoding="utf-8",
    )

    detected = client.post(
        "/api/external-changes/detect",
        json={"workspace_id": "demo-workspace"},
    ).json()
    approved = client.post(
        f"/api/external-changes/{detected[0]['change_id']}/approve",
        json={"workspace_id": "demo-workspace", "actor_id": "user:reviewer"},
    ).json()
    changes = client.get("/api/external-changes?workspace_id=demo-workspace").json()
    revisions = client.get(
        f"/api/nodes/{approved['node_id']}/revisions?workspace_id=demo-workspace"
    ).json()

    assert approved["content"] == "API external approved content."
    assert changes[0]["status"] == "approved"
    assert revisions[-1]["revision"] == 2


def test_fastapi_restricts_local_path_imports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    outside_doc = tmp_path / "outside.md"
    outside_doc.write_text("# Allowed when configured\n\nDocument body.", encoding="utf-8")
    outside_project = tmp_path / "outside-project"
    outside_project.mkdir()
    (outside_project / "README.md").write_text("# Project\n\nBody.", encoding="utf-8")

    client = TestClient(create_app(vault_root / "api.db"))

    rejected_doc = client.post(
        "/api/documents/import",
        json={"workspace_id": "demo-workspace", "path": str(outside_doc)},
    )
    rejected_project = client.post(
        "/api/projects/scan",
        json={"workspace_id": "demo-workspace", "root": str(outside_project)},
    )

    assert rejected_doc.status_code == 400
    assert rejected_project.status_code == 400
    assert "outside allowed import roots" in rejected_doc.json()["detail"]

    monkeypatch.setenv("RHINE_VAULT_IMPORT_ROOTS", str(tmp_path))
    accepted_doc = client.post(
        "/api/documents/import",
        json={"workspace_id": "demo-workspace", "path": str(outside_doc)},
    )
    accepted_project = client.post(
        "/api/projects/scan",
        json={"workspace_id": "demo-workspace", "root": str(outside_project)},
    )

    assert accepted_doc.status_code == 200
    assert accepted_project.status_code == 200
    assert accepted_project.json()["file_tree"] == ["README.md"]


def test_fastapi_endpoints_and_api_docs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RHINE_VAULT_API_DOCS_ONLY", "1")
    monkeypatch.delenv("RHINE_VAULT_UI_DIST", raising=False)
    client = TestClient(create_app(tmp_path / "api.db"))

    index = client.get("/")
    webui = client.get("/webui")
    docs = client.get("/docs")
    openapi = client.get("/openapi.json")

    assert index.status_code == 200
    assert 'href="/docs"' in index.text
    assert 'href="/redoc"' in index.text
    assert webui.status_code == 200
    assert "Rhine-Vault" in webui.text
    assert "data-i18n" in webui.text
    assert "/api/manual" in webui.text
    assert "/api/retrieval/lab" in webui.text
    assert 'id="retrieval-profile-select"' in webui.text
    assert docs.status_code == 200
    assert openapi.status_code == 200
    assert "/api/retrieval/lab" in openapi.text

    zh_catalog = client.get("/api/i18n").json()
    en_catalog = client.get("/api/i18n?locale=en-US").json()
    fallback_catalog = client.get("/api/i18n?locale=fr").json()
    assert zh_catalog["locale"] == "zh"
    assert zh_catalog["messages"]["app.title"] == "Rhine-Vault Phase 6"
    assert zh_catalog["messages"]["manual.title"] == "手动节点编辑"
    assert zh_catalog["messages"]["search.title"] == "Retrieval Lab"
    assert zh_catalog["messages"]["retrieval.run"] == "运行 Retrieval Lab"
    assert zh_catalog["messages"]["conversation.send"] == "发送"
    assert zh_catalog["messages"]["conversation.ask_model"] == "发送并让模型回复"
    assert zh_catalog["messages"]["conversation.pause"] == "暂停当前"
    assert zh_catalog["messages"]["conversation.thinking"] == "思考模式"
    assert zh_catalog["messages"]["nav.conversation_capture"] == "勾选对话内容"
    assert zh_catalog["messages"]["settings.title"] == "运行设置"
    assert zh_catalog["messages"]["settings.test"] == "测试设置"
    assert zh_catalog["messages"]["settings.add_model"] == "添加模型"
    assert zh_catalog["messages"]["settings.model_editor"] == "模型配置"
    assert zh_catalog["messages"]["nav.mcp"] == "MCP 能力"
    assert zh_catalog["messages"]["mcp.title"] == "MCP 能力边界"
    assert zh_catalog["messages"]["workflow.title"] == "正式工作流状态"
    assert zh_catalog["messages"]["workflow.external.approve"] == "批准外部变更"
    assert zh_catalog["messages"]["workflow.validation.ok"] == "通过"
    assert zh_catalog["messages"]["workflow.empty"] == "暂无记录"
    assert zh_catalog["messages"]["output.title"] == "运行状态"
    assert zh_catalog["messages"]["llm.provider.openai"] == "OpenAI"
    assert zh_catalog["messages"]["llm.provider.deepseek"] == "DeepSeek"
    assert zh_catalog["messages"]["llm.model_config.default_deepseek_flash"] == (
        "DeepSeek V4 Flash"
    )
    assert zh_catalog["messages"]["llm.model_config.default_deepseek_pro"] == "DeepSeek V4 Pro"
    assert zh_catalog["messages"]["llm.thinking.enabled"] == "启用思考"
    assert zh_catalog["messages"]["output.toggle"] == "折叠或展开运行状态"
    assert "环境变量状态" in zh_catalog["messages"]["llm.status.note"]
    assert "不是真实大模型" in zh_catalog["messages"]["llm.fake.description"]
    assert en_catalog["locale"] == "en"
    assert en_catalog["messages"]["manual.title"] == "Manual Node Editor"
    assert en_catalog["messages"]["search.title"] == "Retrieval Lab"
    assert en_catalog["messages"]["retrieval.run"] == "Run Retrieval Lab"
    assert en_catalog["messages"]["settings.title"] == "Runtime Settings"
    assert en_catalog["messages"]["nav.mcp"] == "MCP Capabilities"
    assert en_catalog["messages"]["nav.recovery"] == "Recovery and Migration"
    assert en_catalog["messages"]["mcp.title"] == "MCP Capability Boundary"
    assert en_catalog["messages"]["vector.backends"] == "Evaluate Vector Backends"
    assert en_catalog["messages"]["recovery.import_plan.build"] == "Validate Import Plan"
    assert en_catalog["messages"]["llm.provider.openai"] == "OpenAI"
    assert en_catalog["messages"]["llm.provider.deepseek"] == "DeepSeek"
    assert fallback_catalog["locale"] == "zh"
    zh_node_types = client.get("/api/node-types").json()
    en_node_types = client.get("/api/node-types?locale=en").json()
    assert zh_node_types["extension_policy"]["mode"] == "approval_required"
    assert zh_node_types["node_types"][1]["id"] == "Constraint"
    assert zh_node_types["node_types"][1]["display_name"]
    assert en_node_types["node_types"][1]["display_name"] == "Constraint"

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
    staging = client.get("/api/staging?workspace_id=demo-workspace").json()
    assert staging[0]["entry_id"] == staged[0]["entry_id"]
    assert staging[0]["proposed_node"]["title"] == "Manual constraint"
    client.post(
        "/api/staging/approve",
        json={
            "workspace_id": "demo-workspace",
            "entry_ids": [staged[0]["entry_id"]],
            "actor_id": "user:reviewer",
        },
    )
    nodes = client.get("/api/nodes?workspace_id=demo-workspace").json()
    assert nodes[0]["title"] == "Manual constraint"
    assert nodes[0]["node_type"] == "Constraint"
    changesets = client.get("/api/changesets?workspace_id=demo-workspace").json()
    audit_events = client.get("/api/audit-events?workspace_id=demo-workspace").json()
    index_jobs = client.get("/api/index-jobs?workspace_id=demo-workspace").json()
    external_changes = client.get("/api/external-changes?workspace_id=demo-workspace").json()
    revisions = client.get(
        f"/api/nodes/{nodes[0]['node_id']}/revisions?workspace_id=demo-workspace"
    ).json()
    assert changesets[0]["status"] == "applied"
    assert audit_events
    assert index_jobs[0]["status"] == "queued"
    assert external_changes == []
    assert revisions[0]["revision"] == 1

    search = client.post(
        "/api/search",
        json={"workspace_id": "demo-workspace", "query": "reviewed approval"},
    ).json()
    context = client.post(
        "/api/context",
        json={"workspace_id": "demo-workspace", "query": "manual approval"},
    ).json()
    bot_context = client.post(
        "/api/integrations/bot/context",
        json={"workspace_id": "demo-workspace", "query": "manual approval"},
    ).json()
    generated_doc = client.post(
        "/api/documents/generate",
        json={
            "workspace_id": "demo-workspace",
            "query": "manual approval",
            "title": "Manual Approval Brief",
            "audience": "developer",
        },
    ).json()
    llm = client.post(
        "/api/llm/fake",
        json={"workspace_id": "demo-workspace", "query": "manual approval"},
    ).json()

    assert search[0]["title"] == "Manual constraint"
    assert context["mandatory_constraints"]
    assert bot_context["integration"] == "bot-adapter"
    assert bot_context["adapter_hints"]["runtime_owner"] == "external-bot-framework"
    assert bot_context["citations"] == [nodes[0]["node_id"]]
    assert generated_doc["kind"] == "knowledge-document"
    assert generated_doc["title"] == "Manual Approval Brief"
    assert "Manual nodes must be reviewed before approval." in generated_doc["markdown"]
    assert f"`{nodes[0]['node_id']}`" in generated_doc["markdown"]
    assert llm["citations"]
