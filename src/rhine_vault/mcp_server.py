"""Optional MCP SDK adapter for Rhine-Vault Phase 4."""

# mypy: disable-error-code=untyped-decorator

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any

from rhine_vault.capture.service import CaptureService
from rhine_vault.mcp_bridge import MCPBridge
from rhine_vault.runtime_paths import default_database_path
from rhine_vault.storage.sqlite import SQLiteStore


def create_mcp_server(database_path: Path | str | None = None) -> Any:
    """Create a FastMCP server when the optional MCP SDK is installed."""

    fastmcp_module = _load_fastmcp_module()
    db_path = Path(database_path) if database_path else _default_database_path()
    store = SQLiteStore(db_path)
    bridge = MCPBridge(store=store, capture=CaptureService(store))
    server = fastmcp_module.FastMCP("Rhine-Vault", json_response=True)

    @server.tool(name="list_workspaces")
    def list_workspaces(include_empty: bool = False) -> dict[str, Any]:
        return bridge.call_tool("list_workspaces", {"include_empty": include_empty})

    @server.tool(name="get_node")
    def get_node(workspace_id: str, node_id: str) -> dict[str, Any]:
        return bridge.call_tool("get_node", {"workspace_id": workspace_id, "node_id": node_id})

    @server.tool(name="search_nodes")
    def search_nodes(workspace_id: str, query: str, limit: int = 10) -> dict[str, Any]:
        return bridge.call_tool(
            "search_nodes",
            {"workspace_id": workspace_id, "query": query, "limit": limit},
        )

    @server.tool(name="get_local_graph")
    def get_local_graph(
        workspace_id: str,
        node_id: str | None = None,
        depth: int = 1,
        limit: int = 30,
    ) -> dict[str, Any]:
        return bridge.call_tool(
            "get_local_graph",
            {
                "workspace_id": workspace_id,
                "node_id": node_id,
                "depth": depth,
                "limit": limit,
            },
        )

    @server.tool(name="get_related_context")
    def get_related_context(
        workspace_id: str,
        query: str,
        profile_id: str | None = None,
        relation_depth: int | None = None,
        result_limit: int | None = None,
        include_deprecated: bool | None = None,
        node_type: str | None = None,
        authority: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        return bridge.call_tool(
            "get_related_context",
            {
                "workspace_id": workspace_id,
                "query": query,
                "profile_id": profile_id,
                "relation_depth": relation_depth,
                "result_limit": result_limit,
                "include_deprecated": include_deprecated,
                "node_type": node_type,
                "authority": authority,
                "tags": tags or [],
            },
        )

    @server.tool(name="submit_staging_node")
    def submit_staging_node(
        workspace_id: str,
        title: str,
        node_type: str,
        content: str,
        authority: str = "approved",
        tags: list[str] | None = None,
        relations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return bridge.call_tool(
            "submit_staging_node",
            {
                "workspace_id": workspace_id,
                "title": title,
                "node_type": node_type,
                "content": content,
                "authority": authority,
                "tags": tags or [],
                "relations": relations or [],
            },
        )

    @server.tool(name="revise_staging_node")
    def revise_staging_node(
        workspace_id: str,
        entry_id: str,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        return bridge.call_tool(
            "revise_staging_node",
            {"workspace_id": workspace_id, "entry_id": entry_id, "patch": patch},
        )

    @server.resource("rhine://workspace/{workspace_id}/node/{node_id}")
    def memory_node_resource(workspace_id: str, node_id: str) -> dict[str, Any]:
        return bridge.read_resource(f"rhine://workspace/{workspace_id}/node/{node_id}")

    @server.resource("rhine://workspace/{workspace_id}/graph/{node_id}")
    def local_graph_resource(workspace_id: str, node_id: str) -> dict[str, Any]:
        return bridge.read_resource(f"rhine://workspace/{workspace_id}/graph/{node_id}?depth=1")

    @server.resource("rhine://workspace/{workspace_id}/schema/memory-node")
    def memory_node_schema_resource(workspace_id: str) -> dict[str, Any]:
        return bridge.read_resource(f"rhine://workspace/{workspace_id}/schema/memory-node")

    return server


def create_streamable_http_app(database_path: Path | str | None = None) -> Any:
    server = create_mcp_server(database_path)
    return server.streamable_http_app()


def main() -> None:
    server = create_mcp_server(os.getenv("RHINE_VAULT_DB"))
    transport = os.getenv("RHINE_VAULT_MCP_TRANSPORT", "stdio")
    server.run(transport=transport)


def _load_fastmcp_module() -> Any:
    try:
        return importlib.import_module("mcp.server.fastmcp")
    except ImportError as exc:
        raise RuntimeError(
            "MCP support requires the optional extra: pip install 'rhine-vault[mcp]'"
        ) from exc


def _default_database_path() -> Path:
    return default_database_path()


if __name__ == "__main__":
    main()
