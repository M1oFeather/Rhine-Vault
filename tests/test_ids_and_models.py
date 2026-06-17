from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from rhine_vault.domain.capture import CaptureProposal, SourceRecord
from rhine_vault.domain.ids import validate_node_id, validate_workspace_id
from rhine_vault.domain.models import (
    MemoryNode,
    NodeRelation,
    NodeSource,
    NodeStatus,
    RelationDirection,
    StagingEntry,
    StagingStatus,
)

NOW = datetime(2026, 6, 17, 13, 0, tzinfo=UTC)


def test_workspace_and_node_ids_are_validated() -> None:
    assert validate_workspace_id("spectrum-protocol") == "spectrum-protocol"
    assert validate_node_id("spectrum.mechanic.rgb-complement") == (
        "spectrum.mechanic.rgb-complement"
    )

    with pytest.raises(ValueError):
        validate_workspace_id("../escape")
    with pytest.raises(ValueError):
        validate_node_id("Bad/Node")


def test_memory_node_requires_workspace_and_typed_relations() -> None:
    node = MemoryNode(
        node_id="spectrum.mechanic.rgb-complement",
        workspace_id="spectrum-protocol",
        node_type="GameMechanic",
        title="RGB complement",
        content="Approved content",
        status=NodeStatus.ACTIVE,
        revision=1,
        schema_version=1,
        tags=("combat", "rgb"),
        relations=(
            NodeRelation(
                target="spectrum.mechanic.white-finish",
                type="interacts_with",
                direction=RelationDirection.OUTGOING,
            ),
        ),
        source=NodeSource(type="human_reviewed", origin="test", reference=None),
        created_at=NOW,
        updated_at=NOW,
    )

    assert node.workspace_id == "spectrum-protocol"
    assert node.relations[0].type == "interacts_with"


def test_invalid_model_ids_raise_validation_errors() -> None:
    with pytest.raises(ValidationError):
        MemoryNode(
            node_id="invalid/path",
            workspace_id="spectrum-protocol",
            node_type="Note",
            title="Bad",
            status=NodeStatus.ACTIVE,
            revision=1,
            schema_version=1,
            created_at=NOW,
            updated_at=NOW,
        )


def test_staging_and_capture_models_do_not_approve_formal_knowledge() -> None:
    staging = StagingEntry(
        entry_id=uuid4(),
        workspace_id="spectrum-protocol",
        candidate_node_id="spectrum.enemy.shield-crawler",
        status=StagingStatus.PENDING,
        base_revision=None,
        created_by="ptilopsis-agent",
        created_at=NOW,
        updated_at=NOW,
    )
    source = SourceRecord(
        source_id=uuid4(),
        workspace_id=staging.workspace_id,
        source_type="conversation",
        origin="session:test",
        created_at=NOW,
    )
    proposal = CaptureProposal(
        proposal_id=uuid4(),
        workspace_id=staging.workspace_id,
        source_id=source.source_id,
        status="pending_review",
        created_at=NOW,
    )

    assert staging.status is StagingStatus.PENDING
    assert proposal.status == "pending_review"
