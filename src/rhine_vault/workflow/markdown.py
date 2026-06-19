"""Markdown rendering for approved MemoryNode snapshots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def markdown_path_for_node(*, vault_root: Path, workspace_id: str, node_id: str) -> Path:
    safe_name = node_id.replace(".", "__")
    return vault_root / "data" / "workspaces" / workspace_id / "nodes" / f"{safe_name}.md"


def render_node_markdown(node: dict[str, Any], *, revision: int) -> str:
    frontmatter = {
        "workspace_id": node["workspace_id"],
        "node_id": node["node_id"],
        "node_type": node["node_type"],
        "title": node["title"],
        "authority": node.get("authority", "approved"),
        "status": node.get("status", "active"),
        "revision": revision,
        "tags": node.get("tags", []),
        "source_refs": node.get("source_refs", []),
        "relations": node.get("relations", []),
    }
    lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, (str, int)):
            lines.append(f"{key}: {value}")
        else:
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines.extend(["---", "", f"# {node['title']}", "", node.get("content", "").rstrip(), ""])
    return "\n".join(lines)
