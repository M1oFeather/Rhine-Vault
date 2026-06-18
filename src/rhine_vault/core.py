"""Application orchestration for Rhine-Vault."""

from __future__ import annotations

from pathlib import Path

import uvicorn

from rhine_vault.api.app import create_app
from rhine_vault.logger import configure_logging, get_logger

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def run_server(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    database_path: Path | str | None = None,
) -> None:
    """Start the Phase 1.5 FastAPI server."""
    configure_logging()
    logger = get_logger(__name__)
    logger.info("Starting Rhine-Vault at http://%s:%s", host, port)
    uvicorn.run(create_app(database_path), host=host, port=port)


def main() -> None:
    run_server()
