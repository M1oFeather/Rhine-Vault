"""Runtime orchestration kept import-safe for core-only installs."""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

from rhine_vault.logger import configure_logging, get_logger

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def run_server(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
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
    configure_logging()
    logger = get_logger(__name__)
    logger.info("Starting Rhine-Vault at http://%s:%s", host, port)
    uvicorn.run(create_app(database_path), host=host, port=port)


def main() -> None:
    run_server()


def _raise_missing_api_extra(exc: ImportError) -> NoReturn:
    raise RuntimeError(
        "Rhine-Vault core is installed without API server dependencies. "
        'Install the optional API extra with: pip install "rhine-vault[api]"'
    ) from exc
