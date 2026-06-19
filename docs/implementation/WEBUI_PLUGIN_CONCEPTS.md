# WebUI Plugin Concepts

This document records product concepts that should live above Core.

## Bot Adapter API Helper

Rhine-Vault should not become a bot runtime or heavy bot management panel.

Ptilopsis already owns the bot framework side:

- adapter layer;
- core runtime;
- event bus;
- plugin layer;
- platform-specific message sending and receiving.

Rhine-Vault should provide lightweight API surfaces that bot adapters can call:

- search approved knowledge;
- build Context Bundle;
- call `POST /api/integrations/bot/context` for adapter-friendly context payloads;
- answer with a configured model using approved context;
- fetch citations and source references;
- create capture proposals from conversations;
- submit candidate knowledge for review;
- inspect node revisions and provenance.

The WebUI may provide a small API key/status/test panel for bot integrations, but the bot adapter itself should live in Ptilopsis or a separate adapter package.

## Cross-Model Knowledge Curation

Use case:

```text
ChatGPT / Gemini / manual web chat / API extraction
  -> Capture Proposal
  -> human review
  -> approved MemoryNode
  -> generated docs
  -> DeepSeek or another lower-cost model consumes Context Bundle
```

This is not model training. It is a low-cost knowledge curation pipeline.

The important product value is visibility:

- generated knowledge can be reviewed in WebUI;
- wrong knowledge can be edited or rejected;
- citations and source references remain visible;
- generated documentation lets the user inspect the knowledge at human scale;
- downstream models consume approved Context Bundles instead of vague hidden database content.

Example:

For Minecraft mod development on NeoForge 1.21.1, a user can collect newer API behavior from stronger or more current models, official docs, code snippets and manual notes. Rhine-Vault turns those into reviewed nodes and generated documentation. DeepSeek can then answer using that curated project knowledge instead of hallucinating from old Forge/NeoForge versions.

## Supported Capture Modes

WebUI should support both manual and automated extraction:

- manual web chat extraction: user chats in WebUI and selects messages or summaries to capture;
- API supervised extraction: one or more teacher models propose nodes, relations and docs;
- document import: official docs, generated summaries and project notes;
- project import: codebase and configuration scans;
- correction loop: generated docs reveal errors, user edits nodes or rejects proposals.

## Documentation Generation

Documentation generation belongs naturally in WebUI plugins.

Initial API:

- `POST /api/documents/generate`

Targets:

- developer docs;
- user docs;
- worldbuilding handbooks;
- novel project bibles;
- bot command/reference docs;
- version-specific technical notes.

Generated docs should be treated as a projection over approved knowledge:

- docs can cite MemoryNode IDs and source references;
- docs can reveal gaps or contradictions;
- corrections should flow back into Capture Proposal / staging / approval;
- docs should not silently become formal knowledge without review.

## Layer Placement

- Core: capture models, node models, retrieval, context bundle, markdown serialization.
- API: stable endpoints for capture, retrieval, context, query and proposal submission.
- WebUI plugin: extraction workflow, teacher-model comparison, documentation generation UI, review helpers.
- Desktop: richer local file picking, side-by-side editor, local docs preview, workspace file operations.
