"""Rhine-Vault startup entry."""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_local_src_on_path() -> None:
    src_path = Path(__file__).resolve().parent / "src"
    if src_path.is_dir():
        sys.path.insert(0, str(src_path))


_ensure_local_src_on_path()

from rhine_vault.core import main  # noqa: E402

if __name__ == "__main__":
    main()
