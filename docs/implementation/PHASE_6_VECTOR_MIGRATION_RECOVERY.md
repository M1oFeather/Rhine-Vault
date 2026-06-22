# Phase 6 - Vector, Migration and Recovery

## Goal

Phase 6 introduces disaster recovery, migration foundations and an explicit local vector adapter before production vector indexing.

```text
formal Markdown / SQLite / locks
-> .rhine snapshot package
-> checksum verification
-> import plan
-> emergency read-only access
-> explicit local vector adapter
```

## Authorized Slices

- Workspace `.rhine` snapshot package creation.
- Snapshot manifest and per-file checksum generation.
- Import plan generation from a `.rhine` package.
- Emergency read-only Markdown node listing when SQLite is unavailable.
- REST endpoints for snapshot creation, import-plan inspection and emergency read-only listing.
- Tests proving snapshot packages can be verified without mutating the active vault.
- Local deterministic `EmbeddingProvider` for offline vector plumbing tests.
- In-memory vector search over rebuildable `index_chunks`.
- Explicit `enable_vector` retrieval switch and explain trace.
- REST endpoint for read-only vector search.
- Read-only vector backend capability reporting for Chroma adapter evaluation.
- Read-only workflow state aggregation for management clients.
- Built-in WebUI controls for recovery, workflow state, node revisions and vector backend evaluation.

## Not Yet Authorized In This Slice

- Active ChromaDB adapter.
- Production vector retrieval.
- Embedding model provider calls.
- Formal import/mount execution.
- Automatic restore over the active vault.
- Cloud sync.
- Encryption implementation.

## Snapshot Package

The initial `.rhine` package is a ZIP file with:

```text
manifest.json
checksums.sha256
metadata.sqlite
workspace/<workspace_id>/...
```

The manifest records:

- schema version;
- snapshot kind;
- workspace IDs;
- created timestamp;
- database filename;
- file list and hashes.

## Import Plan

An import plan is read-only. It verifies:

- package exists;
- manifest exists;
- checksum file exists;
- every recorded file matches its SHA-256;
- workspace IDs are visible before import.

It does not write into the active vault.

## Emergency Read-Only

Emergency read-only mode scans approved Markdown files under:

```text
data/workspaces/<workspace_id>/nodes/*.md
```

It parses frontmatter and body enough to show formal nodes even if SQLite cannot be opened.

## Local Vector Adapter

The current vector adapter is intentionally local and deterministic:

- `HashEmbeddingProvider` creates offline vectors from chunk text.
- `InMemoryVectorIndex` searches the rebuildable `index_chunks` table.
- Retrieval uses the vector channel only when `enable_vector=true`.
- Vector hits are explainable channel candidates and remain derived data.
- No vector result can bypass formal approval or write to Markdown / SQLite formal state.

This slice exists to prove the adapter boundary and retrieval trace before any future ChromaDB-backed implementation.

## Chroma Adapter Evaluation

Phase 6 may report vector backend capability without activating a backend:

- `local-hash` is the active default backend.
- `chroma` is reported only as an optional candidate.
- The probe may detect whether `chromadb` is importable.
- The probe must not create Chroma collections.
- The probe must not write derived vectors.
- The probe must not change retrieval behavior.
- The probe must not make vector data formal authority.

## Acceptance Criteria

- A workspace snapshot can be created from an approved workspace.
- The snapshot contains manifest, checksums, SQLite metadata and workspace Markdown.
- Import plan validates the snapshot without mutating the vault.
- Tampered package content fails checksum verification.
- Emergency read-only listing returns approved nodes from Markdown only.
- API endpoints expose the above without enabling destructive restore.
- Local vector search returns hits from processed `index_chunks`.
- Retrieval Lab keeps vector disabled by default and exposes vector contribution only when explicitly enabled.
- Vector backend capability reporting shows `local-hash` active and keeps Chroma disabled.
- WebUI can drive Phase 6 recovery and workflow inspection without hidden manual loading steps.
