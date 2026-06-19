"""FastAPI backend and static UI for the active implementation phase."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import gettempdir
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
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
from rhine_vault.mcp_bridge import MCPBridge
from rhine_vault.node_types import node_type_config
from rhine_vault.retrieval import (
    RetrievalOverrides,
    default_retrieval_profiles,
    resolve_retrieval_profile,
    retrieve_context_bundle,
    retrieve_lab,
)
from rhine_vault.storage.sqlite import SQLiteStore
from rhine_vault.webui_plugins import build_bot_adapter_payload, render_knowledge_document


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


class ConversationSessionRequest(BaseModel):
    workspace_id: str
    title: str | None = None


class ConversationMessageRequest(BaseModel):
    workspace_id: str
    role: str
    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("content cannot be empty")
        return cleaned


class ConversationSessionCaptureRequest(BaseModel):
    workspace_id: str


class DocumentImportRequest(BaseModel):
    workspace_id: str
    path: str

    @field_validator("path")
    @classmethod
    def _path_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("path cannot be empty")
        return cleaned


class ProjectScanRequest(BaseModel):
    workspace_id: str
    root: str
    include_paths: tuple[str, ...] = ()

    @field_validator("root")
    @classmethod
    def _root_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("root cannot be empty")
        return cleaned


class UpdateNodeRequest(BaseModel):
    workspace_id: str
    patch: dict[str, Any]


class StageRequest(BaseModel):
    workspace_id: str
    temporary_ids: tuple[str, ...]


class ApproveRequest(BaseModel):
    workspace_id: str
    entry_ids: tuple[str, ...]
    actor_id: str = "user:local"


class RejectRequest(BaseModel):
    workspace_id: str


class RollbackRequest(BaseModel):
    workspace_id: str
    revision: int = Field(ge=1)
    actor_id: str = "user:local"


class ExternalChangeReviewRequest(BaseModel):
    workspace_id: str
    actor_id: str = "user:local"


class QueryRequest(BaseModel):
    workspace_id: str
    query: str
    profile_id: str | None = None
    relation_depth: int | None = None
    result_limit: int | None = None
    include_deprecated: bool | None = None
    node_type: str | None = None
    authority: str | None = None
    tags: tuple[str, ...] = ()


class KnowledgeDocumentRequest(QueryRequest):
    title: str | None = None
    audience: str = "developer"


class OpenAICompatibleQueryRequest(QueryRequest):
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    thinking_enabled: bool = False
    reasoning_effort: str | None = None


class OpenAICompatiblePingRequest(BaseModel):
    workspace_id: str = "demo-workspace"
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    message: str = "你好"
    thinking_enabled: bool = False
    reasoning_effort: str | None = None


class OpenAICompatibleChatMessage(BaseModel):
    role: str
    content: str = Field(min_length=1)


class OpenAICompatibleChatRequest(BaseModel):
    workspace_id: str
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    messages: list[OpenAICompatibleChatMessage] = Field(min_length=1)
    thinking_enabled: bool = False
    reasoning_effort: str | None = None


class MCPToolCallRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


def create_app(database_path: Path | str | None = None) -> FastAPI:
    db_path = Path(database_path) if database_path else Path(gettempdir()) / "rhine-vault-dev.db"
    store = SQLiteStore(db_path)
    capture = CaptureService(store)
    mcp_bridge = MCPBridge(store=store, capture=capture)
    app = FastAPI(title="Rhine-Vault Phase 4")
    app.state.store = store
    app.state.capture = capture
    app.state.mcp_bridge = mcp_bridge
    ui_index_path = _resolve_ui_index_path()
    webui_index_path = _resolve_webui_index_path()
    if ui_index_path is not None:
        ui_assets_path = ui_index_path.parent / "assets"
        if ui_assets_path.is_dir():
            app.mount("/assets", StaticFiles(directory=ui_assets_path), name="ui-assets")
    if os.getenv("RHINE_VAULT_ENABLE_MCP_HTTP") == "1":
        try:
            from rhine_vault.mcp_server import create_streamable_http_app

            app.mount("/mcp", create_streamable_http_app(db_path), name="mcp")
            app.state.mcp_http_enabled = True
        except RuntimeError as exc:
            app.state.mcp_http_enabled = False
            app.state.mcp_http_error = str(exc)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        if os.getenv("RHINE_VAULT_API_DOCS_ONLY") == "1":
            return _api_docs_index()
        if ui_index_path is not None:
            return ui_index_path.read_text(encoding="utf-8")
        if webui_index_path is not None:
            return webui_index_path.read_text(encoding="utf-8")
        return _api_docs_index()

    @app.get("/webui", response_class=HTMLResponse)
    def webui() -> str:
        if webui_index_path is None:
            raise HTTPException(status_code=404, detail="WebUI panel is not available")
        return webui_index_path.read_text(encoding="utf-8")

    @app.get("/element", response_class=HTMLResponse)
    def element_ui() -> str:
        if ui_index_path is None:
            raise HTTPException(status_code=404, detail="Element UI build is not available")
        return ui_index_path.read_text(encoding="utf-8")

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

    @app.get("/api/mcp/capabilities")
    def mcp_capabilities() -> dict[str, Any]:
        payload = mcp_bridge.capabilities()
        payload["streamable_http"] = {
            "enabled": bool(getattr(app.state, "mcp_http_enabled", False)),
            "mount_path": "/mcp",
            "error": getattr(app.state, "mcp_http_error", None),
        }
        return payload

    @app.post("/api/mcp/tools/{tool_name}")
    def mcp_tool(tool_name: str, request: MCPToolCallRequest) -> dict[str, Any]:
        try:
            return mcp_bridge.call_tool(tool_name, request.arguments)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"unknown MCP tool: {tool_name}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/mcp/resources")
    def mcp_resource(uri: str) -> dict[str, Any]:
        try:
            return mcp_bridge.read_resource(uri)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"unknown MCP resource: {uri}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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

    @app.post("/api/conversation-sessions")
    def create_conversation_session(request: ConversationSessionRequest) -> dict[str, Any]:
        return store.create_conversation_session(
            workspace_id=request.workspace_id,
            title=request.title,
        )

    @app.get("/api/conversation-sessions")
    def conversation_sessions(workspace_id: str) -> list[dict[str, Any]]:
        return store.list_conversation_sessions(workspace_id)

    @app.post("/api/conversation-sessions/{session_id}/messages")
    def add_conversation_message(
        session_id: str, request: ConversationMessageRequest
    ) -> dict[str, Any]:
        return store.add_conversation_message(
            workspace_id=request.workspace_id,
            session_id=session_id,
            role=request.role,
            content=request.content,
        )

    @app.get("/api/conversation-sessions/{session_id}/messages")
    def conversation_messages(workspace_id: str, session_id: str) -> list[dict[str, Any]]:
        return store.list_conversation_messages(
            workspace_id=workspace_id,
            session_id=session_id,
        )

    @app.post("/api/conversation-sessions/{session_id}/capture")
    def capture_conversation_session(
        session_id: str, request: ConversationSessionCaptureRequest
    ) -> dict[str, Any]:
        return capture.create_chat_session_proposal(
            workspace_id=request.workspace_id,
            session_id=session_id,
        )

    @app.post("/api/documents/import")
    def document_import(request: DocumentImportRequest) -> dict[str, Any]:
        try:
            return capture.create_document_proposal(
                workspace_id=request.workspace_id,
                path=_resolve_allowed_local_path(
                    request.path,
                    store=store,
                    expected_kind="file",
                ),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/projects/scan")
    def project_scan(request: ProjectScanRequest) -> dict[str, Any]:
        try:
            return capture.scan_project(
                workspace_id=request.workspace_id,
                root=_resolve_allowed_local_path(
                    request.root,
                    store=store,
                    expected_kind="directory",
                ),
                include_paths=request.include_paths,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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

    @app.get("/api/nodes")
    def nodes(workspace_id: str) -> list[dict[str, Any]]:
        return store.list_memory_nodes(workspace_id=workspace_id)

    @app.get("/api/changesets")
    def changesets(workspace_id: str) -> list[dict[str, Any]]:
        return store.list_changesets(workspace_id=workspace_id)

    @app.get("/api/nodes/{node_id}/revisions")
    def node_revisions(workspace_id: str, node_id: str) -> list[dict[str, Any]]:
        return store.list_node_revisions(workspace_id=workspace_id, node_id=node_id)

    @app.post("/api/nodes/{node_id}/rollback")
    def rollback_node(node_id: str, request: RollbackRequest) -> dict[str, Any]:
        return store.rollback_node(
            workspace_id=request.workspace_id,
            node_id=node_id,
            revision=request.revision,
            actor_id=request.actor_id,
        )

    @app.get("/api/audit-events")
    def audit_events(workspace_id: str) -> list[dict[str, Any]]:
        return store.list_audit_events(workspace_id=workspace_id)

    @app.get("/api/index-jobs")
    def index_jobs(workspace_id: str) -> list[dict[str, Any]]:
        return store.list_index_jobs(workspace_id=workspace_id)

    @app.post("/api/external-changes/detect")
    def detect_external_changes(request: RejectRequest) -> list[dict[str, Any]]:
        return store.detect_external_changes(workspace_id=request.workspace_id)

    @app.get("/api/external-changes")
    def external_changes(workspace_id: str) -> list[dict[str, Any]]:
        return store.list_external_changes(workspace_id=workspace_id)

    @app.post("/api/external-changes/{change_id}/approve")
    def approve_external_change(
        change_id: str, request: ExternalChangeReviewRequest
    ) -> dict[str, Any]:
        return store.approve_external_change(
            workspace_id=request.workspace_id,
            change_id=change_id,
            actor_id=request.actor_id,
        )

    @app.post("/api/external-changes/{change_id}/reject")
    def reject_external_change(
        change_id: str, request: ExternalChangeReviewRequest
    ) -> dict[str, Any]:
        return store.reject_external_change(
            workspace_id=request.workspace_id,
            change_id=change_id,
            actor_id=request.actor_id,
        )

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
            actor_id=request.actor_id,
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
        overrides = RetrievalOverrides(
            profile_id=request.profile_id,
            relation_depth=request.relation_depth,
            result_limit=request.result_limit,
            include_deprecated=request.include_deprecated,
            node_type=request.node_type,
            authority=request.authority,
            tags=request.tags,
        )
        return retrieve_context_bundle(
            store=store,
            workspace_id=request.workspace_id,
            query=request.query,
            profile_id=request.profile_id,
            overrides=overrides,
        ).to_dict()

    @app.post("/api/integrations/bot/context")
    def bot_adapter_context(request: QueryRequest) -> dict[str, Any]:
        overrides = RetrievalOverrides(
            profile_id=request.profile_id,
            relation_depth=request.relation_depth,
            result_limit=request.result_limit,
            include_deprecated=request.include_deprecated,
            node_type=request.node_type,
            authority=request.authority,
            tags=request.tags,
        )
        bundle = retrieve_context_bundle(
            store=store,
            workspace_id=request.workspace_id,
            query=request.query,
            profile_id=request.profile_id,
            overrides=overrides,
        )
        return build_bot_adapter_payload(bundle)

    @app.post("/api/documents/generate")
    def generate_knowledge_document(request: KnowledgeDocumentRequest) -> dict[str, Any]:
        overrides = RetrievalOverrides(
            profile_id=request.profile_id,
            relation_depth=request.relation_depth,
            result_limit=request.result_limit,
            include_deprecated=request.include_deprecated,
            node_type=request.node_type,
            authority=request.authority,
            tags=request.tags,
        )
        bundle = retrieve_context_bundle(
            store=store,
            workspace_id=request.workspace_id,
            query=request.query,
            profile_id=request.profile_id,
            overrides=overrides,
        )
        return render_knowledge_document(
            bundle,
            title=request.title,
            audience=request.audience,
        )

    @app.get("/api/retrieval/profiles")
    def retrieval_profiles(workspace_id: str = "demo-workspace") -> dict[str, Any]:
        return {
            "default_profile_id": "technical-documentation",
            "profiles": [
                profile.model_dump()
                for profile in default_retrieval_profiles(workspace_id).values()
            ],
        }

    @app.post("/api/retrieval/lab")
    def retrieval_lab(request: QueryRequest) -> dict[str, Any]:
        overrides = RetrievalOverrides(
            profile_id=request.profile_id,
            relation_depth=request.relation_depth,
            result_limit=request.result_limit,
            include_deprecated=request.include_deprecated,
            node_type=request.node_type,
            authority=request.authority,
            tags=request.tags,
        )
        profile = resolve_retrieval_profile(
            workspace_id=request.workspace_id,
            profile_id=request.profile_id,
            overrides=overrides,
        )
        return retrieve_lab(
            store=store,
            workspace_id=request.workspace_id,
            query=request.query,
            profile=profile,
            overrides=overrides,
        )

    @app.post("/api/llm/fake")
    def fake_llm(request: QueryRequest) -> dict[str, object]:
        bundle = build_context_bundle(
            store=store,
            workspace_id=request.workspace_id,
            question=request.query,
        )
        return FakeLLMProvider().answer(question=request.query, context_bundle=bundle)

    @app.get("/api/llm/openai-compatible/status")
    def openai_compatible_status() -> dict[str, object]:
        return OpenAICompatibleProvider.environment_status()

    @app.post("/api/llm/openai-compatible/ping")
    def openai_compatible_ping(request: OpenAICompatiblePingRequest) -> dict[str, object]:
        try:
            provider = OpenAICompatibleProvider.from_values(
                base_url=request.base_url,
                api_key=request.api_key,
                model=request.model,
            )
            return provider.ping(
                message=request.message,
                thinking_enabled=request.thinking_enabled,
                reasoning_effort=request.reasoning_effort,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/llm/openai-compatible/chat")
    def openai_compatible_chat(request: OpenAICompatibleChatRequest) -> dict[str, object]:
        try:
            provider = OpenAICompatibleProvider.from_values(
                base_url=request.base_url,
                api_key=request.api_key,
                model=request.model,
            )
            return provider.chat(
                messages=[message.model_dump() for message in request.messages],
                thinking_enabled=request.thinking_enabled,
                reasoning_effort=request.reasoning_effort,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/llm/openai-compatible")
    def openai_compatible(request: OpenAICompatibleQueryRequest) -> dict[str, object]:
        bundle = build_context_bundle(
            store=store,
            workspace_id=request.workspace_id,
            question=request.query,
        )
        try:
            provider = OpenAICompatibleProvider.from_values(
                base_url=request.base_url,
                api_key=request.api_key,
                model=request.model,
            )
            return provider.answer(
                question=request.query,
                context_bundle=bundle,
                thinking_enabled=request.thinking_enabled,
                reasoning_effort=request.reasoning_effort,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


def _resolve_ui_index_path() -> Path | None:
    if os.getenv("RHINE_VAULT_API_DOCS_ONLY") == "1":
        return None
    configured_dist = os.getenv("RHINE_VAULT_UI_DIST")
    if configured_dist:
        configured_index = Path(configured_dist) / "index.html"
        if configured_index.is_file():
            return configured_index
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ui" / "dist" / "index.html"
        if candidate.is_file():
            return candidate
    return None


def _resolve_webui_index_path() -> Path | None:
    candidate = Path(__file__).resolve().parent / "static" / "index.html"
    if candidate.is_file():
        return candidate
    return None


def _resolve_allowed_local_path(
    raw_path: str,
    *,
    store: SQLiteStore,
    expected_kind: str,
) -> Path:
    if "\x00" in raw_path:
        raise ValueError("path contains an invalid character")
    path = Path(raw_path).expanduser().resolve(strict=False)
    roots = _allowed_import_roots(store)
    if not any(_is_relative_to(path, root) for root in roots):
        root_list = ", ".join(str(root) for root in roots)
        raise ValueError(f"path is outside allowed import roots: {root_list}")
    if expected_kind == "file" and not path.is_file():
        raise ValueError("path must be an existing file")
    if expected_kind == "directory" and not path.is_dir():
        raise ValueError("path must be an existing directory")
    return path


def _allowed_import_roots(store: SQLiteStore) -> tuple[Path, ...]:
    roots: list[Path] = [store.vault_root, Path.cwd()]
    configured = os.getenv("RHINE_VAULT_IMPORT_ROOTS")
    if configured:
        roots.extend(Path(item) for item in configured.split(os.pathsep) if item.strip())

    resolved: list[Path] = []
    for root in roots:
        resolved_root = root.expanduser().resolve(strict=False)
        if resolved_root not in resolved:
            resolved.append(resolved_root)
    return tuple(resolved)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _api_docs_index() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rhine-Vault API</title>
</head>
<body>
  <main>
    <h1>Rhine-Vault API</h1>
    <p>未检测到已构建的 Element UI, 当前提供 FastAPI 自带接口界面。</p>
    <ul>
      <li><a href="/docs">Swagger UI</a></li>
      <li><a href="/redoc">ReDoc</a></li>
      <li><a href="/openapi.json">OpenAPI JSON</a></li>
    </ul>
  </main>
</body>
</html>
"""
