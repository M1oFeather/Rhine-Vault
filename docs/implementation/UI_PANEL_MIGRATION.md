# UI Panel Migration

## Current Direction

Rhine-Vault should keep both local WebUI and Element/Vite UI available.

- WebUI: stable management panel, suitable for lightweight remote operation.
- Element UI: richer Vue client, using Element Plus components.
- FastAPI `/docs` and `/redoc`: API documentation only, not a replacement for WebUI.

## Product Layer Mapping

- Core: smallest reusable Python library and backend foundation.
- API Platform: FastAPI/OpenAPI boundary around Core.
- WebUI: extensible browser management layer, including plugin-oriented workflows.
- Desktop: complete local workstation with richer Element UI and local-file capabilities.

Worldbuilding generators, novel-writing management, cross-model knowledge curation, and documentation generation should normally target WebUI. Desktop can add stronger local operations on top of the same backend contracts.

Bot integrations should be lightweight API helpers in WebUI. The actual bot adapter/runtime should live in the bot framework, such as Ptilopsis, or in a separate adapter package.

## Vue Rule

Both WebUI and Element UI may be implemented with Vue.

The migration must preserve panel behavior before changing visual layout:

1. Rebuild the existing WebUI panel in Vue with feature parity.
2. Share API client, state helpers, i18n, model config, and icon registry.
3. Use Element Plus as a component layer for the richer client.
4. Keep `/webui` stable for remote management.
5. Keep `/element` available for the Element client when built.

## Do Not Repeat

- Do not replace a complete WebUI panel with a smaller Element placeholder.
- Do not remove manual capture, conversation capture, document import, project scan, review, search, context, LLM, workflow, settings, or run-state surfaces during migration.
- Do not treat FastAPI docs as a user-facing management panel.

## Icon Library

Rhine-Vault uses a curated subset of `M1oFeather/Game-Icon-Pack` for panel visuals.

- Imported icons live under `ui/src/assets/icons/game-icon-pack/`.
- Vue code imports icons through `ui/src/icons/gameIconPack.ts`.
- `ui/src/components/GameIcon.vue` renders named icons.
- Additional icons should be imported from upstream only when needed by an actual panel control.
