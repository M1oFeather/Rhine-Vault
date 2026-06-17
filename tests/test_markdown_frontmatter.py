from __future__ import annotations

from rhine_vault.markdown.frontmatter import parse_markdown_document
from rhine_vault.markdown.serializer import serialize_markdown_document

EXAMPLE = """---
node_id: spectrum.mechanic.rgb-complement
workspace_id: spectrum-protocol
node_type: GameMechanic
title: RGB complement
status: active
revision: 1
schema_version: 1
tags:
  - combat
  - rgb
relations:
  - target: spectrum.mechanic.white-finish
    type: interacts_with
    direction: outgoing
    description: White finish condition
source:
  type: human_reviewed
  origin: architecture-package
  reference: design-baseline-v2.1
---

# Mechanic

Body text.
"""


def test_frontmatter_parser_reads_nested_subset() -> None:
    document = parse_markdown_document(EXAMPLE)

    assert document.frontmatter["workspace_id"] == "spectrum-protocol"
    assert document.frontmatter["revision"] == 1
    assert document.frontmatter["tags"] == ["combat", "rgb"]
    assert document.frontmatter["relations"][0]["type"] == "interacts_with"
    assert document.frontmatter["source"]["origin"] == "architecture-package"
    assert document.body.startswith("# Mechanic")


def test_serialization_is_deterministic_and_parseable() -> None:
    document = parse_markdown_document(EXAMPLE)
    first = serialize_markdown_document(document)
    second = serialize_markdown_document(parse_markdown_document(first))

    assert first == second
    assert parse_markdown_document(second).frontmatter == document.frontmatter
