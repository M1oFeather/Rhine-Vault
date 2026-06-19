from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rhine_vault.api import create_app
from rhine_vault.capture.service import CaptureService
from rhine_vault.mcp_bridge import FORBIDDEN_TOOL_NAMES, MCPBridge
from rhine_vault.mcp_server import create_mcp_server
from rhine_vault.storage.sqlite import SQLiteStore


def _approved_node(
    store: SQLiteStore,
    capture: CaptureService,
    *,
    title: str = "MCP approval rule",
    content: str = "MCP agents must only use approved formal nodes.",
    node_type: str = "Constraint",
) -> dict[str, object]:
    proposal = capture.create_manual_proposal(
        workspace_id="demo-workspace",
        title=title,
        node_type=node_type,
        content=content,
        authority="canonical",
        tags=("mcp",),
    )
    staged = store.save_staging(
        workspace_id="demo-workspace",
        proposal_id=proposal["proposal_id"],
        temporary_ids=(proposal["proposed_nodes"][0]["temporary_id"],),
    )
    return store.approve_staging(
        workspace_id="demo-workspace",
        entry_ids=(staged[0]["entry_id"],),
        actor_id="user:reviewer",
    )[0]


def test_phase_4_mcp_bridge_capabilities_and_read_tools(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "vault.db")
    capture = CaptureService(store)
    node = _approved_node(store, capture)
    bridge = MCPBridge(store=store, capture=capture)

    capabilities = bridge.capabilities()
    tool_names = {tool["name"] for tool in capabilities["tools"]}
    assert "search_nodes" in tool_names
    assert "submit_staging_node" in tool_names
    assert "approve_staging_node" not in tool_names
    assert set(FORBIDDEN_TOOL_NAMES).issubset(set(capabilities["forbidden_tools"]))

    workspaces = bridge.call_tool("list_workspaces", {})
    search = bridge.call_tool(
        "search_nodes",
        {"workspace_id": "demo-workspace", "query": "approved formal nodes"},
    )
    context = bridge.call_tool(
        "get_related_context",
        {"workspace_id": "demo-workspace", "query": "MCP approval"},
    )
    resource = bridge.read_resource(f"rhine://workspace/demo-workspace/node/{node['node_id']}")

    assert workspaces["workspaces"][0]["workspace_id"] == "demo-workspace"
    assert search["hits"][0]["node_id"] == node["node_id"]
    assert context["context_bundle"]["mandatory_constraints"][0]["node_id"] == node["node_id"]
    assert resource["content"]["title"] == "MCP approval rule"


def test_phase_4_mcp_candidate_writes_stop_before_approval(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "vault.db")
    bridge = MCPBridge(store=store)

    submitted = bridge.call_tool(
        "submit_staging_node",
        {
            "workspace_id": "demo-workspace",
            "title": "MCP pending note",
            "node_type": "Note",
            "content": "Original pending candidate.",
            "tags": ["mcp"],
        },
    )
    entry_id = submitted["staging"][0]["entry_id"]
    revised = bridge.call_tool(
        "revise_staging_node",
        {
            "workspace_id": "demo-workspace",
            "entry_id": entry_id,
            "patch": {"content": "Revised pending candidate."},
        },
    )

    assert revised["staging_entry"]["proposed_node"]["content"] == "Revised pending candidate."
    assert store.search(workspace_id="demo-workspace", query="Revised pending") == []
    with pytest.raises(PermissionError):
        bridge.call_tool(
            "approve_staging_node",
            {"workspace_id": "demo-workspace", "entry_id": entry_id},
        )


def test_phase_4_mcp_graph_and_resources_are_bounded(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "vault.db")
    capture = CaptureService(store)
    target = _approved_node(
        store,
        capture,
        title="MCP related context",
        content="Related context can appear through one-hop graph expansion.",
        node_type="Note",
    )
    source = _approved_node(
        store,
        capture,
        title="MCP graph root",
        content="Graph roots can reference related context.",
        node_type="Note",
    )
    proposal = capture.create_manual_proposal(
        workspace_id="demo-workspace",
        title="MCP graph linked root",
        node_type="Note",
        content="Linked graph root.",
        relations=(
            {
                "target": target["node_id"],
                "type": "references",
                "description": "bounded graph edge",
            },
        ),
    )
    staged = store.save_staging(
        workspace_id="demo-workspace",
        proposal_id=proposal["proposal_id"],
        temporary_ids=(proposal["proposed_nodes"][0]["temporary_id"],),
    )
    linked = store.approve_staging(
        workspace_id="demo-workspace",
        entry_ids=(staged[0]["entry_id"],),
    )[0]
    bridge = MCPBridge(store=store, capture=capture)

    graph = bridge.call_tool(
        "get_local_graph",
        {"workspace_id": "demo-workspace", "node_id": linked["node_id"], "depth": 3},
    )
    resource = bridge.read_resource(
        f"rhine://workspace/demo-workspace/graph/{linked['node_id']}?depth=1"
    )
    schema = bridge.read_resource("rhine://workspace/demo-workspace/schema/memory-node")

    assert graph["depth"] == 1
    assert {item["node_id"] for item in graph["nodes"]} == {
        linked["node_id"],
        target["node_id"],
    }
    assert resource["content"]["edges"][0]["target"] == target["node_id"]
    assert schema["content"]["required"]
    assert source["node_id"] not in {item["node_id"] for item in graph["nodes"]}


def test_phase_4_fastapi_mcp_endpoints(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / "api.db"))
    proposal = client.post(
        "/api/manual",
        json={
            "workspace_id": "demo-workspace",
            "title": "API MCP rule",
            "node_type": "Constraint",
            "content": "API MCP calls must keep approvals human controlled.",
            "authority": "canonical",
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

    capabilities = client.get("/api/mcp/capabilities").json()
    search = client.post(
        "/api/mcp/tools/search_nodes",
        json={"arguments": {"workspace_id": "demo-workspace", "query": "human controlled"}},
    ).json()
    forbidden = client.post(
        "/api/mcp/tools/approve_staging_node",
        json={"arguments": {"workspace_id": "demo-workspace"}},
    )
    unknown = client.post("/api/mcp/tools/execute_raw_sql", json={"arguments": {}})

    assert capabilities["phase"] == "Phase 4"
    assert capabilities["streamable_http"]["mount_path"] == "/mcp"
    assert search["hits"][0]["title"] == "API MCP rule"
    assert forbidden.status_code == 403
    assert unknown.status_code == 403


def test_phase_4_ui_surfaces_expose_mcp_capabilities() -> None:
    webui = Path("src/rhine_vault/api/static/index.html").read_text(encoding="utf-8")
    element_app = Path("ui/src/App.vue").read_text(encoding="utf-8")
    element_api = Path("ui/src/api.ts").read_text(encoding="utf-8")

    assert "show('mcp'); loadMcpCapabilities()" in webui
    assert "/api/mcp/capabilities" in webui
    assert "MCP 能力边界" in webui
    assert "type Activity" in element_app
    assert "activity === 'mcp'" in element_app
    assert "MCP 能力边界" in element_app
    assert "mcpCapabilities" in element_api
    assert "/api/mcp/tools/" in element_api


def test_phase_4_optional_mcp_sdk_is_lazy(tmp_path: Path) -> None:
    if importlib.util.find_spec("mcp") is None:
        with pytest.raises(RuntimeError, match="rhine-vault\\[mcp\\]"):
            create_mcp_server(tmp_path / "vault.db")
    else:
        assert create_mcp_server(tmp_path / "vault.db") is not None
