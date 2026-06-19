# Phase 2 — Formal Workflow

## 目的

Phase 2 将 Phase 1.5 的开发者垂直切片推进为正式工作流。

Phase 1.5 已验证：

```text
Source
→ Capture Proposal
→ Review
→ Staging
→ Approve
→ FTS
→ Context Bundle
→ Fake/Real LLM
```

Phase 2 要补齐正式产品必须具备的审批、版本、审计、diff、Git 和外部修改处理能力。

## 核心链路

```text
unsaved / proposal
→ staging
→ validation
→ diff
→ human approval
→ ChangeSet
→ NodeRevision
→ Markdown
→ SQLite
→ Git commit
→ AuditEvent
→ IndexJob
```

任何 UI、Agent、外部编辑器、脚本或未来 MCP 能力都不得绕过该链路。

## 必须实现

### ChangeSet

- 每次人工批准形成一个 ChangeSet。
- ChangeSet 表达一次原子审批意图。
- ChangeSet 记录 workspace_id、actor、staging entries、diff summary、status、created_at、approved_at。
- ChangeSet 后续对应 Git commit。

### NodeRevision

- 每次正式节点变更生成新 revision。
- revision 不覆盖旧 revision。
- 回滚也生成新 revision。
- NodeRevision 记录 base_revision、content hash、frontmatter hash、source refs、ChangeSet。

### Validation

- 批准前必须校验：
  - workspace_id 一致；
  - node_id 合法；
  - node_type 存在或已获批准；
  - relation type 合法；
  - base_revision 未冲突；
  - 未批准内容不进入正式检索。

### Diff

- staging 到正式知识必须生成结构化 diff。
- ExternalChange 必须生成结构化 diff。
- Phase 2 diff 允许是基础字段级 diff，不要求完整语义 diff UI。

### Git

- Git 是内置版本层。
- 批准 ChangeSet 后必须生成 Git commit。
- commit message 必须能追溯 ChangeSet。
- Agent 不得直接执行批准或发布；Git commit 只能由人工批准后的服务流程触发。

### AuditEvent

- 记录 proposal 创建、staging 保存、validation、approval、rejection、Git commit、rollback、ExternalChange review。
- AuditEvent 必须显式携带 workspace_id 与 actor。

### ExternalChange

- 外部 Markdown / Git 修改不得直接进入正式知识。
- 检测到外部变化后生成 ExternalChange。
- ExternalChange 进入 review，批准后才可成为 ChangeSet。

### IndexJob

- 正式批准后创建 IndexJob。
- Phase 2 只要求创建和状态记录。
- Chunk / FTS / Vector 仍是可重建派生数据。

## UI 要求

UI 需要展示：

- ChangeSet 审核信息；
- validation 结果；
- diff 摘要；
- revision 信息；
- audit trail 基础信息；
- ExternalChange 待审项。

图谱式节点连线面板可以保留入口或设计占位，但不在 Phase 2 实现。

## 禁止提前实现

- MCP stdio / Streamable HTTP；
- ChromaDB / 向量索引；
- Weighted RRF 正式检索；
- 生产级图谱 UI；
- Library 发布；
- PDF/DOCX/OCR；
- 完整 Obsidian 插件；
- 云端同步；
- Redis / PostgreSQL / Neo4j。

## 成功条件

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

并且：

- 空标题、非法 ID、跨 workspace、base_revision 冲突都被阻断；
- 未批准内容不进入正式检索；
- 批准和回滚都可追溯；
- 测试覆盖正式工作流主路径和关键失败路径。
