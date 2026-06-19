"""Structured diffs for formal review surfaces."""

from __future__ import annotations

from typing import Any

DIFF_FIELDS = ("title", "node_type", "authority", "content", "tags", "source_refs")


def build_node_diff(*, before: dict[str, Any] | None, after: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic field-level diff for a node candidate."""

    if before is None:
        return {
            "change_type": "create",
            "fields": {
                field: {"before": None, "after": after.get(field)}
                for field in DIFF_FIELDS
                if after.get(field) not in (None, [], "")
            },
        }

    fields: dict[str, dict[str, Any]] = {}
    for field in DIFF_FIELDS:
        before_value = before.get(field)
        after_value = after.get(field)
        if before_value != after_value:
            fields[field] = {"before": before_value, "after": after_value}

    return {
        "change_type": "update" if fields else "noop",
        "fields": fields,
    }
