"""Deterministic Markdown chunking bound to node revision and profile."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Final

from rhine_vault.domain.ids import validate_node_id, validate_workspace_id
from rhine_vault.markdown.blocks import MarkdownBlock, parse_markdown_blocks

PARSER_VERSION: Final = "markdown-blocks-v1"

PROFILE_LIMITS: Final[dict[str, tuple[int, int]]] = {
    "technical": (450, 900),
    "worldbuilding": (700, 1400),
    "semantic-kb": (350, 700),
}


@dataclass(frozen=True)
class MarkdownChunk:
    chunk_id: str
    workspace_id: str
    node_id: str
    node_revision: int
    heading_path: tuple[str, ...]
    chunk_type: str
    sequence: int
    token_count: int
    start_line: int
    end_line: int
    chunking_profile_id: str
    chunking_profile_revision: int
    parser_version: str
    content: str


def chunk_markdown(
    markdown: str,
    *,
    workspace_id: str,
    node_id: str,
    node_revision: int,
    chunking_profile_id: str = "technical",
    chunking_profile_revision: int = 1,
) -> tuple[MarkdownChunk, ...]:
    validate_workspace_id(workspace_id)
    validate_node_id(node_id)
    if node_revision < 1:
        raise ValueError("node_revision must be >= 1")
    if chunking_profile_revision < 1:
        raise ValueError("chunking_profile_revision must be >= 1")

    blocks = parse_markdown_blocks(markdown)
    heading_stack: list[tuple[int, str]] = []
    chunks: list[MarkdownChunk] = []

    for block in blocks:
        if block.type == "heading":
            heading_stack = _updated_heading_stack(heading_stack, block)
            continue

        heading_path = tuple(text for _, text in heading_stack)
        block_chunks = _split_block_if_needed(block, chunking_profile_id)
        for block_text, start_line, end_line in block_chunks:
            sequence = len(chunks) + 1
            content = _with_heading_context(block_text, heading_path)
            chunk_type = block.semantic_kind or block.type
            token_count = count_tokens(content)
            chunks.append(
                MarkdownChunk(
                    chunk_id=_stable_chunk_id(
                        workspace_id=workspace_id,
                        node_id=node_id,
                        node_revision=node_revision,
                        profile_id=chunking_profile_id,
                        profile_revision=chunking_profile_revision,
                        sequence=sequence,
                        content=content,
                    ),
                    workspace_id=workspace_id,
                    node_id=node_id,
                    node_revision=node_revision,
                    heading_path=heading_path,
                    chunk_type=chunk_type,
                    sequence=sequence,
                    token_count=token_count,
                    start_line=start_line,
                    end_line=end_line,
                    chunking_profile_id=chunking_profile_id,
                    chunking_profile_revision=chunking_profile_revision,
                    parser_version=PARSER_VERSION,
                    content=content,
                )
            )

    return tuple(chunks)


def count_tokens(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text))


def _updated_heading_stack(
    heading_stack: list[tuple[int, str]], block: MarkdownBlock
) -> list[tuple[int, str]]:
    if block.heading_level is None or block.heading_text is None:
        return heading_stack
    return [(level, text) for level, text in heading_stack if level < block.heading_level] + [
        (block.heading_level, block.heading_text)
    ]


def _split_block_if_needed(
    block: MarkdownBlock, chunking_profile_id: str
) -> tuple[tuple[str, int, int], ...]:
    _, max_tokens = PROFILE_LIMITS.get(chunking_profile_id, PROFILE_LIMITS["technical"])
    if block.type in {"code", "table", "list", "quote", "semantic"}:
        return ((block.text, block.start_line, block.end_line),)
    if count_tokens(block.text) <= max_tokens:
        return ((block.text, block.start_line, block.end_line),)

    lines = block.text.splitlines()
    pieces: list[tuple[str, int, int]] = []
    current: list[str] = []
    current_start = block.start_line
    for offset, line in enumerate(lines):
        current.append(line)
        if count_tokens("\n".join(current)) >= max_tokens:
            end_line = block.start_line + offset
            pieces.append(("\n".join(current), current_start, end_line))
            current = []
            current_start = end_line + 1
    if current:
        pieces.append(("\n".join(current), current_start, block.end_line))
    return tuple(pieces)


def _with_heading_context(block_text: str, heading_path: tuple[str, ...]) -> str:
    if not heading_path:
        return block_text
    return f"Heading: {' > '.join(heading_path)}\n\n{block_text}"


def _stable_chunk_id(
    *,
    workspace_id: str,
    node_id: str,
    node_revision: int,
    profile_id: str,
    profile_revision: int,
    sequence: int,
    content: str,
) -> str:
    payload = "\n".join(
        [
            workspace_id,
            node_id,
            str(node_revision),
            profile_id,
            str(profile_revision),
            PARSER_VERSION,
            str(sequence),
            content,
        ]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"chunk-{digest}"
