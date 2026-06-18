"""Minimal FastAPI backend and static UI for Phase 1.5."""

from __future__ import annotations

from pathlib import Path
from tempfile import gettempdir
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator

from rhine_vault.capture.service import CaptureService
from rhine_vault.context import build_context_bundle
from rhine_vault.i18n import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    normalize_locale,
    translation_catalog,
)
from rhine_vault.llm import FakeLLMProvider, OpenAICompatibleProvider
from rhine_vault.node_types import node_type_config
from rhine_vault.storage.sqlite import SQLiteStore


class ManualNodeRequest(BaseModel):
    workspace_id: str
    title: str = Field(min_length=1)
    node_type: str = Field(min_length=1)
    content: str
    authority: str = "approved"
    tags: tuple[str, ...] = ()

    @field_validator("title", "node_type")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value cannot be empty")
        return cleaned


class ConversationMessage(BaseModel):
    message_id: str
    role: str
    content: str


class ConversationCaptureRequest(BaseModel):
    workspace_id: str
    session_id: str
    messages: list[ConversationMessage] = Field(min_length=1)


class DocumentImportRequest(BaseModel):
    workspace_id: str
    path: str


class ProjectScanRequest(BaseModel):
    workspace_id: str
    root: str
    include_paths: tuple[str, ...] = ()


class UpdateNodeRequest(BaseModel):
    workspace_id: str
    patch: dict[str, Any]


class StageRequest(BaseModel):
    workspace_id: str
    temporary_ids: tuple[str, ...]


class ApproveRequest(BaseModel):
    workspace_id: str
    entry_ids: tuple[str, ...]


class RejectRequest(BaseModel):
    workspace_id: str


class QueryRequest(BaseModel):
    workspace_id: str
    query: str


def create_app(database_path: Path | str | None = None) -> FastAPI:
    db_path = Path(database_path) if database_path else Path(gettempdir()) / "rhine-vault-dev.db"
    store = SQLiteStore(db_path)
    capture = CaptureService(store)
    app = FastAPI(title="Rhine-Vault Phase 1.5")
    app.state.store = store
    app.state.capture = capture

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")

    @app.get("/api/i18n")
    def i18n(locale: str | None = None) -> dict[str, object]:
        selected = normalize_locale(locale)
        return {
            "locale": selected,
            "default_locale": DEFAULT_LOCALE,
            "supported_locales": list(SUPPORTED_LOCALES),
            "messages": translation_catalog(selected),
        }

    @app.get("/api/node-types")
    def node_types(locale: str | None = None) -> dict[str, object]:
        return node_type_config(locale)

    @app.post("/api/manual")
    def manual(request: ManualNodeRequest) -> dict[str, Any]:
        return capture.create_manual_proposal(**request.model_dump())

    @app.post("/api/conversations/capture")
    def conversation(request: ConversationCaptureRequest) -> dict[str, Any]:
        return capture.create_conversation_proposal(
            workspace_id=request.workspace_id,
            session_id=request.session_id,
            messages=[message.model_dump() for message in request.messages],
        )

    @app.post("/api/documents/import")
    def document_import(request: DocumentImportRequest) -> dict[str, Any]:
        return capture.create_document_proposal(
            workspace_id=request.workspace_id,
            path=Path(request.path),
        )

    @app.post("/api/projects/scan")
    def project_scan(request: ProjectScanRequest) -> dict[str, Any]:
        return capture.scan_project(
            workspace_id=request.workspace_id,
            root=Path(request.root),
            include_paths=request.include_paths,
        )

    @app.get("/api/proposals")
    def proposals(workspace_id: str) -> list[dict[str, Any]]:
        return store.list_proposals(workspace_id)

    @app.patch("/api/proposals/{proposal_id}/nodes/{temporary_id}")
    def update_node(
        proposal_id: str, temporary_id: str, request: UpdateNodeRequest
    ) -> dict[str, Any]:
        return store.update_proposed_node(
            workspace_id=request.workspace_id,
            proposal_id=proposal_id,
            temporary_id=temporary_id,
            patch=request.patch,
        )

    @app.post("/api/proposals/{proposal_id}/stage")
    def stage(proposal_id: str, request: StageRequest) -> list[dict[str, Any]]:
        return store.save_staging(
            workspace_id=request.workspace_id,
            proposal_id=proposal_id,
            temporary_ids=request.temporary_ids,
        )

    @app.get("/api/staging")
    def staging(workspace_id: str, status: str | None = "pending") -> list[dict[str, Any]]:
        return store.list_staging(workspace_id=workspace_id, status=status)

    @app.post("/api/proposals/{proposal_id}/reject")
    def reject(proposal_id: str, request: RejectRequest) -> dict[str, Any]:
        return store.reject_proposal(
            workspace_id=request.workspace_id,
            proposal_id=proposal_id,
        )

    @app.post("/api/staging/approve")
    def approve(request: ApproveRequest) -> list[dict[str, Any]]:
        return store.approve_staging(
            workspace_id=request.workspace_id,
            entry_ids=request.entry_ids,
        )

    @app.post("/api/search")
    def search(request: QueryRequest) -> list[dict[str, Any]]:
        return [
            hit.__dict__
            for hit in store.search(
                workspace_id=request.workspace_id,
                query=request.query,
            )
        ]

    @app.post("/api/context")
    def context(request: QueryRequest) -> dict[str, Any]:
        return build_context_bundle(
            store=store,
            workspace_id=request.workspace_id,
            question=request.query,
        ).to_dict()

    @app.post("/api/llm/fake")
    def fake_llm(request: QueryRequest) -> dict[str, object]:
        bundle = build_context_bundle(
            store=store,
            workspace_id=request.workspace_id,
            question=request.query,
        )
        return FakeLLMProvider().answer(question=request.query, context_bundle=bundle)

    @app.post("/api/llm/openai-compatible")
    def openai_compatible(request: QueryRequest) -> dict[str, object]:
        bundle = build_context_bundle(
            store=store,
            workspace_id=request.workspace_id,
            question=request.query,
        )
        return OpenAICompatibleProvider.from_env().answer(
            question=request.query,
            context_bundle=bundle,
        )

    return app
