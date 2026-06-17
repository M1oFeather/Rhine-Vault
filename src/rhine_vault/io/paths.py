"""Server-side path resolution with workspace isolation."""

from __future__ import annotations

from pathlib import Path, PureWindowsPath
from uuid import UUID

from rhine_vault.domain.ids import validate_node_id, validate_workspace_id


class PathResolutionError(ValueError):
    """Raised when a requested logical path would escape the vault root."""


class WorkspacePathResolver:
    """Resolve logical identifiers to vault paths without accepting client paths."""

    def __init__(self, vault_root: Path | str) -> None:
        self.vault_root = Path(vault_root).resolve(strict=False)

    def workspace_root(self, workspace_id: str) -> Path:
        return self._safe_join("workspaces", validate_workspace_id(workspace_id))

    def node_markdown_path(self, workspace_id: str, node_id: str) -> Path:
        return self._safe_join(
            "workspaces",
            validate_workspace_id(workspace_id),
            "nodes",
            f"{validate_node_id(node_id)}.md",
        )

    def staging_entry_path(self, workspace_id: str, entry_id: UUID) -> Path:
        return self._safe_join(
            "workspaces",
            validate_workspace_id(workspace_id),
            ".staging",
            f"{entry_id}.md",
        )

    def resolve_workspace_relative(self, workspace_id: str, relative_path: str) -> Path:
        """Resolve an internal relative path after rejecting traversal and drive syntax."""

        workspace_root = self.workspace_root(workspace_id)
        parts = self._validated_relative_parts(relative_path)
        candidate = workspace_root.joinpath(*parts).resolve(strict=False)
        if not self._is_relative_to(candidate, workspace_root):
            raise PathResolutionError("resolved path escapes workspace root")
        return candidate

    def _safe_join(self, *parts: str) -> Path:
        candidate = self.vault_root.joinpath(*parts).resolve(strict=False)
        if not self._is_relative_to(candidate, self.vault_root):
            raise PathResolutionError("resolved path escapes vault root")
        return candidate

    @staticmethod
    def _validated_relative_parts(relative_path: str) -> tuple[str, ...]:
        if not relative_path or "\x00" in relative_path:
            raise PathResolutionError("path is empty or contains NUL")
        if Path(relative_path).is_absolute() or PureWindowsPath(relative_path).drive:
            raise PathResolutionError("absolute paths and drive prefixes are forbidden")
        parts = PureWindowsPath(relative_path).parts
        if any(part in {"..", ""} for part in parts):
            raise PathResolutionError("path traversal is forbidden")
        return tuple(str(part) for part in parts)

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
        except ValueError:
            return False
        return True
