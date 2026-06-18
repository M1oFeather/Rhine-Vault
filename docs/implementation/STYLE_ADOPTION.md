# Style Adoption

## 项目

- Name: Rhine-Vault
- Repository: local private repository
- Current status: Phase 1.5 Knowledge Capture Vertical Slice

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

## 当前结构调整

- 新增根目录薄入口 `main.py`。
- 新增 `src/rhine_vault/core.py`，集中应用启动编排。
- 新增 `src/rhine_vault/logger.py`，集中日志初始化。
- 新增 `src/rhine_vault/i18n.py`，集中 Phase 1.5 UI 翻译词表。
- 新增 `src/rhine_vault/config/node_types.json`，集中节点类型配置和多语言显示名。
- 新增 `src/rhine_vault/node_types.py`，负责节点类型配置加载和本地化。
- 新增 `rhine-vault` console script，指向 `rhine_vault.core:main`。
- README 项目结构图已同步入口层变化。

## 暂不迁移

- 暂不将 `src/rhine_vault/api/static/index.html` 移到根目录 `web/`。

Reason:

Phase 1.5 的 UI 是极简静态页面，并且当前 wheel 构建已经显式打包该文件。移动到根目录 `web/` 会引入额外资源定位和打包配置变化，收益暂时不高。

- 暂不新增 `adapter/`、`event/`、`plugin/` 目录。

Reason:

当前阶段没有正式 MCP、插件或事件总线。提前建立空框架会扩大 Phase 1.5 表面积。

## 已知历史问题

- Issue: 本地 AI 协作规则从根目录移动到 `docs/local/AGENTS.md` 后，外部工具若只自动扫描根目录 `AGENTS.md`，可能无法自动发现规则。
- Risk: 后续新会话需要明确从 `docs/local/AGENTS.md` 读取本地协作规则。
- Plan: 保持 README 和本地说明中的路径清晰；若后续工具要求根目录入口，可创建被忽略的本地根目录指针文件。

## 下一步

1. 若继续结构整理，优先检查是否需要将 API 层拆成 router/service 边界。
2. 若 UI 增长，再评估是否迁移到根目录 `web/` 或包内 `web/`。
3. 进入 Phase 2 前，再决定是否引入 `adapter`、`event`、`plugin` 等扩展目录。
