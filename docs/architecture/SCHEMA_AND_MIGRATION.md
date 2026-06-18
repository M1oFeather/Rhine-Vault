# Schema 与旧 Vault 迁移规范

## 独立版本

分别管理：

- Workspace Schema
- MemoryNode Schema
- RelationType Schema
- RetrievalProfile Schema
- ChunkingProfile Schema
- LibraryManifest Schema
- LockFile Schema
- SQLite Schema
- API Version

应用版本不得与数据 Schema 版本混为一谈。

## 兼容策略

每类 Schema 声明：

- min_readable
- max_readable
- writable

旧版本允许只读兼容；一旦要修改，必须迁移到当前 writable 版本。

## Canonical Internal Model

各版本 Parser 将旧格式转换为统一内部模型。业务层只操作内部模型，不分散处理历史版本。

## Migration 类型

- 无损结构迁移；
- 需要人工确认的推断迁移；
- 破坏性迁移。

所有 Migration 先生成 Migration Plan 和 ChangeSet，不直接修改正式知识。

## Git 流程

```text
检查 working tree
→ 创建 migration branch
→ 生成 ChangeSet
→ 校验与预览
→ 人工批准
→ commit
→ 合并主分支
→ 重建派生索引
```

## SQLite

数据库结构迁移使用 Alembic；Markdown、配置、Library 与关系迁移使用 Rhine Migration Orchestrator。

## 索引

Chunk、FTS、ChromaDB 为派生数据，Schema 不兼容时优先重建。

## Library

已发布 Snapshot 不原地迁移。应在工作树迁移后发布新的 Library 版本。

## 不可逆迁移

必须：

- 创建完整 Snapshot；
- 标记 reversible=false；
- 明确恢复方式；
- 不承诺自动反向迁移。
