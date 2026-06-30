# Novel Studio Plugin

Novel Studio is a WebUI/Desktop plugin capability on top of Rhine-Vault. It is
not a replacement for the formal knowledge core.

## Boundary

- Worldbuilding, character cards, timeline events, outlines, chapter drafts,
  foreshadowing threads and chapter reverse extraction are writing workflow
  artifacts.
- Durable story knowledge must still enter Rhine-Vault through Capture Proposal,
  staging and human approval.
- Generated chapters are drafts. They can be saved as `ChapterDraft` proposals,
  but they are not canon until reviewed.
- Chapter reverse extraction creates `ChapterKnowledge` proposals with
  `experimental` authority by default.

## Current Capabilities

- Create Novel Studio artifacts:
  - `Worldbuilding`
  - `CharacterCard`
  - `TimelineEvent`
  - `OutlineBeat`
  - `ChapterDraft`
  - `ForeshadowingThread`
- Generate a deterministic chapter draft from approved Context Bundle anchors.
- Run a consistency check against approved story context and explicit forbidden
  terms.
- Review foreshadowing cues, planned payoffs and unresolved cues.
- Extract candidate facts from a chapter draft and optionally place the proposal
  into staging.

## API Surface

- `POST /api/novel/artifacts`
- `POST /api/novel/chapter/generate`
- `POST /api/novel/consistency/check`
- `POST /api/novel/foreshadowing/review`
- `POST /api/novel/chapter/extract`

All retrieval-backed endpoints accept the same query/profile override shape as
the existing Context Bundle flow.

## UI Surface

The Element UI exposes Novel Studio as a dedicated activity. The page keeps the
workflow linear:

1. Create or import story artifacts as candidates.
2. Review and approve useful artifacts.
3. Generate chapter drafts from approved context.
4. Check consistency and foreshadowing.
5. Reverse-extract new candidate knowledge from finished chapter text.

This keeps the creative loop fast while preserving Rhine-Vault's audit boundary.
