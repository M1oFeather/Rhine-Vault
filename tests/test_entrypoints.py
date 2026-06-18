from __future__ import annotations

import sys
from pathlib import Path

import main

import rhine_vault.core as core


def test_root_entrypoint_adds_local_src_to_import_path() -> None:
    src_path = str(Path(main.__file__).resolve().parent / "src")

    assert src_path in sys.path


def test_core_main_delegates_to_server_runner(monkeypatch) -> None:
    called = False

    def fake_run_server() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(core, "run_server", fake_run_server)

    core.main()

    assert called
