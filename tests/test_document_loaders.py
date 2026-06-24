from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from rhine_vault.api import create_app
from rhine_vault.capture.service import CaptureService
from rhine_vault.document_loaders import (
    OptionalDocumentDependencyError,
    document_loader_capabilities,
    load_document_text,
)
from rhine_vault.storage.sqlite import SQLiteStore


def test_document_loader_capabilities_keep_optional_formats_explicit() -> None:
    capabilities = document_loader_capabilities()
    loaders = {loader["loader_id"]: loader for loader in capabilities["loaders"]}

    assert ".pdf" in capabilities["supported_suffixes"]
    assert ".docx" in capabilities["supported_suffixes"]
    assert loaders["markdown-text"]["available"] is True
    assert loaders["pdf-pypdf"]["optional_dependency"] == "pypdf"
    assert loaders["docx-python-docx"]["optional_dependency"] == "python-docx"
    assert "Capture Proposal" in capabilities["authority"]


def test_pdf_loader_reports_missing_optional_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "notes.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    def fake_import_module(name: str) -> Any:
        if name == "pypdf":
            raise ImportError(name)
        return importlib.import_module(name)

    monkeypatch.setattr("rhine_vault.document_loaders.importlib.import_module", fake_import_module)

    with pytest.raises(OptionalDocumentDependencyError, match="rhine-vault\\[documents\\]"):
        load_document_text(pdf_path)


def test_pdf_document_import_uses_optional_loader_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakePage:
        def extract_text(self) -> str:
            return "NeoForge PDF knowledge\nDeferredRegister can be documented from PDF."

    class FakePdfReader:
        def __init__(self, path: str) -> None:
            self.path = path
            self.pages = [FakePage()]

    def fake_import_module(name: str) -> Any:
        if name == "pypdf":
            return SimpleNamespace(PdfReader=FakePdfReader)
        return importlib.import_module(name)

    monkeypatch.setattr("rhine_vault.document_loaders.importlib.import_module", fake_import_module)
    pdf_path = tmp_path / "guide.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    store = SQLiteStore(tmp_path / ".rhine" / "vault.db", vault_root=tmp_path)
    proposal = CaptureService(store).create_document_proposal(
        workspace_id="demo-workspace",
        path=pdf_path,
    )

    assert proposal["proposed_nodes"][0]["title"] == "Page 1"
    assert "DeferredRegister" in proposal["proposed_nodes"][0]["content"]
    assert proposal["proposed_nodes"][0]["source_refs"][0]["type"] == "document"


def test_fastapi_document_importer_probe(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path / ".rhine" / "vault.db"))

    response = client.get("/api/documents/importers")
    payload = response.json()

    assert response.status_code == 200
    assert ".pdf" in payload["supported_suffixes"]
    assert "Capture Proposal" in payload["authority"]
