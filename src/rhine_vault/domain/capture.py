"""Phase 1.5 capture model placeholders without workflow implementation."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from rhine_vault.domain.ids import validate_node_id, validate_workspace_id
from rhine_vault.domain.models import BaseDomainModel, NodeRelation


class SourceRecord(BaseDomainModel):
    source_id: UUID
    workspace_id: str
    source_type: Literal["conversation", "document", "project_file"]
    origin: str = Field(min_length=1)
    content_hash: str | None = None
    locator: str | None = None
    created_at: datetime

    @field_validator("workspace_id")
    @classmethod
    def _valid_workspace_id(cls, value: str) -> str:
        return validate_workspace_id(value)


class ProposedRelation(BaseDomainModel):
    relation: NodeRelation
    rationale: str | None = None


class ProposedNode(BaseDomainModel):
    proposed_node_id: str
    node_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = ""
    tags: tuple[str, ...] = ()
    relations: tuple[ProposedRelation, ...] = ()

    @field_validator("proposed_node_id")
    @classmethod
    def _valid_proposed_node_id(cls, value: str) -> str:
        return validate_node_id(value)


class CaptureProposal(BaseDomainModel):
    proposal_id: UUID
    workspace_id: str
    source_id: UUID
    status: Literal["draft", "pending_review", "accepted_to_staging", "rejected"]
    proposed_nodes: tuple[ProposedNode, ...] = ()
    created_at: datetime

    @field_validator("workspace_id")
    @classmethod
    def _valid_workspace_id(cls, value: str) -> str:
        return validate_workspace_id(value)


class ConversationCaptureProposal(BaseDomainModel):
    proposal_id: UUID
    workspace_id: str
    session_id: str = Field(min_length=1)
    message_start: int = Field(ge=0)
    message_end: int = Field(ge=0)
    capture_proposal: CaptureProposal

    @field_validator("workspace_id")
    @classmethod
    def _valid_workspace_id(cls, value: str) -> str:
        return validate_workspace_id(value)


class DocumentImportJob(BaseDomainModel):
    job_id: UUID
    workspace_id: str
    path: str = Field(min_length=1)
    file_hash: str | None = None
    status: Literal["queued", "scanned", "proposal_created", "failed"]
    created_at: datetime

    @field_validator("workspace_id")
    @classmethod
    def _valid_workspace_id(cls, value: str) -> str:
        return validate_workspace_id(value)


class ProjectImportJob(BaseDomainModel):
    job_id: UUID
    workspace_id: str
    root_locator: str = Field(min_length=1)
    status: Literal["queued", "scanned", "proposal_created", "failed"]
    created_at: datetime

    @field_validator("workspace_id")
    @classmethod
    def _valid_workspace_id(cls, value: str) -> str:
        return validate_workspace_id(value)


class BatchReviewItem(BaseDomainModel):
    item_id: UUID
    workspace_id: str
    proposal_id: UUID
    status: Literal["pending", "approved_to_staging", "rejected"]
    reviewer_note: str | None = None

    @field_validator("workspace_id")
    @classmethod
    def _valid_workspace_id(cls, value: str) -> str:
        return validate_workspace_id(value)
