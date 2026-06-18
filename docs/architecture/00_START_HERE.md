# Rhine-Vault v0.5 架构总览

## 定位

Rhine-Vault 是本地优先、数据主权优先的无头知识图谱与检索引擎。

## 权威分层

- Markdown：已批准正式知识内容；
- SQLite：审核、工作流、审计、revision 与状态；
- Git：Vault 级不可无痕改写的版本历史；
- ChromaDB：可重建向量索引。

未审批的磁盘修改不是正式知识。

## 知识写入

```text
编辑
→ unsaved
→ 保存为 staging
→ 校验和 Diff
→ 人工批准
→ revision
→ Markdown
→ SQLite
→ Git commit
→ IndexJob
```

外部编辑器、Obsidian 和外部 Git 修改统一进入 ExternalChange 审批。

## 核心模型

- Workspace
- MemoryNode
- NodeRelation
- StagingEntry
- ChangeSet
- NodeRevision
- ExternalChange
- IndexJob
- AuditEvent
- RetrievalProfile
- ChunkingProfile

## 检索

```text
精确检索 + FTS + 向量 + metadata
→ Weighted RRF
→ 规则重排
→ 关系扩展
→ 冲突和状态过滤
→ Context Bundle
```

Context Bundle 分为：

- Mandatory Constraints
- Relevant Context
- Supporting References
- Warnings

## Chunking

- MemoryNode 是审核单位；
- Chunk 是确定性派生检索单位；
- Markdown AST 与标题层级优先；
- 代码块、表格和列表尽量原子化；
- Chunk 与 Node Revision 强绑定。

## 多场景配置

Retrieval Profile 和 Chunking Profile 支持：

- 技术文档；
- 世界观；
- AI 知识库；
- 用户自定义。

UI 提供检索实验台、评分拆解和版本追踪。

## 关系

- 正式 outgoing relation 写入 Markdown；
- SQLite 保存可重建边索引；
- incoming edge 动态生成；
- 关系类型由 Schema 约束；
- supersedes 具有特殊系统语义。

## 版本

- 每次正式变更产生新 revision；
- 回滚也产生新 revision；
- NodeID 发布后不可原地修改；
- Git 是内置能力；
- ChangeSet 对应原子审批与 commit。

## 工作区与 Library

- Project 与 Library 分离；
- 跨工作区依赖显式声明；
- Library 只读发布快照；
- SemVer + Tag + Commit + Manifest；
- requested 与 resolved lock 分离；
- 项目可定义显式 override。

## 权限

- 单用户也区分 User 与 Actor；
- viewer/editor/reviewer/admin；
- Agent 采用 Capability 和 Workspace Scope；
- Agent 不得批准、发布、回滚或执行 Git。

## Obsidian

- 保证 Markdown、Frontmatter、Wiki Link 兼容；
- UI 中作为可选集成；
- 不是核心依赖；
- Obsidian 修改必须审批。
