"""A small deterministic Markdown block parser for Phase 1 chunking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

BlockType = Literal["heading", "paragraph", "code", "table", "list", "quote", "semantic"]

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_FENCE_RE = re.compile(r"^(```+|~~~+)")
_LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_TABLE_DELIMITER_RE = re.compile(r"^\s*\|?[\s:-]+\|[\s|:-]*$")
_SEMANTIC_RE = re.compile(r"^:::\s*(constraint|warning|example|rationale|deprecated|note)\s*$")


@dataclass(frozen=True)
class MarkdownBlock:
    type: BlockType
    text: str
    start_line: int
    end_line: int
    heading_level: int | None = None
    heading_text: str | None = None
    semantic_kind: str | None = None


def parse_markdown_blocks(markdown: str) -> tuple[MarkdownBlock, ...]:
    lines = markdown.splitlines()
    blocks: list[MarkdownBlock] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        line_number = index + 1
        if not line.strip():
            index += 1
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            blocks.append(
                MarkdownBlock(
                    type="heading",
                    text=line,
                    start_line=line_number,
                    end_line=line_number,
                    heading_level=len(heading.group(1)),
                    heading_text=heading.group(2).strip(),
                )
            )
            index += 1
            continue

        fence = _FENCE_RE.match(line)
        if fence:
            block, index = _consume_fenced_code(lines, index, fence.group(1))
            blocks.append(block)
            continue

        semantic = _SEMANTIC_RE.match(line)
        if semantic:
            block, index = _consume_until_closing_marker(
                lines, index, "semantic", semantic_kind=semantic.group(1)
            )
            blocks.append(block)
            continue

        if _starts_table(lines, index):
            block, index = _consume_table(lines, index)
            blocks.append(block)
            continue

        if _LIST_RE.match(line):
            block, index = _consume_list(lines, index)
            blocks.append(block)
            continue

        if line.lstrip().startswith(">"):
            block, index = _consume_prefixed(lines, index, "quote", ">")
            blocks.append(block)
            continue

        block, index = _consume_paragraph(lines, index)
        blocks.append(block)

    return tuple(blocks)


def _consume_fenced_code(
    lines: list[str], start_index: int, opening_fence: str
) -> tuple[MarkdownBlock, int]:
    fence_marker = opening_fence[0]
    index = start_index + 1
    while index < len(lines):
        if lines[index].startswith(fence_marker * len(opening_fence)):
            index += 1
            break
        index += 1
    return _block_from_range(lines, start_index, index, "code"), index


def _consume_until_closing_marker(
    lines: list[str],
    start_index: int,
    block_type: BlockType,
    *,
    semantic_kind: str | None = None,
) -> tuple[MarkdownBlock, int]:
    index = start_index + 1
    while index < len(lines):
        if lines[index].strip() == ":::":
            index += 1
            break
        index += 1
    block = _block_from_range(lines, start_index, index, block_type)
    return (
        MarkdownBlock(
            type=block.type,
            text=block.text,
            start_line=block.start_line,
            end_line=block.end_line,
            semantic_kind=semantic_kind,
        ),
        index,
    )


def _starts_table(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    return "|" in lines[index] and bool(_TABLE_DELIMITER_RE.match(lines[index + 1]))


def _consume_table(lines: list[str], start_index: int) -> tuple[MarkdownBlock, int]:
    index = start_index
    while index < len(lines) and lines[index].strip() and "|" in lines[index]:
        index += 1
    return _block_from_range(lines, start_index, index, "table"), index


def _consume_list(lines: list[str], start_index: int) -> tuple[MarkdownBlock, int]:
    index = start_index
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            if index + 1 < len(lines) and (
                _LIST_RE.match(lines[index + 1]) or lines[index + 1].startswith((" ", "\t"))
            ):
                index += 1
                continue
            break
        if _LIST_RE.match(line) or line.startswith((" ", "\t")):
            index += 1
            continue
        break
    return _block_from_range(lines, start_index, index, "list"), index


def _consume_prefixed(
    lines: list[str], start_index: int, block_type: BlockType, prefix: str
) -> tuple[MarkdownBlock, int]:
    index = start_index
    while index < len(lines) and lines[index].lstrip().startswith(prefix):
        index += 1
    return _block_from_range(lines, start_index, index, block_type), index


def _consume_paragraph(lines: list[str], start_index: int) -> tuple[MarkdownBlock, int]:
    index = start_index
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            break
        if index != start_index and (
            _HEADING_RE.match(line)
            or _FENCE_RE.match(line)
            or _SEMANTIC_RE.match(line)
            or _LIST_RE.match(line)
            or line.lstrip().startswith(">")
            or _starts_table(lines, index)
        ):
            break
        index += 1
    return _block_from_range(lines, start_index, index, "paragraph"), index


def _block_from_range(
    lines: list[str], start_index: int, end_index_exclusive: int, block_type: BlockType
) -> MarkdownBlock:
    return MarkdownBlock(
        type=block_type,
        text="\n".join(lines[start_index:end_index_exclusive]),
        start_line=start_index + 1,
        end_line=end_index_exclusive,
    )
