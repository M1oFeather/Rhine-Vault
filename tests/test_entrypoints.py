from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import main
import pytest

import rhine_vault.core as core
from rhine_vault.api.app import _resolve_ui_index_path


def test_root_entrypoint_adds_local_src_to_import_path() -> None:
    src_path = str(Path(main.__file__).resolve().parent / "src")

    assert src_path in sys.path


def test_core_main_delegates_to_server_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def fake_run_server() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(core, "run_server", fake_run_server)

    core.main()

    assert called


def test_default_install_is_core_only() -> None:
    pyproject = tomllib.loads((Path(main.__file__).resolve().parent / "pyproject.toml").read_text())

    dependencies = pyproject["project"]["dependencies"]
    optional_dependencies = pyproject["project"]["optional-dependencies"]

    assert dependencies == ["pydantic>=2.12,<3"]
    assert "fastapi>=0.125,<1" in optional_dependencies["api"]
    assert "uvicorn>=0.38,<1" in optional_dependencies["api"]
    assert optional_dependencies["webui"] == optional_dependencies["api"]
    assert optional_dependencies["desktop"] == optional_dependencies["api"]


def test_api_can_resolve_external_ui_dist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    index = dist / "index.html"
    index.write_text('<!doctype html><div id="app"></div>', encoding="utf-8")
    monkeypatch.setenv("RHINE_VAULT_UI_DIST", str(dist))

    assert _resolve_ui_index_path() == index
