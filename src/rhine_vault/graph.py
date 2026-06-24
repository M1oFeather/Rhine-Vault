"""Formal knowledge graph projection helpers."""

from __future__ import annotations

from collections import deque
from typing import Any


def local_graph_payload(
    *,
    nodes: list[dict[str, Any]],
    workspace_id: str,
    node_id: str | None = None,
    depth: int = 1,
    limit: int = 100,
) -> dict[str, Any]:
    node_by_id = {str(node["node_id"]): node for node in nodes}
    if node_id is not None and node_id not in node_by_id:
        raise KeyError(node_id)
    edges = graph_edges(nodes)
    selected_ids = _selected_node_ids(
        all_ids=set(node_by_id),
        edges=edges,
        center=node_id,
        depth=max(depth, 0),
        limit=max(limit, 1),
    )
    return {
        "workspace_id": workspace_id,
        "center_node_id": node_id,
        "depth": depth,
        "limit": limit,
        "nodes": [node_summary(node_by_id[item]) for item in sorted(selected_ids)],
        "edges": [
            edge
            for edge in edges
            if edge["source"] in selected_ids and edge["target"] in selected_ids
        ],
    }


def graph_edges(nodes: list[dict[str, Any]]) -> list[dict[str, str]]:
    edges: list[dict[str, str]] = []
    node_ids = {str(node["node_id"]) for node in nodes}
    for node in nodes:
        source = str(node["node_id"])
        for relation in node.get("relations", []):
            if not isinstance(relation, dict):
                continue
            target = str(relation.get("target", ""))
            if target in node_ids:
                edges.append(
                    {
                        "source": source,
                        "target": target,
                        "type": str(relation.get("type", "")),
                        "description": str(relation.get("description", "")),
                    }
                )
    return edges


def node_summary(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_id": node["node_id"],
        "workspace_id": node["workspace_id"],
        "title": node["title"],
        "node_type": node["node_type"],
        "authority": node["authority"],
        "status": node["status"],
        "revision": node["revision"],
    }


def _selected_node_ids(
    *,
    all_ids: set[str],
    edges: list[dict[str, str]],
    center: str | None,
    depth: int,
    limit: int,
) -> set[str]:
    if center is None:
        return set(sorted(all_ids)[:limit])
    selected = {center}
    frontier = deque([(center, 0)])
    while frontier and len(selected) < limit:
        current, current_depth = frontier.popleft()
        if current_depth >= depth:
            continue
        for neighbor in _neighbors(edges, current):
            if neighbor in selected:
                continue
            selected.add(neighbor)
            frontier.append((neighbor, current_depth + 1))
            if len(selected) >= limit:
                break
    return selected


def _neighbors(edges: list[dict[str, str]], node_id: str) -> list[str]:
    neighbors: set[str] = set()
    for edge in edges:
        if edge["source"] == node_id:
            neighbors.add(edge["target"])
        if edge["target"] == node_id:
            neighbors.add(edge["source"])
    return sorted(neighbors)
