# Phase 3 — Formal Retrieval

## 目的

Phase 3 将 Phase 2 产生的正式 MemoryNode 推进为可解释、可配置、可测试的检索链路。

Phase 2 已验证：

```text
Capture Proposal / ExternalChange
→ Staging
→ Validation
→ Diff
→ Human Approval
→ ChangeSet
→ NodeRevision
→ Markdown + SQLite
→ Git Commit
→ AuditEvent
→ IndexJob
```

Phase 3 要补齐正式检索需要的 profile、候选召回、融合排名、规则重排、关系扩展、状态过滤、冲突 warning 与 Context Bundle explain trace。

## 核心链路

```text
query
→ Retrieval Profile
→ exact / metadata / FTS candidates
→ Weighted RRF fusion
→ rule reranking
→ lifecycle and conflict filtering
→ one-hop relation expansion
→ Context Bundle layers
→ explain trace
```

## 必须实现

### Retrieval Profile

- 提供技术文档、世界观、AI 知识库三个默认预设。
- Profile 记录通道权重、RRF k 值、关系深度、结果预算、冲突策略和 Context Bundle 分层预算。
- 单次请求可覆盖非危险参数, 但服务端必须强制硬上限。

### Candidate Channels

- Exact channel: NodeID、标题短语、关键词精确匹配。
- Metadata channel: node_type、authority、tags、title。
- FTS channel: SQLite FTS5 正文全文检索。
- Vector channel 在 Phase 3 不接 ChromaDB, 只能作为 disabled/explain 占位。

### Weighted RRF

- 不直接相加不同通道原始分数。
- 使用 `score = Σ weight / (k + rank)` 融合。
- explain trace 必须记录每个 channel 的 rank、weight 和贡献。

### Rule Reranking

- exact match bonus；
- authority bonus；
- deprecated / archived penalty 或排除；
- superseded 节点应进入 warning 或替代说明；
- unresolved conflicts 不得静默选边。

### Relation Expansion

- 默认深度 1；
- 服务端硬上限不超过 2；
- Phase 3 只做一跳基础扩展；
- `related_to` 默认不自动扩展；
- `depends_on`、`implements`、`extends`、`supersedes`、`conflicts_with` 优先。

### Context Bundle

必须输出：

- `mandatory_constraints`
- `relevant_context`
- `supporting_references`
- `warnings`
- `explain_trace`

每个纳入项应记录 node_id、score、source channel、profile、revision 和纳入原因。

### Retrieval Lab UI

必须展示：

- 选用的 Retrieval Profile；
- 每个通道候选；
- Weighted RRF 融合排名；
- 状态过滤和冲突 warning；
- 关系扩展；
- 最终 Context Bundle；
- 纳入和排除原因。

## 禁止提前实现

- MCP stdio / Streamable HTTP；
- ChromaDB / 生产向量索引；
- 生产级图谱 UI；
- Library 发布；
- PDF/DOCX/OCR；
- 完整 Obsidian 插件；
- 云端同步；
- Redis / PostgreSQL / Neo4j。

## 成功条件

```text
approved MemoryNode
→ exact / metadata / FTS candidates
→ Weighted RRF
→ rule reranking
→ relation expansion
→ Context Bundle
→ explain trace
```

并且：

- 未批准 staging 和 ExternalChange 内容不得进入检索；
- workspace_id 始终显式过滤；
- ranking 可解释；
- profile 可配置；
- deprecated / superseded / conflicting 内容不静默混入正常上下文；
- 测试覆盖 ranking、filtering、profile 和 explain trace。

## 本轮实现记录

- 新增 `src/rhine_vault/retrieval.py` 作为 Phase 3 正式检索服务。
- 提供 `technical-documentation`、`worldbuilding`、`semantic-knowledge-base` 三个默认 Retrieval Profile。
- 正式检索使用 exact、metadata、SQLite FTS 三个本地候选通道；vector channel 在 explain trace 中显式标记为 disabled。
- 使用 Weighted RRF 融合候选，记录每个 channel 的 rank、weight、raw_score 和 contribution。
- 增加 authority / exact-match 规则加分，并对 archived、deprecated、superseded 节点执行过滤或 warning。
- 增加一跳关系扩展，默认跳过 `related_to`，优先 `depends_on`、`implements`、`extends`、`supersedes`、`conflicts_with` 等关系。
- Context Bundle 现在包含 retrieval profile 与 explain trace，并在纳入项记录 score、source channel、revision 和 include reason。
- SQLite `memory_nodes` 兼容迁移新增 `status` 与 `relations_json`，老数据默认 `active` 与空关系。
- 新增 Retrieval Lab API 与 UI 控件，用于查看 channel candidates、fused ranking、filtered items、relation expansion 和最终 Context Bundle。
- 新增 Phase 3 测试覆盖 ranking/profile/explain trace、filtering/conflict warning/relation depth 和 FastAPI Retrieval Lab。
- 完成 `conflict_strategy=block` 行为：技术文档 profile 会阻止冲突节点同时进入普通上下文，并在 filtered/explain 中记录原因。
- 关系扩展纳入项现在显式标记 `source_channels=["relation_expansion"]`。
- 内置 WebUI 增加 Retrieval Lab 面板，可选择 profile、结果数、关系深度和过滤参数，并调用 `/api/retrieval/lab` 查看完整 explain trace。
