# Style Adoption

## 项目

- Name: Rhine-Vault
- Repository: local private repository
- Current status: Phase 4 Formal UI and MCP

## 已采用

- [x] README 展示结构
- [x] 根目录 `main.py`
- [x] 清晰项目包 `src/rhine_vault`
- [x] `docs` / `examples` / `tests` 分离
- [x] 运行数据忽略
- [x] 本地 AI 协作材料归档到 `docs/local`
- [x] MkDocs 使用 `docs/` 作为文档源
- [x] lint / format / test / type-check 命令
- [x] Markdown 文档 UTF-8 with BOM，便于 Windows PowerShell 读取中文
- [x] UI 默认中文，并支持中文 / English i18n 切换
- [x] 节点类型下拉列表来自配置文件，并支持中文 / English 显示名
- [x] 默认 Python 安装保持 core-only，不强制 API/UI 依赖
- [x] 安装层级区分 core / api / webui / desktop
- [x] 新增独立 `ui/` Element Plus / Vite 客户端骨架
- [x] Phase 4 MCP 能力边界可在 WebUI 和 Element UI 中查看

## 当前结构调整

- 新增根目录薄入口 `main.py`。
- 新增 `src/rhine_vault/core/`，作为 core-only 入口与运行时边界。
- 新增 `src/rhine_vault/logger.py`，集中日志初始化。
- 新增 `src/rhine_vault/i18n.py`，集中当前原生 UI 翻译词表。
- 新增 `src/rhine_vault/config/node_types.json`，集中节点类型配置和多语言显示名。
- 新增 `src/rhine_vault/node_types.py`，负责节点类型配置加载和本地化。
- 新增 `rhine-vault` console script，指向 `rhine_vault.core:main`，API 依赖在运行时 lazy import。
- 新增 `api`、`webui`、`desktop` optional extras，表达分层安装目标。
- 新增 `mcp` optional extra，保持 MCP SDK 可选加载。
- 新增 `ui/`，使用 Vite + Vue + Element Plus 作为可选前端客户端。
- 保留 `src/rhine_vault/api/static/index.html` 作为内置 WebUI 管理面板。
- WebUI 与 Element UI 均新增 MCP 能力边界面板，用于查看工具白名单、禁止工具、资源模板和调用受限工具。
- 新增 `ui/src/assets/icons/game-icon-pack/`，引入 `M1oFeather/Game-Icon-Pack` 精选 SVG 子集供面板使用。
- README 项目结构图已同步入口层变化。

## UI 边界

Reason:

Rhine-Vault 需要同时保留内置 WebUI 和 Element/Vite UI。WebUI 用于轻量远程管理和功能连续性；Element UI 用于后续更完整的前端体验。FastAPI `/docs`、`/redoc` 和 `/openapi.json` 是接口文档入口，不替代 Web 管理面板。

## 暂不迁移

- 暂不新增 `adapter/`、`event/`、`plugin/` 目录。

Reason:

当前 Phase 4 只实现正式 MCP 边界，不建立完整插件或事件总线。提前建立空框架会扩大阶段表面积。

## 已知历史问题

- Issue: 本地 AI 协作规则从根目录移动到 `docs/local/AGENTS.md` 后，外部工具若只自动扫描根目录 `AGENTS.md`，可能无法自动发现规则。
- Risk: 后续新会话需要明确从 `docs/local/AGENTS.md` 读取本地协作规则。
- Plan: 保持 README 和本地说明中的路径清晰；若后续工具要求根目录入口，可创建被忽略的本地根目录指针文件。

## 下一步

1. 若继续结构整理，优先检查是否需要将 API 层拆成 router/service 边界。
2. 若 UI 增长，优先在 `ui/` 内继续组件化，不再把复杂前端塞回 Python 包内。
3. 后续实现时，继续补齐 workflow/service/store 边界；`adapter`、`event`、`plugin` 等扩展目录继续等到对应阶段再引入。
