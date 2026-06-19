# V1.0 验收标准

## 工作区

- 创建两个 Project 和一个 Library；
- 无声明依赖时无法跨库搜索；
- 非法 workspace_id 和路径穿越被拒绝。

## 安装与客户端边界

- 默认 Python 安装可作为 core-only 库使用；
- API server 依赖通过可选 extra 安装；
- UI 客户端位于独立 `ui/` 目录；
- 后端可托管构建后的 `ui/dist`，但 core 不依赖前端工具链；
- 后端保留内置 WebUI 管理面板，至少可通过 `/webui` 打开；
- 未构建 Element UI 时 API server 可回落到 WebUI，并保留 FastAPI 自带 `/docs`、`/redoc` 和 `/openapi.json` 入口。
- HTTP API 的本地文档导入与项目扫描必须限制在允许导入根目录内。

## 编辑与审批

- UI 编辑不会直接改正式文件；
- 保存只进入 staging；
- 批准生成 revision、Git commit、AuditEvent、IndexJob；
- revision 冲突被阻止；
- 外部编辑生成 ExternalChange；
- 未批准内容不进入检索。

## 检索

- 精确、FTS、metadata 可用；
- Weighted RRF 可解释；
- Context Bundle 四层输出；
- profile 可切换；
- canonical 冲突产生 warning 或阻断；
- relation depth 与 token budget 生效。

## Git

- 单节点批准一个 commit；
- 回滚产生新 revision 和新 commit；
- 外部 Git 修改不自动发布；
- dirty tree 状态可见。

## Library

- Library 发布 Snapshot 可被项目锁定；
- lock 记录 version/tag/commit/manifest；
- Library 更新不自动影响项目；
- 升级需报告与批准。

## 恢复

- 可导出 `.rhine`；
- 可在临时目录验证；
- SQLite 删除后可重建当前正式节点；
- 向量索引删除后系统仍可运行；
- inconsistent 状态阻止发布。


# Phase 1.5 补充验收

- 可通过极简 UI 创建或导入节点；
- 可保存 staging；
- 可人工批准；
- 已批准节点可被 FTS 检索；
- 可生成 Context Bundle v0；
- FakeLLM 可完成端到端集成测试；
- OpenAI-compatible Provider 可选启用；
- UI 显示引用来源；
- 未配置真实 LLM 时系统仍可完整测试；
- 不依赖 ChromaDB；
- 不提前实现正式 Git 事务和 MCP。


# Knowledge Capture 验收

## 对话录入

- 用户可提交一段对话；
- 系统生成 Capture Proposal；
- 候选节点可编辑；
- 来源 session/message 范围可追溯；
- 未批准候选不进入正式检索；
- 批准后可被搜索和引用。

## 文档导入

- 支持 Markdown/TXT；
- 文件 hash 被记录；
- heading path 与 line range 可追溯；
- 可批量审核；
- 同一文件重复导入可被识别。

## 项目导入

- 支持本地目录扫描；
- ignore 规则生效；
- 文件树可预览和筛选；
- Source Index 与 Curated Knowledge 分离；
- 至少可生成项目概览、模块说明和约束候选。

## LLM

- FakeLLM 完成端到端测试；
- 真实 LLM 未配置时不影响系统测试；
- 回答显示引用节点和来源。


# Phase 2 Formal Workflow 验收

- staging 批准前会执行 validation；
- staging / ExternalChange 可生成结构化 diff；
- 人工批准会生成 ChangeSet；
- 节点变更会生成 NodeRevision；
- base_revision 冲突会被阻止；
- 批准后的正式知识会同步 Markdown 与 SQLite；
- 批准后的变更会生成 Git commit；
- 批准、拒绝、回滚和外部变更处理会生成 AuditEvent；
- 回滚生成新的 revision，而不是覆盖历史 revision；
- 外部 Markdown 变更会进入 ExternalChange 审批入口；
- 正式批准后创建 IndexJob；
- 未批准内容仍不得进入正式检索。


# Phase 3 Formal Retrieval 验收

- Retrieval Profile 提供技术文档、世界观和 AI 知识库默认预设；
- 单次检索可选择 profile，并且服务端强制关系深度和结果数上限；
- exact、metadata、SQLite FTS 三个候选通道可用；
- vector channel 在 Phase 3 不启用，并在 explain trace 中说明原因；
- Weighted RRF 融合记录每个 channel 的 rank、weight、raw_score 和 contribution；
- 规则重排覆盖 exact match 与 authority；
- archived、deprecated、superseded 节点不会静默混入普通上下文；
- `conflicts_with` 和 `supersedes` 关系会生成 warning；
- 一跳关系扩展可用，`related_to` 默认不自动扩展；
- Context Bundle 输出 mandatory_constraints、relevant_context、supporting_references、warnings 和 explain_trace；
- Retrieval Lab UI 可展示 profile、通道候选、融合排名、过滤结果、关系扩展和最终 Context Bundle；
- 未批准 staging 和 ExternalChange 内容仍不得进入正式检索。


# Phase 4 Formal UI and MCP 验收

- 默认 core-only 安装不依赖 MCP SDK、FastAPI、uvicorn 或前端工具链；
- MCP SDK 只通过 `rhine-vault[mcp]` 可选启用；
- `GET /api/mcp/capabilities` 能列出工具白名单、资源模板和 forbidden tools；
- MCP read tools 只读取已批准 formal MemoryNode、Context Bundle、bounded local graph 或 schema metadata；
- MCP candidate write tools 只能提交或修订 pending staging candidate；
- MCP 不提供批准 staging、直接写正式节点、删除节点、raw SQL、任意文件读取、Git commit 或 Library publish；
- `rhine://workspace/{workspace_id}/node/{node_id}` 只返回正式节点；
- `rhine://workspace/{workspace_id}/graph/{node_id}?depth=1` 只返回 bounded one-hop graph；
- 未批准 staging 内容不会进入 `search_nodes` 或 `get_related_context`；
- SDK 未安装时 API server 仍可启动，并报告 MCP HTTP 挂载不可用原因。
