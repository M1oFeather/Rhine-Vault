from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import main
import pytest
from fastapi.testclient import TestClient

import rhine_vault.core as core
from rhine_vault.api.app import _resolve_ui_index_path, create_app
from rhine_vault.runtime_paths import default_database_path, runtime_home


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


def test_default_runtime_paths_use_local_rhine_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("RHINE_VAULT_HOME", raising=False)
    monkeypatch.delenv("RHINE_VAULT_DB", raising=False)

    assert runtime_home() == tmp_path / ".rhine"
    assert default_database_path() == tmp_path / ".rhine" / "rhine-vault.db"


def test_runtime_database_path_honors_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = tmp_path / "configured" / "vault.sqlite3"
    monkeypatch.setenv("RHINE_VAULT_DB", str(configured))

    assert default_database_path() == configured


def test_fastapi_health_reports_usable_runtime_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("RHINE_VAULT_DB", raising=False)
    monkeypatch.delenv("RHINE_VAULT_HOME", raising=False)
    client = TestClient(create_app())

    health = client.get("/api/health").json()

    assert health["status"] == "ok"
    assert health["version"] == "0.1.0"
    assert health["phase"] == "Phase 6"
    assert health["database_path"] == str(tmp_path / ".rhine" / "rhine-vault.db")
    assert health["vault_root"] == str(tmp_path)
    assert health["ui"]["webui_available"] is True
    assert health["mcp"]["capability_bridge"] is True
    assert health["environment"]["database_configured"] is False


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
