# Phase 5 — Indexing and Libraries

## Goal

Phase 5 turns approved knowledge into rebuildable derived indexes and introduces the first formal Library / dependency boundary.

```text
approved MemoryNode
-> queued IndexJob
-> deterministic index chunks
-> published Library snapshot
-> explicit project dependency lock
```

## Authorized Scope

- Execute queued `IndexJob` records into deterministic local `index_chunks`.
- Rebuild derived chunk indexes from approved formal nodes.
- Keep FTS and chunk indexes as rebuildable derived data.
- Register Project and Library workspaces.
- Publish immutable Library snapshot manifests.
- Read published Library snapshots.
- Lock a Project workspace to a specific Library snapshot.
- Generate dependency upgrade reports without applying the upgrade.
- Write deterministic `rhine-lock.yaml` files.
- Expose Phase 5 operations through REST endpoints.

## Hard Constraints

- Do not implement production vector search in this phase.
- Do not implement ChromaDB in this phase.
- Do not implement transitive dependency resolution.
- Do not allow silent Library upgrades.
- Do not mix Library nodes into project retrieval unless an explicit dependency and retrieval rule are implemented later.
- Do not allow downstream Projects to write Library formal nodes.
- Do not publish staging or ExternalChange content.

## Implemented Slice

- Added `index_chunks` as a rebuildable derived index table.
- Added `process_index_jobs()` to execute queued/failed jobs.
- Added `rebuild_derived_index()` to enqueue rebuild jobs for approved nodes.
- Chunking now uses rendered Markdown body only; frontmatter stays out of derived chunks.
- Added `workspace_records` for project/library registration.
- Added `library_snapshots` with immutable `(workspace_id, version)` records.
- Added `workspace_dependencies` and deterministic `rhine-lock.yaml` writing.
- Added dependency upgrade reports that compare locked and target manifests.
- Added REST endpoints for workspace registration, index processing, chunk listing, Library snapshot publishing/reading, dependency locking and upgrade reports.
- Added Phase 5 management controls to both the built-in WebUI and the Element UI client.

## REST API

| Endpoint | Purpose |
|---|---|
| `POST /api/workspaces` | Register a project or library workspace |
| `GET /api/workspaces` | List known workspaces |
| `POST /api/index-jobs/process` | Execute queued derived-index jobs |
| `POST /api/index-jobs/rebuild` | Enqueue rebuild jobs for approved nodes |
| `GET /api/index-chunks` | Inspect derived chunks |
| `POST /api/libraries/{workspace_id}/snapshots` | Publish a Library snapshot manifest |
| `GET /api/libraries/{workspace_id}/snapshots` | List published snapshots |
| `GET /api/libraries/{workspace_id}/snapshots/{version}` | Read a published snapshot |
| `POST /api/workspaces/{workspace_id}/dependencies` | Lock a project to a Library snapshot |
| `GET /api/workspaces/{workspace_id}/dependencies` | List locked dependencies |
| `GET /api/workspaces/{workspace_id}/dependencies/{alias}/upgrade-report` | Compare locked and target Library snapshots without applying the upgrade |

## Acceptance Criteria

- Approved nodes create queued index jobs.
- Processing an index job creates deterministic chunks.
- Rebuild creates new jobs without mutating formal knowledge.
- Published Library snapshots cannot be overwritten.
- Dependency lock records manifest hash, version, tag and commit.
- `rhine-lock.yaml` is generated deterministically.
- Upgrade reports list added, removed and changed Library nodes without modifying the lock.
- Library usage is explicit and does not enable silent cross-workspace retrieval.
- WebUI and Element UI can trigger index jobs, inspect chunks, publish/list snapshots, lock/list dependencies and request upgrade reports.
