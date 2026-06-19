"""Pydantic v2 domain models for Phase 1."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from rhine_vault.domain.ids import (
    BUILT_IN_RELATION_TYPES,
    validate_actor_id,
    validate_node_id,
    validate_relation_type,
    validate_workspace_id,
)


class NodeStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"
    SUPERSEDED = "superseded"


class RelationDirection(StrEnum):
    OUTGOING = "outgoing"
    INCOMING = "incoming"
    BIDIRECTIONAL = "bidirectional"


class StagingStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class IndexOperation(StrEnum):
    UPSERT = "upsert"
    DELETE = "delete"
    REBUILD = "rebuild"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ExternalChangeStatus(StrEnum):
    DETECTED = "detected"
    REVIEWING = "reviewing"
    ACCEPTED_TO_STAGING = "accepted_to_staging"
    REJECTED = "rejected"


class BaseDomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Workspace(BaseDomainModel):
    workspace_id: str
    title: str = Field(min_length=1)
    description: str | None = None
    schema_version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime

    @field_validator("workspace_id")
    @classmethod
    def _valid_workspace_id(cls, value: str) -> str:
        return validate_workspace_id(value)


class NodeSource(BaseDomainModel):
    type: str = Field(min_length=1)
    origin: str | None = None
    reference: str | None = None


class NodeRelation(BaseDomainModel):
    target: str
    type: str
    direction: RelationDirection
    description: str | None = None

    @field_validator("target")
    @classmethod
    def _valid_target(cls, value: str) -> str:
        return validate_node_id(value)

    @field_validator("type")
    @classmethod
    def _valid_relation_type(cls, value: str) -> str:
        return validate_relation_type(value)


class MemoryNode(BaseDomainModel):
    node_id: str
    workspace_id: str
    node_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = ""
    status: NodeStatus
    revision: int = Field(ge=1)
    schema_version: int = Field(ge=1)
    tags: tuple[str, ...] = ()
    relations: tuple[NodeRelation, ...] = ()
    source: NodeSource | None = None
    authority: Literal["canonical", "approved", "reference", "historical", "experimental"] = (
        "approved"
    )
    created_at: datetime
    updated_at: datetime

    @field_validator("node_id")
    @classmethod
    def _valid_node_id(cls, value: str) -> str:
        return validate_node_id(value)

    @field_validator("workspace_id")
    @classmethod
    def _valid_workspace_id(cls, value: str) -> str:
        return validate_workspace_id(value)

    @field_validator("tags")
    @classmethod
    def _valid_tags(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not tag.strip() for tag in value):
            raise ValueError("tags cannot contain empty values")
        return value


class ValidationIssue(BaseDomainModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: Literal["info", "warning", "error"] = "error"
    field: str | None = None


class StagingEntry(BaseDomainModel):
    entry_id: UUID
    workspace_id: str
    candidate_node_id: str
    status: StagingStatus
    base_revision: int | None = Field(default=None, ge=1)
    created_by: str
    created_at: datetime
    updated_at: datetime
    validation_errors: tuple[ValidationIssue, ...] = ()

    @field_validator("workspace_id")
    @classmethod
    def _valid_workspace_id(cls, value: str) -> str:
        return validate_workspace_id(value)

    @field_validator("candidate_node_id")
    @classmethod
    def _valid_candidate_node_id(cls, value: str) -> str:
        return validate_node_id(value)

    @field_validator("created_by")
    @classmethod
    def _valid_created_by(cls, value: str) -> str:
        return validate_actor_id(value)


class NodeRevision(BaseDomainModel):
    workspace_id: str
    node_id: str
    revision: int = Field(ge=1)
    content_hash: str = Field(min_length=1)
    created_by: str
    created_at: datetime

    @field_validator("workspace_id")
    @classmethod
    def _valid_workspace_id(cls, value: str) -> str:
        return validate_workspace_id(value)

    @field_validator("node_id")
    @classmethod
    def _valid_node_id(cls, value: str) -> str:
        return validate_node_id(value)

    @field_validator("created_by")
    @classmethod
    def _valid_created_by(cls, value: str) -> str:
        return validate_actor_id(value)


class ChangeSet(BaseDomainModel):
    changeset_id: UUID
    workspace_id: str
    status: Literal["draft", "pending_review", "approved", "rejected", "applied"]
    base_revision: int | None = Field(default=None, ge=1)
    description: str | None = None
    created_by: str
    created_at: datetime

    @field_validator("workspace_id")
    @classmethod
    def _valid_workspace_id(cls, value: str) -> str:
        return validate_workspace_id(value)

    @field_validator("created_by")
    @classmethod
    def _valid_created_by(cls, value: str) -> str:
        return validate_actor_id(value)


class ExternalChange(BaseDomainModel):
    change_id: UUID
    workspace_id: str
    path: str = Field(min_length=1)
    status: ExternalChangeStatus
    detected_at: datetime
    content_hash: str = Field(min_length=1)

    @field_validator("workspace_id")
    @classmethod
    def _valid_workspace_id(cls, value: str) -> str:
        return validate_workspace_id(value)


class IndexJob(BaseDomainModel):
    job_id: UUID
    workspace_id: str
    node_id: str
    revision: int = Field(ge=1)
    operation: IndexOperation
    status: JobStatus
    attempts: int = Field(ge=0)
    error_message: str | None = None

    @field_validator("workspace_id")
    @classmethod
    def _valid_workspace_id(cls, value: str) -> str:
        return validate_workspace_id(value)

    @field_validator("node_id")
    @classmethod
    def _valid_node_id(cls, value: str) -> str:
        return validate_node_id(value)


class AuditEvent(BaseDomainModel):
    event_id: UUID
    workspace_id: str
    actor_id: str
    action: str = Field(min_length=1)
    result: Literal["succeeded", "failed", "blocked"]
    node_id: str | None = None
    staging_entry_id: UUID | None = None
    before_hash: str | None = None
    after_hash: str | None = None
    error: str | None = None
    created_at: datetime

    @field_validator("workspace_id")
    @classmethod
    def _valid_workspace_id(cls, value: str) -> str:
        return validate_workspace_id(value)

    @field_validator("actor_id")
    @classmethod
    def _valid_actor_id(cls, value: str) -> str:
        return validate_actor_id(value)

    @field_validator("node_id")
    @classmethod
    def _valid_optional_node_id(cls, value: str | None) -> str | None:
        return None if value is None else validate_node_id(value)


class RetrievalProfile(BaseDomainModel):
    profile_id: str = Field(min_length=1)
    workspace_id: str
    name: str = Field(min_length=1)
    exact_weight: float = Field(default=1.0, ge=0)
    metadata_weight: float = Field(default=1.0, ge=0)
    fts_weight: float = Field(default=1.0, ge=0)
    vector_weight: float = Field(default=0.0, ge=0)
    rrf_k: int = Field(default=60, ge=1, le=200)
    relation_depth: int = Field(default=1, ge=0, le=2)
    result_limit: int = Field(default=8, ge=1, le=50)
    mandatory_limit: int = Field(default=4, ge=0, le=20)
    relevant_limit: int = Field(default=6, ge=0, le=30)
    supporting_limit: int = Field(default=6, ge=0, le=30)
    conflict_strategy: Literal["warn", "block"] = "warn"
    include_deprecated: bool = False
    schema_version: int = Field(default=1, ge=1)

    @field_validator("workspace_id")
    @classmethod
    def _valid_workspace_id(cls, value: str) -> str:
        return validate_workspace_id(value)


class ChunkingProfile(BaseDomainModel):
    profile_id: str = Field(min_length=1)
    workspace_id: str
    name: Literal["technical", "worldbuilding", "semantic-kb", "custom"]
    target_tokens: int = Field(ge=1, le=2_000)
    max_tokens: int = Field(ge=1, le=4_000)
    revision: int = Field(default=1, ge=1)
    schema_version: int = Field(default=1, ge=1)

    @field_validator("workspace_id")
    @classmethod
    def _valid_workspace_id(cls, value: str) -> str:
        return validate_workspace_id(value)


class ActorContext(BaseDomainModel):
    actor_id: str
    workspace_id: str
    role: Literal["viewer", "editor", "reviewer", "admin"]
    capabilities: tuple[str, ...] = ()

    @field_validator("actor_id")
    @classmethod
    def _valid_actor_id(cls, value: str) -> str:
        return validate_actor_id(value)

    @field_validator("workspace_id")
    @classmethod
    def _valid_workspace_id(cls, value: str) -> str:
        return validate_workspace_id(value)


__all__ = [
    "BUILT_IN_RELATION_TYPES",
    "ActorContext",
    "AuditEvent",
    "ChangeSet",
    "ChunkingProfile",
    "ExternalChange",
    "IndexJob",
    "MemoryNode",
    "NodeRelation",
    "NodeRevision",
    "NodeSource",
    "RetrievalProfile",
    "StagingEntry",
    "ValidationIssue",
    "Workspace",
]
