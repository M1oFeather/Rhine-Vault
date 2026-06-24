# Current Phase

## Active

Full Implementation Mode

## Implementation status

Phase gates are lifted after explicit user instruction on 2026-06-23.
Future work may implement previously deferred capabilities as long as the core
architecture contract remains intact: local-first, audited knowledge, human
review boundaries for formal knowledge, and core-only install safety.

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
- Optional PDF/DOCX document text loaders that feed Capture Proposal only

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

## Newly authorized implementation areas

- Optional ChromaDB / production vector index adapters.
- Embedding provider network calls behind explicit configuration.
- Production graph API and UI surfaces.
- PDF/DOCX/OCR import pipelines behind optional dependencies.
- Obsidian integration and ExternalChange review loop.
- Cloud sync and alternative storage backends when explicitly configured.
- Import/mount execution and restore workflows with auditable safeguards.

## Phase advancement rule

Phase advancement is no longer the project limiter. Work should advance by
auditable, tested capability slices.

## Next planned phase

Immediate implementation focus:

```text
1. production vector/embedding boundary
2. graph API and UI
3. executable snapshot import workflow
4. document/OCR import extensions
5. Obsidian/plugin/sync integrations
```

Initial PDF/DOCX text loaders are implemented as optional dependencies. OCR remains a future
capability slice.

Do not collapse CMCC, Ptilopsis and Rhine-Vault into one runtime. Rhine-Vault
remains the audited long-term knowledge backend.
