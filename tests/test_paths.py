from __future__ import annotations

from uuid import UUID

import pytest

from rhine_vault.io.paths import PathResolutionError, WorkspacePathResolver


def test_resolver_generates_paths_from_ids_only(tmp_path) -> None:  # type: ignore[no-untyped-def]
    resolver = WorkspacePathResolver(tmp_path)

    node_path = resolver.node_markdown_path("spectrum-protocol", "spectrum.mechanic.rgb-complement")
    staging_path = resolver.staging_entry_path(
        "spectrum-protocol", UUID("5a0e5b4e-8aa8-4e03-b153-b0af51894e90")
    )

    assert node_path == (
        tmp_path / "workspaces/spectrum-protocol/nodes/spectrum.mechanic.rgb-complement.md"
    )
    assert staging_path == (
        tmp_path / "workspaces/spectrum-protocol/.staging/5a0e5b4e-8aa8-4e03-b153-b0af51894e90.md"
    )


def test_relative_resolution_rejects_traversal_and_absolute_paths(tmp_path) -> None:  # type: ignore[no-untyped-def]
    resolver = WorkspacePathResolver(tmp_path)

    with pytest.raises(PathResolutionError):
        resolver.resolve_workspace_relative("spectrum-protocol", "../outside.md")
    with pytest.raises(PathResolutionError):
        resolver.resolve_workspace_relative("spectrum-protocol", "C:/outside.md")
    with pytest.raises(ValueError):
        resolver.workspace_root("Bad Workspace")
