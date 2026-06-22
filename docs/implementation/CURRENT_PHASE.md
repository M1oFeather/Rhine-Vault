# Current Phase

## Active

Phase 6 - Vector, Migration and Recovery

## Implementation status

Phase 6 implementation is in progress after explicit user advancement.

## Authorized work

- Workspace `.rhine` snapshot package creation
- Snapshot manifest and checksum generation
- Read-only import plan generation
- Emergency read-only Markdown node listing
- REST management endpoints for Phase 6 recovery operations
- Tests proving snapshots can be verified without mutating the active vault
- Local deterministic EmbeddingProvider and in-memory vector adapter over rebuildable index_chunks
- Explicit enable_vector retrieval toggle and vector explain trace
- Read-only vector backend capability probe for Phase 6 Chroma adapter evaluation
- Read-only workflow state aggregation for WebUI/remote management interaction flow
- WebUI Phase 6 controls for recovery, workflow state, node revisions and vector backend evaluation

## Hard constraints

- Core-only install remains the default and must not require FastAPI, uvicorn, MCP SDK or frontend tooling.
- MCP support is optional through `rhine-vault[mcp]`.
- Agents may read approved formal knowledge and submit/revise candidates only.
- Agents may not approve staging, write formal nodes directly, delete formal nodes, commit Git changes, publish libraries, execute raw SQL or read arbitrary local files.
- WebUI and Element UI must remain separate reachable surfaces: `/webui` and `/element`.
- FastAPI `/docs`, `/redoc` and `/openapi.json` remain API documentation entrances.
- Snapshot/import plan operations must not overwrite active vault data without explicit future approval.
- Emergency read-only mode may read Markdown but must not repair or write formal state.
- Vector indexes remain rebuildable derived data and must not become the formal knowledge authority.
- Vector backend probes may report optional dependency availability but must not create collections, write indexes or activate production retrieval.

## Not authorized in current Phase 6 slice

- ChromaDB / production vector index
- Embedding provider network calls
- production graph UI
- PDF/DOCX/OCR
- full Obsidian plugin
- cloud sync
- Redis / PostgreSQL / Neo4j
- destructive restore over the active vault
- automatic import/mount execution

## Phase advancement rule

Only update this file after the user explicitly confirms advancement.

## Next planned phase

After this Phase 6 local vector adapter slice passes review:

```text
Phase 6 continued - optional Chroma adapter design, still disabled by default
```

Do not skip directly beyond Phase 6 without explicit confirmation.
