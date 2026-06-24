"""Ptilopsis starter knowledge seed.

The seed intentionally enters the normal proposal/staging workflow so starter
knowledge remains reviewable before it becomes formal MemoryNode content.
"""

from __future__ import annotations

import argparse
import json
from importlib import resources
from pathlib import Path
from typing import Any, cast

from rhine_vault.storage.sqlite import SQLiteStore

SEED_RESOURCE = "ptilopsis_initial.json"


def load_ptilopsis_seed() -> dict[str, Any]:
    """Load the packaged Ptilopsis starter seed."""
    text = resources.files(__package__).joinpath(SEED_RESOURCE).read_text(encoding="utf-8")
    loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise ValueError("Ptilopsis seed must be a JSON object")
    return cast(dict[str, Any], loaded)


def apply_ptilopsis_seed(
    store: SQLiteStore,
    *,
    workspace_id: str | None = None,
    display_name: str | None = None,
    stage: bool = True,
    approve: bool = False,
    actor_id: str = "user:local",
) -> dict[str, Any]:
    """Create a proposal, optionally stage and approve the Ptilopsis starter seed."""
    seed = load_ptilopsis_seed()
    target_workspace_id = workspace_id or str(seed["workspace_id"])
    target_display_name = display_name or str(seed["display_name"])
    store.register_workspace(
        workspace_id=target_workspace_id,
        workspace_type="library",
        display_name=target_display_name,
    )

    existing_node_ids = {
        str(node["node_id"]) for node in store.list_memory_nodes(target_workspace_id)
    }
    pending_node_ids = {
        str(entry["proposed_node"]["node_id"])
        for entry in store.list_staging(workspace_id=target_workspace_id, status="pending")
    }
    skipped_node_ids = sorted(existing_node_ids | pending_node_ids)
    proposed_nodes = [
        _node_from_seed(target_workspace_id=target_workspace_id, node=node, seed=seed)
        for node in seed["nodes"]
        if str(node["node_id"]) not in existing_node_ids
        and str(node["node_id"]) not in pending_node_ids
    ]

    if not proposed_nodes:
        return {
            "seed_id": seed["seed_id"],
            "workspace_id": target_workspace_id,
            "display_name": target_display_name,
            "proposal": None,
            "staging": [],
            "approved_nodes": [],
            "skipped_node_ids": skipped_node_ids,
        }

    source = store.add_source(
        workspace_id=target_workspace_id,
        source_type="seed_pack",
        origin=str(seed["seed_id"]),
        locator=str(seed.get("source_url", "")),
        body=json.dumps(seed, ensure_ascii=False, indent=2),
        metadata={
            "seed_id": seed["seed_id"],
            "version": seed["version"],
            "source_url": seed.get("source_url"),
            "source_note": seed.get("source_note"),
        },
    )
    for node in proposed_nodes:
        node["source_refs"] = [
            {"type": "seed_pack", "source_id": source["source_id"]},
            {"type": "web", "url": seed.get("source_url")},
        ]

    proposal = store.add_proposal(
        workspace_id=target_workspace_id,
        source_ids=(source["source_id"],),
        proposed_nodes=tuple(proposed_nodes),
        rationale="Packaged Ptilopsis starter seed.",
        confidence=0.82,
    )

    staging: list[dict[str, Any]] = []
    approved_nodes: list[dict[str, Any]] = []
    if stage or approve:
        staging = store.save_staging(
            workspace_id=target_workspace_id,
            proposal_id=proposal["proposal_id"],
            temporary_ids=tuple(node["temporary_id"] for node in proposed_nodes),
        )
    if approve:
        approved_nodes = store.approve_staging(
            workspace_id=target_workspace_id,
            entry_ids=tuple(str(entry["entry_id"]) for entry in staging),
            actor_id=actor_id,
        )

    return {
        "seed_id": seed["seed_id"],
        "workspace_id": target_workspace_id,
        "display_name": target_display_name,
        "proposal": proposal,
        "staging": staging,
        "approved_nodes": approved_nodes,
        "skipped_node_ids": skipped_node_ids,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import the packaged Ptilopsis starter seed.")
    parser.add_argument(
        "--db",
        default=".rhine/rhine-vault.db",
        help="SQLite database path. Defaults to .rhine/rhine-vault.db.",
    )
    parser.add_argument(
        "--vault-root",
        default=".",
        help="Vault root for generated workspace Markdown files. Defaults to current directory.",
    )
    parser.add_argument("--workspace-id", default=None, help="Override target workspace_id.")
    parser.add_argument("--display-name", default=None, help="Override workspace display name.")
    parser.add_argument(
        "--proposal-only",
        action="store_true",
        help="Create only the Capture Proposal and leave staging empty.",
    )
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Stage and approve the seed immediately.",
    )
    parser.add_argument("--actor-id", default="user:local", help="Approval actor id.")
    args = parser.parse_args(argv)

    store = SQLiteStore(Path(args.db), vault_root=Path(args.vault_root))
    result = apply_ptilopsis_seed(
        store,
        workspace_id=args.workspace_id,
        display_name=args.display_name,
        stage=not args.proposal_only,
        approve=args.approve,
        actor_id=args.actor_id,
    )
    print(
        json.dumps(
            {
                "seed_id": result["seed_id"],
                "workspace_id": result["workspace_id"],
                "proposal_id": (
                    None
                    if result["proposal"] is None
                    else result["proposal"]["proposal_id"]
                ),
                "staging_count": len(result["staging"]),
                "approved_count": len(result["approved_nodes"]),
                "skipped_count": len(result["skipped_node_ids"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _node_from_seed(
    *, target_workspace_id: str, node: dict[str, Any], seed: dict[str, Any]
) -> dict[str, Any]:
    node_id = str(node["node_id"])
    source_workspace_id = str(seed["workspace_id"])
    if target_workspace_id != str(seed["workspace_id"]):
        _, _, suffix = node_id.partition(".")
        node_id = f"{target_workspace_id}.{suffix or node_id}"
    relations = [
        _remap_relation_target(
            relation=relation,
            source_workspace_id=source_workspace_id,
            target_workspace_id=target_workspace_id,
        )
        for relation in node.get("relations", [])
    ]
    return {
        "temporary_id": f"proposal.seed.{node_id}",
        "node_id": node_id,
        "title": str(node["title"]),
        "node_type": str(node["node_type"]),
        "content": str(node["content"]),
        "tags": list(node.get("tags", [])),
        "authority": str(node.get("authority", "reference")),
        "source_refs": [],
        "relations": relations,
        "rationale": f"Imported from packaged seed {seed['seed_id']}.",
        "confidence": 0.82,
    }


def _remap_relation_target(
    *,
    relation: dict[str, Any],
    source_workspace_id: str,
    target_workspace_id: str,
) -> dict[str, Any]:
    copied = dict(relation)
    target_node_id = str(copied.get("target_node_id", ""))
    prefix = f"{source_workspace_id}."
    if target_workspace_id != source_workspace_id and target_node_id.startswith(prefix):
        copied["target_node_id"] = f"{target_workspace_id}.{target_node_id.removeprefix(prefix)}"
    return copied


if __name__ == "__main__":
    raise SystemExit(main())
