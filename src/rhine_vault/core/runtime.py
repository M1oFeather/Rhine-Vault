"""Runtime orchestration kept import-safe for core-only installs."""

from __future__ import annotations

import argparse
import importlib.util
import os
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from rhine_vault import __version__
from rhine_vault.logger import configure_logging, get_logger
from rhine_vault.runtime_paths import default_database_path, runtime_home

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


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    command = getattr(args, "command", None)
    if command is None:
        parser.print_help()
        return 0
    if command == "version":
        print(f"Rhine-Vault {__version__}")
        return 0
    if command == "paths":
        _print_paths()
        return 0
    if command == "status":
        _print_status()
        return 0
    if command == "server":
        run_server(host=args.host, port=args.port, database_path=args.database)
        return 0
    parser.error(f"unknown command: {command}")
    return 2


def _raise_missing_api_extra(exc: ImportError) -> NoReturn:
    raise RuntimeError(
        "Rhine-Vault core is installed without API server dependencies. "
        'Install the optional API extra with: pip install "rhine-vault[api]". '
        'Core-only commands remain available: "rhine-vault status", '
        '"rhine-vault paths" and "rhine-vault version".'
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rhine-vault",
        description=(
            "Rhine-Vault core CLI. Core commands work without optional API, "
            "WebUI, desktop or MCP dependencies."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", metavar="command")

    subparsers.add_parser("version", help="Print the installed Rhine-Vault version.")
    subparsers.add_parser("paths", help="Print the resolved runtime and database paths.")
    subparsers.add_parser("status", help="Show core status and optional dependency availability.")

    server = subparsers.add_parser(
        "server",
        help="Start the optional FastAPI server. Requires rhine-vault[api].",
    )
    server.add_argument("--host", default=None, help=f"Bind host. Defaults to {DEFAULT_HOST}.")
    server.add_argument(
        "--port",
        default=None,
        type=_port_arg,
        help=f"Bind port. Defaults to {DEFAULT_PORT} or RHINE_VAULT_PORT.",
    )
    server.add_argument(
        "--database",
        default=None,
        type=Path,
        help="SQLite database path. Defaults to RHINE_VAULT_DB or .rhine/rhine-vault.db.",
    )
    return parser


def _print_paths() -> None:
    print(f"runtime_home: {runtime_home()}")
    print(f"database_path: {default_database_path()}")


def _print_status() -> None:
    print(f"version: {__version__}")
    print("core: available")
    print(f"api_extra: {_availability('fastapi', 'uvicorn')}")
    print(f"mcp_extra: {_availability('mcp')}")
    print(f"documents_extra: {_availability('pypdf', 'docx')}")
    _print_paths()


def _availability(*modules: str) -> str:
    missing = [module for module in modules if importlib.util.find_spec(module) is None]
    if not missing:
        return "available"
    return "missing " + ", ".join(missing)


def _port_arg(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if port < 1 or port > 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port
