"""Packaged starter knowledge seeds."""

from __future__ import annotations

from typing import Any

__all__ = ["apply_ptilopsis_seed", "load_ptilopsis_seed"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from rhine_vault.seeds import ptilopsis

        return getattr(ptilopsis, name)
    raise AttributeError(name)
