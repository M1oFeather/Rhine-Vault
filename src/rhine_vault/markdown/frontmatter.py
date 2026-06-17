"""YAML-frontmatter subset parser used for deterministic Phase 1 round-trips."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MarkdownDocument:
    frontmatter: dict[str, Any]
    body: str


class FrontmatterError(ValueError):
    """Raised when a document frontmatter block cannot be parsed."""


def parse_markdown_document(markdown: str) -> MarkdownDocument:
    normalized = markdown.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---\n"):
        return MarkdownDocument(frontmatter={}, body=normalized)

    lines = normalized.split("\n")
    closing_index = _find_closing_marker(lines)
    if closing_index is None:
        raise FrontmatterError("frontmatter opening marker has no closing marker")

    frontmatter_lines = lines[1:closing_index]
    body = "\n".join(lines[closing_index + 1 :])
    if body.startswith("\n"):
        body = body[1:]
    return MarkdownDocument(frontmatter=_parse_mapping(frontmatter_lines), body=body)


def _find_closing_marker(lines: list[str]) -> int | None:
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return index
    return None


def _parse_mapping(lines: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.startswith(" "):
            raise FrontmatterError(f"unexpected indentation at line {index + 1}")
        key, raw_value = _split_key_value(line)
        if raw_value == "":
            value, index = _parse_nested(lines, index + 1)
        else:
            value = _parse_scalar(raw_value)
            index += 1
        result[key] = value
    return result


def _parse_nested(lines: list[str], start_index: int) -> tuple[Any, int]:
    if start_index >= len(lines) or not lines[start_index].startswith("  "):
        return None, start_index

    if lines[start_index].lstrip().startswith("- "):
        items: list[Any] = []
        index = start_index
        while index < len(lines) and lines[index].startswith("  - "):
            item_line = lines[index][4:]
            if ": " in item_line or item_line.endswith(":"):
                item: dict[str, Any] = {}
                if item_line:
                    key, raw_value = _split_key_value(item_line)
                    item[key] = _parse_scalar(raw_value) if raw_value != "" else None
                index += 1
                while index < len(lines) and lines[index].startswith("    "):
                    key, raw_value = _split_key_value(lines[index][4:])
                    item[key] = _parse_scalar(raw_value)
                    index += 1
                items.append(item)
            else:
                items.append(_parse_scalar(item_line))
                index += 1
        return items, index

    mapping: dict[str, Any] = {}
    index = start_index
    while index < len(lines) and lines[index].startswith("  "):
        key, raw_value = _split_key_value(lines[index][2:])
        mapping[key] = _parse_scalar(raw_value)
        index += 1
    return mapping, index


def _split_key_value(line: str) -> tuple[str, str]:
    if ":" not in line:
        raise FrontmatterError(f"expected key-value line, got: {line!r}")
    key, raw_value = line.split(":", 1)
    key = key.strip()
    if not key:
        raise FrontmatterError("empty frontmatter key")
    return key, raw_value.strip()


def _parse_scalar(raw_value: str) -> Any:
    if raw_value == "null":
        return None
    if raw_value == "true":
        return True
    if raw_value == "false":
        return False
    if raw_value.startswith("[") and raw_value.endswith("]"):
        inner = raw_value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    if raw_value.isdecimal():
        return int(raw_value)
    return _unquote(raw_value)


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
