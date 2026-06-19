"""Core-only public entrypoints for Rhine-Vault."""

from __future__ import annotations

from rhine_vault.core.runtime import DEFAULT_HOST, DEFAULT_PORT, run_server


def main() -> None:
    run_server()


__all__ = ["DEFAULT_HOST", "DEFAULT_PORT", "main", "run_server"]
