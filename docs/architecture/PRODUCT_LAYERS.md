# Product Layers

Rhine-Vault is split by product capability, not only by frontend technology.

## Layer 0 - Core

Core is the smallest useful installation.

Responsibilities:

- domain models;
- schema validation;
- path safety primitives;
- Markdown round-trip parsing and serialization;
- deterministic chunking;
- SQLite persistence;
- formal workflow primitives;
- retrieval and Context Bundle assembly;
- library-safe Python APIs that other projects can import.

Core must not require FastAPI, uvicorn, Vue, Element Plus, browser runtime, desktop runtime, or plugin UI dependencies.

Core can be used in three ways:

- embedded as a dependency of another Python project;
- used by a CLI;
- used behind a separately installed API/WebUI/Desktop layer.

## Layer 1 - API Platform

API Platform is the thin HTTP boundary around Core.

Responsibilities:

- FastAPI app factory;
- OpenAPI/Swagger/ReDoc;
- stable REST contracts;
- API request validation and HTTP-specific safety checks;
- optional hosting of WebUI/Desktop build artifacts.

API Platform should avoid product-specific features such as worldbuilding workflows, novel project dashboards, bot control panels, or desktop-only file operations.

API Platform may expose stable integration endpoints that external systems call, including bot adapters.

## Layer 2 - WebUI

WebUI is the rich, extensible browser management layer.

Responsibilities:

- CLI-launched local/remote management panel;
- plugin-capable UI shell;
- worldbuilding generator workflows;
- novel writing and project management workflows;
- lightweight bot/robot integration helpers where the adapter lives in the bot framework or a separate adapter package;
- cross-model knowledge curation workflows, such as extracting knowledge from ChatGPT/Gemini/manual chat and serving approved Context Bundles to DeepSeek;
- documentation generation workflows based on approved knowledge;
- backend endpoints needed by WebUI plugins that are not necessary for Core;
- stable `/webui` entry.

WebUI may use Vue and can share code with the Desktop UI. WebUI should preserve management-panel feature parity before visual redesign.

WebUI is allowed to add Python support modules when a workflow needs server-side orchestration. It should not push product-specific plugin behavior down into Core.

WebUI plugins can provide product workflows, but formal knowledge still enters through Capture Proposal, staging and human approval.

## Layer 3 - Desktop

Desktop is the complete local workstation.

Responsibilities:

- full Element Plus workbench;
- IDE/VS Code-like layout;
- top-level menus such as File, Edit, View, Help;
- local documentation entry in the top bar;
- richer local file operations;
- desktop-only capabilities that should not be exposed by the remote WebUI by default;
- optional integration with local editor/runtime helpers.

Desktop can depend on WebUI/API/Core. Desktop should not become the only way to use Rhine-Vault.

## Packaging Direction

Initial packaging should use extras:

- `rhine-vault`: Core only.
- `rhine-vault[api]`: Core + HTTP API platform.
- `rhine-vault[webui]`: Core + API + WebUI support.
- `rhine-vault[desktop]`: Core + API + WebUI + Desktop support.

If the codebase grows, the extras can later become separate distributions:

- `rhine-vault-core`;
- `rhine-vault-api`;
- `rhine-vault-webui`;
- `rhine-vault-desktop`.

## Plugin Boundary

Plugins should target the lowest layer that can support them:

- pure knowledge/model plugins: Core or API;
- management workflows: WebUI;
- local file/editor automation: Desktop;
- bot framework adapters: external adapter packages that call Core/API; WebUI should provide lightweight status/test/config helpers, not own the bot runtime;
- cross-model knowledge curation and documentation generation: WebUI plugins, with Desktop adding richer local editing and preview.

This keeps Core lightweight while allowing WebUI and Desktop to become rich product surfaces.

## Novel Studio Plugin

Novel generation and writing management should start as a Rhine-Vault WebUI plugin, not as
Core behavior and not as a separate repository by default.

Responsibilities:

- worldbuilding libraries;
- character cards and relationship maps;
- factions, locations, items and rules;
- outline and timeline management;
- chapter planning and draft generation;
- consistency checks against approved knowledge;
- foreshadowing and callback tracking;
- chapter-to-knowledge extraction that produces Capture Proposals or staging candidates.

Novel Studio may add WebUI-specific Python orchestration when generation, consistency checks or
document projection need server-side support. Formal knowledge still enters Rhine-Vault through
Capture Proposal, staging and human approval.

Desktop may extend Novel Studio with richer local file operations, a longer-form editor, project
tree management, local preview and export tools.

Novel Studio can become a separate product later only if it grows beyond a Rhine-Vault plugin into
an independent writing application. Even then, Rhine-Vault should remain the audited knowledge
backend rather than duplicating formal knowledge storage.
