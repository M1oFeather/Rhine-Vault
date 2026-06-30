# 架构决策记录

状态定义：

- **已确定**：可直接作为实现约束。
- **暂定**：当前推荐方案，但后续允许调整。
- **待讨论**：代码 Agent 不得自行定案。
- **已取代**：历史决策，仅作为背景记录，不再作为当前实现约束。

| ID | 决策 | 状态 | 说明 |
|---|---|---|---|
| ADR-001 | Rhine-Vault 为无头知识引擎，不承担聊天前端 | 已确定 | 客户端与数据底座解耦 |
| ADR-002 | 所有操作显式指定 workspace_id | 已确定 | 默认禁止跨域污染 |
| ADR-003 | 正式知识使用 Markdown + YAML | 已确定 | 保证可读、可迁移 |
| ADR-004 | 新知识先进入 `.staging` | 已确定 | 未审批内容不进入正式索引 |
| ADR-005 | AI 不得直接批准正式节点 | 已确定 | Human-in-the-loop |
| ADR-006 | ChromaDB 是派生索引 | 已确定 | 可删除、可重建 |
| ADR-007 | 使用 SQLite 管理工作流与审计 | 暂定 | V1 轻量实现 |
| ADR-008 | MCP 使用 stdio + Streamable HTTP | 已确定 | 不以旧 HTTP+SSE 为主 |
| ADR-009 | 使用官方 MCP Python SDK | 已确定 | 避免自实现协议 |
| ADR-010 | FastAPI 与 MCP 服务共享进程 | 暂定 | 可通过 ASGI 挂载 |
| ADR-011 | MemoryNode 为统一核心模型 | 已确定 | 业务类型通过 node_type 扩展 |
| ADR-012 | 关系必须带 type | 已确定 | 避免无语义边 |
| ADR-013 | Markdown 内容与 SQLite 状态的真源边界 | 待讨论 | 需定义恢复和冲突规则 |
| ADR-014 | 节点粒度 | 待讨论 | 过大影响检索，过小增加维护成本 |
| ADR-015 | 正式节点是否允许缺失关系目标 | 待讨论 | 可选择严格或软引用 |
| ADR-016 | 向量模型首选 | 暂定 | 需考虑中英文与代码检索 |
| ADR-017 | V1 是否立即接入 ChromaDB | 待讨论 | 可先完成 BM25/FTS5 |
| ADR-018 | 自动 Chunk 策略 | 待讨论 | 标题层级优先或固定窗口 |
| ADR-019 | 节点历史版本保留方式 | 暂定 | `.archive` + audit log |
| ADR-020 | UI 技术栈采用独立 Element Plus / Vite 客户端 | 已确定 | Element UI 独立于 core；内置 WebUI 继续保留；FastAPI docs 只作为接口文档 |
| ADR-021 | Agent 使用结构化 Context Bundle，不直接消费原始搜索结果 | 已确定 | 分 Mandatory、Relevant、Supporting、Warnings |
| ADR-022 | 关系扩展默认深度 1，并按 Profile 可调 | 已确定 | 服务端设置最大上限 |
| ADR-023 | 强制规则冲突不得静默选边 | 已确定 | 可阻断执行或降级只读 |
| ADR-024 | 检索参数由 Retrieval Profile 管理 | 已确定 | 一个工作区可有多个 Profile |
| ADR-025 | UI 提供技术文档、世界观、AI 知识库预设 | 已确定 | 支持高级自定义与实验台 |
| ADR-026 | 检索采用 Weighted RRF 融合 | 已确定 | 不直接相加不同检索器原始分数 |
| ADR-027 | 引入 authority 字段 | 已确定 | canonical/approved/reference/historical/experimental |
| ADR-028 | Chunk 为可重建派生数据，不是正式知识实体 | 已确定 | 与 Node Revision 强绑定 |
| ADR-029 | Chunking 使用 Markdown AST 与标题层级优先 | 已确定 | 代码块、表格、列表尽量保持原子 |
| ADR-030 | 基础 Chunking 必须确定性 | 已确定 | AI 只参与可选摘要与语义增强 |
| ADR-031 | 每次正式知识变更生成新 revision，不允许无历史覆盖 | 已确定 | 回滚也生成新 revision |
| ADR-032 | Git 是 Rhine-Vault 内置版本层 | 已确定 | 每次批准、回滚、ChangeSet 对应提交 |
| ADR-033 | NodeID 发布后不可原地修改 | 已确定 | 改名通过新节点与 supersedes |
| ADR-034 | UI 编辑先进入 unsaved，再保存为 staging | 已确定 | 保存不等于发布 |
| ADR-035 | 外部 Markdown/Git 修改必须进入 ExternalChange 审批 | 已确定 | 未批准内容不得污染索引 |
| ADR-036 | 内容不一致必须分类处理，不能一律 Markdown 覆盖数据库 | 已确定 | 派生索引可自动重建 |
| ADR-037 | Markdown relations 是已批准关系内容源，SQLite 为派生边索引 | 已确定 | 反向边动态计算 |
| ADR-038 | Obsidian 作为兼容且可选的 UI 集成 | 已确定 | 非核心依赖，不可绕过审批 |
| ADR-039 | 工作区分为 Project 与 Library | 已确定 | Library 默认只读供下游依赖 |
| ADR-040 | 跨工作区检索必须显式声明 dependency | 已确定 | 默认禁止全局跨库搜索 |
| ADR-041 | 项目可声明本地 override，但必须展示原规则 | 已确定 | 不静默覆盖 Library |
| ADR-042 | V1 默认每工作区独立 Git 仓库 | 已确定 | Library 独立发布 |
| ADR-043 | 单用户模式仍区分 User 与 Actor | 已确定 | UI、Agent、Git、Indexer 分开审计 |
| ADR-044 | Agent 使用 Capability 与 Workspace Scope | 已确定 | 不继承管理员权限 |
| ADR-045 | Library 采用 SemVer + Git Tag + Commit + Manifest | 已确定 | 发布版本不可变 |
| ADR-046 | workspace.yaml 记录 requested，rhine-lock.yaml 记录 resolved | 已确定 | 依赖升级需审批 |
| ADR-047 | Library 工作树与发布快照分离 | 已确定 | 下游只读取发布快照 |
| ADR-048 | V1 不实现传递依赖自动解析 | 已确定 | 所有 Library 显式声明 |
| ADR-049 | 各类 Schema 独立版本化 | 已确定 | 应用、Markdown、SQLite、API 版本分离 |
| ADR-050 | 旧 Schema 可只读兼容，写入前必须迁移 | 已确定 | 业务层使用 Canonical Internal Model |
| ADR-051 | Migration 通过 ChangeSet 与 Git 分支执行 | 已确定 | 不直接无审核改正式知识 |
| ADR-052 | 派生索引优先重建而不是迁移 | 已确定 | Chunk/FTS/Vector 可重建 |
| ADR-053 | 采用统一 Snapshot Orchestrator | 已确定 | 不直接复制运行中目录 |
| ADR-054 | 使用 .rhine 作为可移植备份包 | 已确定 | 包含 Manifest 与校验和 |
| ADR-055 | 导入必须先生成 Import Plan | 已确定 | 不直接覆盖现有工作区 |
| ADR-056 | 系统支持健康状态机 | 已确定 | healthy/degraded/read_only/inconsistent/recovery_required |
| ADR-057 | Codex Handoff Package 与数据恢复包分离 | 已确定 | 一个用于开发，一个用于数据恢复 |
| ADR-058 | Rhine-Vault 必须支持 core-only 安装 | 已确定 | 默认 pip 安装不强制 FastAPI、uvicorn 或前端工具链；API server 作为可选 extra |
| ADR-059 | 产品层级分为 Core / API / WebUI / Desktop | 已确定 | Core 最小可嵌入；WebUI 可扩展；Desktop 是完整本地工作台 |
| ADR-060 | Novel Studio 作为 WebUI/Desktop 插件实现 | 已取代 | 被 ADR-061 取代；保留为历史背景 |
| ADR-061 | Rhine-Lore 从 Rhine-Vault runtime 中拆出 | 已确定 | 长篇创作工作台独立成产品/仓库；Rhine-Vault 保持审计知识后端，通过 API/Context Bundle/Proposal 链路服务 Lore |
