"""Logging helpers for Rhine-Vault."""

from __future__ import annotations

import logging

DEFAULT_LOG_FORMAT = "%(levelname)s %(name)s: %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    """Configure process-wide logging for local development entrypoints."""
    logging.basicConfig(level=level, format=DEFAULT_LOG_FORMAT)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
