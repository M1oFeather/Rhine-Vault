"""Runtime orchestration kept import-safe for core-only installs."""

from __future__ import annotations

import os
from pathlib import Path
from typing import NoReturn

from rhine_vault.logger import configure_logging, get_logger
from rhine_vault.runtime_paths import default_database_path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def run_server(
    *,
    host: str | None = None,
    port: int | None = None,
    database_path: Path | str | None = None,
) -> None:
    """Start the optional FastAPI server.

    The imports stay inside this function so `pip install rhine-vault` can remain
    core-only. Users who want the REST/UI server install `rhine-vault[api]`.
    """

    try:
        import uvicorn

        from rhine_vault.api.app import create_app
    except ImportError as exc:
        _raise_missing_api_extra(exc)
    resolved_host = host or os.getenv("RHINE_VAULT_HOST") or DEFAULT_HOST
    resolved_port = port if port is not None else _env_port()
    resolved_database_path = Path(database_path) if database_path else default_database_path()
    configure_logging()
    logger = get_logger(__name__)
    logger.info(
        "Starting Rhine-Vault at http://%s:%s with database %s",
        resolved_host,
        resolved_port,
        resolved_database_path,
    )
    uvicorn.run(create_app(resolved_database_path), host=resolved_host, port=resolved_port)


def main() -> None:
    run_server()


def _raise_missing_api_extra(exc: ImportError) -> NoReturn:
    raise RuntimeError(
        "Rhine-Vault core is installed without API server dependencies. "
        'Install the optional API extra with: pip install "rhine-vault[api]"'
    ) from exc


def _env_port() -> int:
    raw_port = os.getenv("RHINE_VAULT_PORT")
    if raw_port is None:
        return DEFAULT_PORT
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise RuntimeError("RHINE_VAULT_PORT must be an integer") from exc
    if port < 1 or port > 65535:
        raise RuntimeError("RHINE_VAULT_PORT must be between 1 and 65535")
    return port
