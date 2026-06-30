"""FastAPI backend and static UI for the active implementation phase."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from rhine_vault import __version__
from rhine_vault.capture.service import CaptureService
from rhine_vault.context import build_context_bundle
from rhine_vault.document_loaders import (
    OptionalDocumentDependencyError,
    document_loader_capabilities,
)
from rhine_vault.graph import local_graph_payload
from rhine_vault.i18n import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    normalize_locale,
    translation_catalog,
)
from rhine_vault.llm import FakeLLMProvider, OpenAICompatibleProvider
from rhine_vault.mcp_bridge import MCPBridge
from rhine_vault.node_types import node_type_config
from rhine_vault.novel_studio import (
    ChapterGenerationInput,
    NovelArtifactInput,
    build_consistency_report,
    build_foreshadowing_report,
    create_novel_artifact_proposal,
    extract_chapter_knowledge_proposal,
    generate_chapter_draft,
)
from rhine_vault.recovery import (
    apply_import_plan,
    build_import_plan,
    create_workspace_snapshot,
    emergency_readonly_nodes,
    sqlite_health,
)
from rhine_vault.retrieval import (
    RetrievalOverrides,
    default_retrieval_profiles,
    resolve_retrieval_profile,
    retrieve_context_bundle,
    retrieve_lab,
)
from rhine_vault.runtime_paths import default_database_path
from rhine_vault.seeds.ptilopsis import apply_ptilopsis_seed
from rhine_vault.storage.sqlite import SQLiteStore
from rhine_vault.vector import search_index_chunks
from rhine_vault.vector_backends import vector_backend_capabilities
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


class WorkspaceRegisterRequest(BaseModel):
    workspace_id: str
    workspace_type: str = "project"
    display_name: str | None = None


class PtilopsisSeedRequest(BaseModel):
    workspace_id: str | None = None
    display_name: str | None = None
    stage: bool = True
    approve: bool = False
    actor_id: str = "user:local"


class IndexProcessRequest(BaseModel):
    workspace_id: str
    limit: int = Field(default=20, ge=1, le=100)
    chunking_profile_id: str = "technical"
    chunking_profile_revision: int = Field(default=1, ge=1)


class IndexRebuildRequest(BaseModel):
    workspace_id: str


class LibrarySnapshotRequest(BaseModel):
    version: str
    git_tag: str | None = None
    commit_hash: str | None = None


class WorkspaceDependencyRequest(BaseModel):
    alias: str
    library_workspace_id: str
    version: str
    version_requirement: str | None = None


class WorkspaceSnapshotRequest(BaseModel):
    workspace_id: str


class ImportPlanRequest(BaseModel):
    package_path: str

    @field_validator("package_path")
    @classmethod
    def _package_path_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("package_path cannot be empty")
        return cleaned


class ImportApplyRequest(ImportPlanRequest):
    target_workspace_id: str | None = None
    approve: bool = False
    overwrite: bool = False
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
    enable_vector: bool = False


class KnowledgeDocumentRequest(QueryRequest):
    title: str | None = None
    audience: str = "developer"


class NovelArtifactRequest(BaseModel):
    workspace_id: str
    artifact_type: str
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    tags: tuple[str, ...] = ()
    fields: dict[str, Any] = Field(default_factory=dict)


class NovelChapterGenerateRequest(QueryRequest):
    project_title: str = ""
    chapter_title: str = ""
    chapter_number: int = Field(default=1, ge=1)
    outline: str = ""
    pov_character: str = ""
    tone: str = ""
    target_words: int = Field(default=1200, ge=1, le=20000)
    extra_constraints: tuple[str, ...] = ()
    save_as_proposal: bool = False


class NovelConsistencyRequest(QueryRequest):
    manuscript: str = Field(min_length=1)
    strictness: str = "normal"


class NovelForeshadowingRequest(QueryRequest):
    manuscript: str = Field(min_length=1)
    planned_payoffs: tuple[str, ...] = ()


class NovelChapterExtractRequest(BaseModel):
    workspace_id: str
    chapter_title: str = Field(min_length=1)
    chapter_text: str = Field(min_length=1)
    tags: tuple[str, ...] = ()
    stage: bool = False


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
    db_path = Path(database_path) if database_path else default_database_path()
    store = SQLiteStore(db_path)
    capture = CaptureService(store)
    mcp_bridge = MCPBridge(store=store, capture=capture)
    app = FastAPI(title="Rhine-Vault Full Implementation")
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

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": __version__,
            "phase": "Full Implementation",
            "database_path": str(store.database_path),
            "vault_root": str(store.vault_root),
            "ui": {
                "webui_available": webui_index_path is not None,
                "element_available": ui_index_path is not None,
                "element_path": str(ui_index_path) if ui_index_path is not None else None,
            },
            "mcp": {
                "capability_bridge": True,
                "streamable_http_enabled": bool(getattr(app.state, "mcp_http_enabled", False)),
                "streamable_http_error": getattr(app.state, "mcp_http_error", None),
            },
            "recovery": {
                "sqlite": sqlite_health(store.database_path),
                "snapshot_schema_version": 1,
            },
            "environment": {
                "database_configured": bool(os.getenv("RHINE_VAULT_DB")),
                "home_configured": bool(os.getenv("RHINE_VAULT_HOME")),
                "import_roots_configured": bool(os.getenv("RHINE_VAULT_IMPORT_ROOTS")),
            },
        }

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

    @app.post("/api/workspaces")
    def register_workspace(request: WorkspaceRegisterRequest) -> dict[str, Any]:
        return store.register_workspace(
            workspace_id=request.workspace_id,
            workspace_type=request.workspace_type,
            display_name=request.display_name,
        )

    @app.get("/api/workspaces")
    def workspaces() -> list[dict[str, Any]]:
        return store.list_workspaces()

    @app.post("/api/seeds/ptilopsis")
    def seed_ptilopsis(request: PtilopsisSeedRequest) -> dict[str, Any]:
        return apply_ptilopsis_seed(
            store,
            workspace_id=request.workspace_id,
            display_name=request.display_name,
            stage=request.stage,
            approve=request.approve,
            actor_id=request.actor_id,
        )

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
        except (OptionalDocumentDependencyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/documents/importers")
    def document_importers() -> dict[str, Any]:
        return document_loader_capabilities()

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

    @app.get("/api/graph/local")
    def local_graph(
        workspace_id: str,
        node_id: str | None = None,
        depth: int = 1,
        limit: int = 100,
    ) -> dict[str, Any]:
        try:
            return local_graph_payload(
                nodes=store.list_memory_nodes(workspace_id=workspace_id),
                workspace_id=workspace_id,
                node_id=node_id or None,
                depth=min(max(depth, 0), 4),
                limit=min(max(limit, 1), 300),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

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

    @app.get("/api/workflow/state")
    def workflow_state(workspace_id: str) -> dict[str, Any]:
        proposals = store.list_proposals(workspace_id)
        staging_entries = store.list_staging(workspace_id=workspace_id, status="pending")
        nodes = store.list_memory_nodes(workspace_id=workspace_id)
        changesets = store.list_changesets(workspace_id=workspace_id)
        audit_events = store.list_audit_events(workspace_id=workspace_id)
        index_jobs_payload = store.list_index_jobs(workspace_id=workspace_id)
        external_changes = store.list_external_changes(workspace_id=workspace_id)
        return {
            "workspace_id": workspace_id,
            "counts": {
                "proposals": len(proposals),
                "pending_staging": len(staging_entries),
                "nodes": len(nodes),
                "changesets": len(changesets),
                "audit_events": len(audit_events),
                "index_jobs": len(index_jobs_payload),
                "external_changes": len(external_changes),
            },
            "proposals": proposals,
            "pending_staging": staging_entries,
            "nodes": nodes,
            "changesets": changesets,
            "audit_events": audit_events,
            "index_jobs": index_jobs_payload,
            "external_changes": external_changes,
        }

    @app.post("/api/index-jobs/process")
    def process_index_jobs(request: IndexProcessRequest) -> dict[str, Any]:
        return store.process_index_jobs(
            workspace_id=request.workspace_id,
            limit=request.limit,
            chunking_profile_id=request.chunking_profile_id,
            chunking_profile_revision=request.chunking_profile_revision,
        )

    @app.post("/api/index-jobs/rebuild")
    def rebuild_index_jobs(request: IndexRebuildRequest) -> list[dict[str, Any]]:
        return store.rebuild_derived_index(workspace_id=request.workspace_id)

    @app.get("/api/index-chunks")
    def index_chunks(workspace_id: str, node_id: str | None = None) -> list[dict[str, Any]]:
        return store.list_index_chunks(workspace_id=workspace_id, node_id=node_id)

    @app.post("/api/vector/search")
    def vector_search(request: QueryRequest) -> dict[str, Any]:
        return search_index_chunks(
            chunks=store.list_index_chunks(workspace_id=request.workspace_id),
            workspace_id=request.workspace_id,
            query=request.query,
            limit=request.result_limit or 10,
        )

    @app.get("/api/vector/backends")
    def vector_backends() -> dict[str, Any]:
        return vector_backend_capabilities()

    @app.post("/api/libraries/{workspace_id}/snapshots")
    def publish_library_snapshot(
        workspace_id: str,
        request: LibrarySnapshotRequest,
    ) -> dict[str, Any]:
        try:
            return store.publish_library_snapshot(
                workspace_id=workspace_id,
                version=request.version,
                git_tag=request.git_tag,
                commit_hash=request.commit_hash,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/libraries/{workspace_id}/snapshots")
    def library_snapshots(workspace_id: str) -> list[dict[str, Any]]:
        return store.list_library_snapshots(workspace_id=workspace_id)

    @app.get("/api/libraries/{workspace_id}/snapshots/{version}")
    def library_snapshot(workspace_id: str, version: str) -> dict[str, Any]:
        try:
            return store.read_library_snapshot(workspace_id=workspace_id, version=version)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/workspaces/{workspace_id}/dependencies")
    def lock_workspace_dependency(
        workspace_id: str,
        request: WorkspaceDependencyRequest,
    ) -> dict[str, Any]:
        try:
            return store.lock_workspace_dependency(
                project_workspace_id=workspace_id,
                alias=request.alias,
                library_workspace_id=request.library_workspace_id,
                version=request.version,
                version_requirement=request.version_requirement,
            )
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/workspaces/{workspace_id}/dependencies")
    def workspace_dependencies(workspace_id: str) -> list[dict[str, Any]]:
        return store.list_workspace_dependencies(project_workspace_id=workspace_id)

    @app.get("/api/workspaces/{workspace_id}/dependencies/{alias}/upgrade-report")
    def workspace_dependency_upgrade_report(
        workspace_id: str,
        alias: str,
        target_version: str | None = None,
    ) -> dict[str, Any]:
        try:
            return store.dependency_upgrade_report(
                project_workspace_id=workspace_id,
                alias=alias,
                target_version=target_version,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/recovery/snapshots/workspace")
    def workspace_snapshot(request: WorkspaceSnapshotRequest) -> dict[str, Any]:
        return create_workspace_snapshot(store=store, workspace_id=request.workspace_id)

    @app.post("/api/recovery/import-plan")
    def recovery_import_plan(request: ImportPlanRequest) -> dict[str, Any]:
        try:
            return build_import_plan(
                _resolve_allowed_local_path(
                    request.package_path,
                    store=store,
                    expected_kind="file",
                )
            )
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/recovery/import-apply")
    def recovery_import_apply(request: ImportApplyRequest) -> dict[str, Any]:
        try:
            return apply_import_plan(
                store=store,
                package_path=_resolve_allowed_local_path(
                    request.package_path,
                    store=store,
                    expected_kind="file",
                ),
                target_workspace_id=request.target_workspace_id,
                approve=request.approve,
                overwrite=request.overwrite,
                actor_id=request.actor_id,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/recovery/emergency-readonly")
    def emergency_readonly(workspace_id: str) -> dict[str, Any]:
        return emergency_readonly_nodes(vault_root=store.vault_root, workspace_id=workspace_id)

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
            enable_vector=request.enable_vector,
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
            enable_vector=request.enable_vector,
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
        overrides = _overrides_from_query(request)
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

    @app.post("/api/novel/artifacts")
    def novel_artifact(request: NovelArtifactRequest) -> dict[str, Any]:
        try:
            return create_novel_artifact_proposal(
                capture=capture,
                workspace_id=request.workspace_id,
                artifact=NovelArtifactInput(
                    artifact_type=request.artifact_type,
                    title=request.title,
                    content=request.content,
                    tags=request.tags,
                    fields=request.fields,
                ),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/novel/chapter/generate")
    def novel_chapter_generate(request: NovelChapterGenerateRequest) -> dict[str, Any]:
        bundle = retrieve_context_bundle(
            store=store,
            workspace_id=request.workspace_id,
            query=request.query,
            profile_id=request.profile_id,
            overrides=_overrides_from_query(request),
        )
        generated = generate_chapter_draft(
            bundle,
            generation=ChapterGenerationInput(
                project_title=request.project_title,
                chapter_title=request.chapter_title,
                chapter_number=request.chapter_number,
                outline=request.outline,
                pov_character=request.pov_character,
                tone=request.tone,
                target_words=request.target_words,
                extra_constraints=request.extra_constraints,
            ),
        )
        if request.save_as_proposal:
            proposal = capture.create_manual_proposal(
                workspace_id=request.workspace_id,
                title=str(generated["title"]),
                node_type="ChapterDraft",
                content=str(generated["markdown"]),
                authority="experimental",
                tags=("novel", "chapter", "draft"),
            )
            generated["proposal"] = proposal
        return generated

    @app.post("/api/novel/consistency/check")
    def novel_consistency_check(request: NovelConsistencyRequest) -> dict[str, Any]:
        bundle = retrieve_context_bundle(
            store=store,
            workspace_id=request.workspace_id,
            query=request.query,
            profile_id=request.profile_id,
            overrides=_overrides_from_query(request),
        )
        return build_consistency_report(
            bundle,
            manuscript=request.manuscript,
            strictness=request.strictness,
        )

    @app.post("/api/novel/foreshadowing/review")
    def novel_foreshadowing_review(request: NovelForeshadowingRequest) -> dict[str, Any]:
        bundle = retrieve_context_bundle(
            store=store,
            workspace_id=request.workspace_id,
            query=request.query,
            profile_id=request.profile_id,
            overrides=_overrides_from_query(request),
        )
        return build_foreshadowing_report(
            bundle,
            manuscript=request.manuscript,
            planned_payoffs=request.planned_payoffs,
        )

    @app.post("/api/novel/chapter/extract")
    def novel_chapter_extract(request: NovelChapterExtractRequest) -> dict[str, Any]:
        proposal = extract_chapter_knowledge_proposal(
            capture=capture,
            workspace_id=request.workspace_id,
            chapter_title=request.chapter_title,
            chapter_text=request.chapter_text,
            tags=request.tags,
        )
        staging: list[dict[str, Any]] = []
        if request.stage:
            staging = store.save_staging(
                workspace_id=request.workspace_id,
                proposal_id=proposal["proposal_id"],
                temporary_ids=tuple(
                    str(node["temporary_id"]) for node in proposal["proposed_nodes"]
                ),
            )
        return {"proposal": proposal, "staging": staging}

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
            enable_vector=request.enable_vector,
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


def _overrides_from_query(request: QueryRequest) -> RetrievalOverrides:
    return RetrievalOverrides(
        profile_id=request.profile_id,
        relation_depth=request.relation_depth,
        result_limit=request.result_limit,
        include_deprecated=request.include_deprecated,
        node_type=request.node_type,
        authority=request.authority,
        tags=request.tags,
        enable_vector=request.enable_vector,
    )


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
