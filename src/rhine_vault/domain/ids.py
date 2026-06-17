"""Identifier validation shared by models and path resolution."""

from __future__ import annotations

import re
from typing import Final

WORKSPACE_ID_PATTERN: Final = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")
NODE_ID_PATTERN: Final = re.compile(r"^[a-z0-9][a-z0-9._-]{1,126}[a-z0-9]$")
RELATION_TYPE_PATTERN: Final = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
ACTOR_ID_PATTERN: Final = re.compile(r"^[a-z0-9][a-z0-9._:-]{1,126}[a-z0-9]$")

BUILT_IN_RELATION_TYPES: Final[frozenset[str]] = frozenset(
    {
        "depends_on",
        "implements",
        "extends",
        "references",
        "conflicts_with",
        "supersedes",
        "causes",
        "affects",
        "belongs_to",
        "interacts_with",
        "related_to",
    }
)


class InvalidIdentifierError(ValueError):
    """Raised when an identifier does not match the Rhine-Vault contract."""


def validate_workspace_id(workspace_id: str) -> str:
    if not WORKSPACE_ID_PATTERN.fullmatch(workspace_id):
        raise InvalidIdentifierError(f"invalid workspace_id: {workspace_id!r}")
    return workspace_id


def validate_node_id(node_id: str) -> str:
    if not NODE_ID_PATTERN.fullmatch(node_id):
        raise InvalidIdentifierError(f"invalid node_id: {node_id!r}")
    return node_id


def validate_relation_type(relation_type: str) -> str:
    if not RELATION_TYPE_PATTERN.fullmatch(relation_type):
        raise InvalidIdentifierError(f"invalid relation type: {relation_type!r}")
    return relation_type


def validate_actor_id(actor_id: str) -> str:
    if not ACTOR_ID_PATTERN.fullmatch(actor_id):
        raise InvalidIdentifierError(f"invalid actor_id: {actor_id!r}")
    return actor_id
