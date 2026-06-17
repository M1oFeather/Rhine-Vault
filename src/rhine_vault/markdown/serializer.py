"""Deterministic Markdown frontmatter serialization."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from rhine_vault.markdown.frontmatter import MarkdownDocument

PREFERRED_FRONTMATTER_ORDER = (
    "node_id",
    "entry_id",
    "candidate_node_id",
    "workspace_id",
    "node_type",
    "title",
    "status",
    "revision",
    "base_revision",
    "schema_version",
    "created_by",
    "created_at",
    "updated_at",
    "tags",
    "relations",
    "source",
)


def serialize_markdown_document(document: MarkdownDocument) -> str:
    body = document.body.replace("\r\n", "\n").replace("\r", "\n")
    if not document.frontmatter:
        return body

    lines = ["---"]
    for key in _ordered_keys(document.frontmatter):
        lines.extend(_dump_key_value(key, document.frontmatter[key], indent=0))
    lines.append("---")
    lines.append("")
    lines.append(body.rstrip("\n"))
    return "\n".join(lines) + "\n"


def _ordered_keys(mapping: Mapping[str, Any]) -> list[str]:
    preferred = [key for key in PREFERRED_FRONTMATTER_ORDER if key in mapping]
    rest = sorted(key for key in mapping if key not in PREFERRED_FRONTMATTER_ORDER)
    return preferred + rest


def _dump_key_value(key: str, value: Any, *, indent: int) -> list[str]:
    prefix = " " * indent
    if isinstance(value, Mapping):
        lines = [f"{prefix}{key}:"]
        for nested_key in _ordered_keys(value):
            lines.extend(_dump_key_value(nested_key, value[nested_key], indent=indent + 2))
        return lines
    if isinstance(value, Sequence) and not isinstance(value, str):
        if not value:
            return [f"{prefix}{key}: []"]
        lines = [f"{prefix}{key}:"]
        for item in value:
            if isinstance(item, Mapping):
                item_keys = _ordered_keys(item)
                first_key = item_keys[0]
                lines.append(f"{prefix}  - {first_key}: {_dump_scalar(item[first_key])}")
                for nested_key in item_keys[1:]:
                    lines.extend(_dump_key_value(nested_key, item[nested_key], indent=indent + 4))
            else:
                lines.append(f"{prefix}  - {_dump_scalar(item)}")
        return lines
    return [f"{prefix}{key}: {_dump_scalar(value)}"]


def _dump_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)
