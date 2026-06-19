"""Validation for formal approval candidates."""

from __future__ import annotations

from typing import Any

from rhine_vault.domain.ids import validate_node_id


def validate_candidate_node(node: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for field in ("node_id", "title", "node_type"):
        if not str(node.get(field, "")).strip():
            issues.append(
                {
                    "code": "REQUIRED_FIELD",
                    "field": field,
                    "severity": "error",
                    "message": f"{field} is required",
                }
            )
    node_id = node.get("node_id")
    if node_id:
        try:
            validate_node_id(str(node_id))
        except ValueError as exc:
            issues.append(
                {
                    "code": "INVALID_NODE_ID",
                    "field": "node_id",
                    "severity": "error",
                    "message": str(exc),
                }
            )
    return issues
