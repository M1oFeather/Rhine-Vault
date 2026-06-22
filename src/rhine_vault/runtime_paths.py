"""Runtime path helpers shared by API, core and MCP adapters."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_RUNTIME_DIR_NAME = ".rhine"
DEFAULT_DATABASE_NAME = "rhine-vault.db"


def runtime_home() -> Path:
    """Return the local runtime directory for the current process."""

    configured = os.getenv("RHINE_VAULT_HOME")
    if configured:
        return Path(configured).expanduser().resolve(strict=False)
    return (Path.cwd() / DEFAULT_RUNTIME_DIR_NAME).resolve(strict=False)


def default_database_path() -> Path:
    """Resolve the SQLite database path used when no explicit path is passed."""

    configured = os.getenv("RHINE_VAULT_DB")
    if configured:
        return Path(configured).expanduser().resolve(strict=False)
    return runtime_home() / DEFAULT_DATABASE_NAME
