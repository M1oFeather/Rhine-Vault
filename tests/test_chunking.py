from __future__ import annotations

from rhine_vault.markdown.chunking import chunk_markdown

MARKDOWN = """# Root

Opening paragraph.

## API

```python
def answer() -> int:
    return 42
```

| Name | Value |
|---|---|
| alpha | beta |

- first
- second
  - nested

::: warning
This is a constraint-like warning block.
:::
"""


def test_chunking_is_deterministic_and_revision_bound() -> None:
    chunks_a = chunk_markdown(
        MARKDOWN,
        workspace_id="spectrum-protocol",
        node_id="spectrum.mechanic.rgb-complement",
        node_revision=1,
    )
    chunks_b = chunk_markdown(
        MARKDOWN,
        workspace_id="spectrum-protocol",
        node_id="spectrum.mechanic.rgb-complement",
        node_revision=1,
    )
    chunks_c = chunk_markdown(
        MARKDOWN,
        workspace_id="spectrum-protocol",
        node_id="spectrum.mechanic.rgb-complement",
        node_revision=2,
    )

    assert [chunk.chunk_id for chunk in chunks_a] == [chunk.chunk_id for chunk in chunks_b]
    assert [chunk.chunk_id for chunk in chunks_a] != [chunk.chunk_id for chunk in chunks_c]


def test_chunking_preserves_atomic_markdown_blocks() -> None:
    chunks = chunk_markdown(
        MARKDOWN,
        workspace_id="spectrum-protocol",
        node_id="spectrum.mechanic.rgb-complement",
        node_revision=1,
    )

    assert any(chunk.chunk_type == "code" and "def answer" in chunk.content for chunk in chunks)
    assert any(
        chunk.chunk_type == "table" and "| alpha | beta |" in chunk.content for chunk in chunks
    )
    assert any(chunk.chunk_type == "list" and "  - nested" in chunk.content for chunk in chunks)
    assert any(chunk.chunk_type == "warning" for chunk in chunks)
    assert all(chunk.workspace_id == "spectrum-protocol" for chunk in chunks)
    assert chunks[1].heading_path == ("Root", "API")
