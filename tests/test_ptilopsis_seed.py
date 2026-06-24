from __future__ import annotations

from pathlib import Path

from rhine_vault.seeds.ptilopsis import apply_ptilopsis_seed, load_ptilopsis_seed
from rhine_vault.storage.sqlite import SQLiteStore


def test_ptilopsis_seed_can_enter_approved_workflow(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "vault.db", vault_root=tmp_path)

    result = apply_ptilopsis_seed(store, approve=True)

    seed = load_ptilopsis_seed()
    assert result["workspace_id"] == "ptilopsis"
    assert len(result["approved_nodes"]) == len(seed["nodes"])
    assert store.search(workspace_id="ptilopsis", query="Ptilopsis")
    assert store.search(workspace_id="ptilopsis", query="CMCCPlugin")
    assert (tmp_path / "data" / "workspaces" / "ptilopsis" / "nodes").exists()


def test_ptilopsis_seed_skips_existing_nodes(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "vault.db", vault_root=tmp_path)
    first = apply_ptilopsis_seed(store, approve=True)
    second = apply_ptilopsis_seed(store, approve=True)

    assert first["approved_nodes"]
    assert second["proposal"] is None
    assert second["approved_nodes"] == []
    assert len(second["skipped_node_ids"]) == len(first["approved_nodes"])
