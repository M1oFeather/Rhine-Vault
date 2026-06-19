# Current Phase

## Active

Phase 4 — Formal UI and MCP

## Implementation status

Phase 4 implementation is in progress after explicit user advancement.

## Authorized work

- Formal UI polish and API surface continuity
- MCP stdio adapter using the official Python MCP SDK as an optional dependency
- Streamable HTTP MCP adapter behind explicit runtime enablement
- Dynamic MCP capability listing
- Bounded MCP resources for approved MemoryNode, local graph and schema metadata
- Candidate-only MCP write tools for submitting and revising staging nodes
- Tests proving MCP cannot approve, publish, delete, execute raw SQL or read arbitrary files

## Hard constraints

- Core-only install remains the default and must not require FastAPI, uvicorn, MCP SDK or frontend tooling.
- MCP support is optional through `rhine-vault[mcp]`.
- Agents may read approved formal knowledge and submit/revise candidates only.
- Agents may not approve staging, write formal nodes directly, delete formal nodes, commit Git changes, publish libraries, execute raw SQL or read arbitrary local files.
- WebUI and Element UI must remain separate reachable surfaces: `/webui` and `/element`.
- FastAPI `/docs`, `/redoc` and `/openapi.json` remain API documentation entrances.

## Not authorized in Phase 4

- ChromaDB / production vector index
- production graph UI
- Library publishing
- PDF/DOCX/OCR
- full Obsidian plugin
- cloud sync
- Redis / PostgreSQL / Neo4j

## Phase advancement rule

Only update this file after the user explicitly confirms advancement.

## Next planned phase

After Phase 4 passes review:

```text
Phase 5 — Indexing and Libraries
```

Do not skip directly beyond Phase 4 without explicit confirmation.
