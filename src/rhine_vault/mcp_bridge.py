"""Transport-neutral MCP capability bridge for Phase 4."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

from rhine_vault.capture.service import CaptureService
from rhine_vault.retrieval import RetrievalOverrides, retrieve_context_bundle
from rhine_vault.storage.sqlite import SearchHit, SQLiteStore

ALLOWED_TOOL_NAMES = (
    "list_workspaces",
    "get_node",
    "search_nodes",
    "get_local_graph",
    "get_related_context",
    "submit_staging_node",
    "revise_staging_node",
)
FORBIDDEN_TOOL_NAMES = (
    "approve_staging_node",
    "write_formal_node",
    "delete_formal_node",
    "execute_raw_sql",
    "read_arbitrary_file",
    "publish_library",
    "git_commit",
)
RESOURCE_TEMPLATES = (
    "rhine://workspace/{workspace_id}/node/{node_id}",
    "rhine://workspace/{workspace_id}/graph/{node_id}?depth=1",
    "rhine://workspace/{workspace_id}/schema/memory-node",
)


@dataclass(frozen=True)
class MCPToolDefinition:
    name: str
    description: str
    write_scope: str
    input_schema: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "write_scope": self.write_scope,
            "input_schema": self.input_schema,
        }


class MCPBridge:
    """Expose approved Rhine-Vault operations without owning any transport."""

    def __init__(self, store: SQLiteStore, capture: CaptureService | None = None) -> None:
        self.store = store
        self.capture = capture or CaptureService(store)

    def capabilities(self) -> dict[str, Any]:
        return {
            "phase": "Phase 4",
            "transport_neutral": True,
            "tools": [tool.to_dict() for tool in tool_definitions()],
            "resources": list(RESOURCE_TEMPLATES),
            "forbidden_tools": list(FORBIDDEN_TOOL_NAMES),
            "approval_policy": (
                "Agents may read formal knowledge and submit or revise candidates, "
                "but cannot approve, publish, delete, execute raw SQL, or read arbitrary files."
            ),
        }

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        args = arguments or {}
        if name in FORBIDDEN_TOOL_NAMES:
            raise PermissionError(f"{name} is forbidden by the MCP capability contract")
        if name not in ALLOWED_TOOL_NAMES:
            raise KeyError(name)
        handlers = {
            "list_workspaces": self._list_workspaces,
            "get_node": self._get_node_tool,
            "search_nodes": self._search_nodes,
            "get_local_graph": self._get_local_graph,
            "get_related_context": self._get_related_context,
            "submit_staging_node": self._submit_staging_node,
            "revise_staging_node": self._revise_staging_node,
        }
        return handlers[name](args)

    def read_resource(self, uri: str) -> dict[str, Any]:
        parsed = urlparse(uri)
        if parsed.scheme != "rhine" or parsed.netloc != "workspace":
            raise ValueError("unsupported resource URI")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) == 3 and parts[1] == "node":
            return {
                "uri": uri,
                "kind": "memory-node",
                "content": self._find_node(workspace_id=parts[0], node_id=parts[2]),
            }
        if len(parts) == 3 and parts[1] == "graph":
            query = parse_qs(parsed.query)
            depth = _bounded_int(query.get("depth", ["1"])[0], default=1, minimum=0, maximum=1)
            return {
                "uri": uri,
                "kind": "local-graph",
                "content": self._local_graph_payload(
                    workspace_id=parts[0],
                    node_id=parts[2],
                    depth=depth,
                    limit=30,
                ),
            }
        if len(parts) == 3 and parts[1] == "schema" and parts[2] == "memory-node":
            return {"uri": uri, "kind": "schema", "content": memory_node_schema_resource()}
        raise ValueError("unsupported resource URI")

    def _list_workspaces(self, args: dict[str, Any]) -> dict[str, Any]:
        include_empty = bool(args.get("include_empty", False))
        workspaces = self.store.list_workspaces()
        if include_empty and not workspaces:
            workspaces = [
                {
                    "workspace_id": "demo-workspace",
                    "vault_root": str(self.store.vault_root),
                }
            ]
        return {"workspaces": workspaces}

    def _get_node_tool(self, args: dict[str, Any]) -> dict[str, Any]:
        workspace_id = _require_str(args, "workspace_id")
        node_id = _require_str(args, "node_id")
        return {"node": self._find_node(workspace_id=workspace_id, node_id=node_id)}

    def _search_nodes(self, args: dict[str, Any]) -> dict[str, Any]:
        workspace_id = _require_str(args, "workspace_id")
        query = _require_str(args, "query")
        limit = _bounded_int(args.get("limit"), default=10, minimum=1, maximum=30)
        hits = self.store.search(workspace_id=workspace_id, query=query, limit=limit)
        return {"hits": [_hit_to_dict(hit) for hit in hits]}

    def _get_local_graph(self, args: dict[str, Any]) -> dict[str, Any]:
        workspace_id = _require_str(args, "workspace_id")
        node_id = args.get("node_id")
        depth = _bounded_int(args.get("depth"), default=1, minimum=0, maximum=1)
        limit = _bounded_int(args.get("limit"), default=30, minimum=1, maximum=100)
        return self._local_graph_payload(
            workspace_id=workspace_id,
            node_id=str(node_id) if node_id else None,
            depth=depth,
            limit=limit,
        )

    def _get_related_context(self, args: dict[str, Any]) -> dict[str, Any]:
        workspace_id = _require_str(args, "workspace_id")
        query = _require_str(args, "query")
        overrides = RetrievalOverrides(
            profile_id=_optional_str(args, "profile_id"),
            relation_depth=_optional_int(args, "relation_depth"),
            result_limit=_optional_int(args, "result_limit"),
            include_deprecated=_optional_bool(args, "include_deprecated"),
            node_type=_optional_str(args, "node_type"),
            authority=_optional_str(args, "authority"),
            tags=_string_tuple(args.get("tags", ())),
        )
        return {
            "context_bundle": retrieve_context_bundle(
                store=self.store,
                workspace_id=workspace_id,
                query=query,
                profile_id=overrides.profile_id,
                overrides=overrides,
            ).to_dict()
        }

    def _submit_staging_node(self, args: dict[str, Any]) -> dict[str, Any]:
        workspace_id = _require_str(args, "workspace_id")
        title = _require_str(args, "title")
        node_type = _require_str(args, "node_type")
        content = _require_str(args, "content")
        proposal = self.capture.create_manual_proposal(
            workspace_id=workspace_id,
            title=title,
            node_type=node_type,
            content=content,
            authority=str(args.get("authority", "approved")),
            tags=_string_tuple(args.get("tags", ())),
            relations=tuple(args.get("relations", ())),
        )
        staging = self.store.save_staging(
            workspace_id=workspace_id,
            proposal_id=proposal["proposal_id"],
            temporary_ids=(proposal["proposed_nodes"][0]["temporary_id"],),
        )
        return {"proposal": proposal, "staging": staging}

    def _revise_staging_node(self, args: dict[str, Any]) -> dict[str, Any]:
        workspace_id = _require_str(args, "workspace_id")
        entry_id = _require_str(args, "entry_id")
        patch = args.get("patch")
        if not isinstance(patch, dict) or not patch:
            raise ValueError("patch must be a non-empty object")
        return {
            "staging_entry": self.store.update_staging_node(
                workspace_id=workspace_id,
                entry_id=entry_id,
                patch=patch,
            )
        }

    def _find_node(self, *, workspace_id: str, node_id: str) -> dict[str, Any]:
        for node in self.store.list_memory_nodes(workspace_id):
            if node["node_id"] == node_id:
                return node
        raise KeyError(node_id)

    def _local_graph_payload(
        self,
        *,
        workspace_id: str,
        node_id: str | None,
        depth: int,
        limit: int,
    ) -> dict[str, Any]:
        nodes = self.store.list_memory_nodes(workspace_id)
        node_by_id = {node["node_id"]: node for node in nodes}
        selected_ids = set(node_by_id if node_id is None else [node_id])
        if node_id is not None and node_id not in node_by_id:
            raise KeyError(node_id)
        edges = _graph_edges(nodes)
        if node_id is not None and depth > 0:
            for edge in edges:
                if edge["source"] == node_id:
                    selected_ids.add(edge["target"])
                if edge["target"] == node_id:
                    selected_ids.add(edge["source"])
        selected_ids = set(sorted(selected_ids)[:limit])
        return {
            "workspace_id": workspace_id,
            "center_node_id": node_id,
            "depth": depth,
            "nodes": [_node_summary(node_by_id[item]) for item in sorted(selected_ids)],
            "edges": [
                edge
                for edge in edges
                if edge["source"] in selected_ids and edge["target"] in selected_ids
            ],
        }


def tool_definitions() -> tuple[MCPToolDefinition, ...]:
    return (
        MCPToolDefinition(
            name="list_workspaces",
            description="List workspaces known to the local vault.",
            write_scope="read-only",
            input_schema={"type": "object", "properties": {"include_empty": {"type": "boolean"}}},
        ),
        MCPToolDefinition(
            name="get_node",
            description="Read one approved formal MemoryNode by workspace and node ID.",
            write_scope="read-only",
            input_schema=_schema_with_required("workspace_id", "node_id"),
        ),
        MCPToolDefinition(
            name="search_nodes",
            description="Search approved formal MemoryNodes with local SQLite retrieval.",
            write_scope="read-only",
            input_schema=_schema_with_required("workspace_id", "query"),
        ),
        MCPToolDefinition(
            name="get_local_graph",
            description="Read a bounded one-hop local relation graph.",
            write_scope="read-only",
            input_schema=_schema_with_required("workspace_id"),
        ),
        MCPToolDefinition(
            name="get_related_context",
            description="Build a Context Bundle from approved formal MemoryNodes.",
            write_scope="read-only",
            input_schema=_schema_with_required("workspace_id", "query"),
        ),
        MCPToolDefinition(
            name="submit_staging_node",
            description="Submit a candidate MemoryNode to staging for human review.",
            write_scope="candidate-only",
            input_schema=_schema_with_required("workspace_id", "title", "node_type", "content"),
        ),
        MCPToolDefinition(
            name="revise_staging_node",
            description="Revise a pending staging candidate before human approval.",
            write_scope="candidate-only",
            input_schema=_schema_with_required("workspace_id", "entry_id", "patch"),
        ),
    )


def memory_node_schema_resource() -> dict[str, Any]:
    return {
        "type": "object",
        "required": [
            "node_id",
            "workspace_id",
            "title",
            "node_type",
            "content",
            "authority",
            "status",
            "revision",
        ],
        "properties": {
            "node_id": {"type": "string"},
            "workspace_id": {"type": "string"},
            "title": {"type": "string"},
            "node_type": {"type": "string"},
            "content": {"type": "string"},
            "authority": {
                "type": "string",
                "enum": ["canonical", "approved", "reference", "historical", "experimental"],
            },
            "status": {
                "type": "string",
                "enum": ["active", "deprecated", "archived", "superseded"],
            },
            "tags": {"type": "array", "items": {"type": "string"}},
            "relations": {"type": "array", "items": {"type": "object"}},
            "source_refs": {"type": "array", "items": {"type": "object"}},
            "revision": {"type": "integer", "minimum": 1},
        },
    }


def _schema_with_required(*required: str) -> dict[str, Any]:
    return {
        "type": "object",
        "required": list(required),
        "properties": {name: {"type": "string"} for name in required},
    }


def _graph_edges(nodes: list[dict[str, Any]]) -> list[dict[str, str]]:
    edges = []
    node_ids = {node["node_id"] for node in nodes}
    for node in nodes:
        for relation in node.get("relations", []):
            target = str(relation.get("target", ""))
            if target in node_ids:
                edges.append(
                    {
                        "source": node["node_id"],
                        "target": target,
                        "type": str(relation.get("type", "")),
                        "description": str(relation.get("description", "")),
                    }
                )
    return edges


def _node_summary(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_id": node["node_id"],
        "workspace_id": node["workspace_id"],
        "title": node["title"],
        "node_type": node["node_type"],
        "authority": node["authority"],
        "status": node["status"],
        "revision": node["revision"],
    }


def _hit_to_dict(hit: SearchHit) -> dict[str, Any]:
    return {
        "node_id": hit.node_id,
        "workspace_id": hit.workspace_id,
        "title": hit.title,
        "node_type": hit.node_type,
        "content": hit.content,
        "authority": hit.authority,
        "status": hit.status,
        "tags": list(hit.tags),
        "relations": list(hit.relations),
        "source_refs": list(hit.source_refs),
        "revision": hit.revision,
        "score": hit.score,
    }


def _require_str(args: dict[str, Any], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value.strip()


def _optional_str(args: dict[str, Any], key: str) -> str | None:
    value = args.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _optional_int(args: dict[str, Any], key: str) -> int | None:
    value = args.get(key)
    if value is None:
        return None
    return _bounded_int(value, default=0, minimum=0, maximum=100)


def _optional_bool(args: dict[str, Any], key: str) -> bool | None:
    value = args.get(key)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def _bounded_int(value: object, *, default: int, minimum: int, maximum: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError("expected an integer")
    if isinstance(value, int):
        number = value
    elif isinstance(value, str):
        try:
            number = int(value)
        except ValueError as exc:
            raise ValueError("expected an integer") from exc
    else:
        raise ValueError("expected an integer")
    return min(max(number, minimum), maximum)


def _string_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list | tuple):
        return tuple(str(item) for item in value if str(item).strip())
    raise ValueError("expected a string list")
