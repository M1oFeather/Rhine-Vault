# 备份、恢复与灾难恢复

## 数据分级

### 核心数据

- 正式 Markdown
- Git 完整历史
- SQLite
- staging
- ExternalChange
- 工作区配置
- Schema
- Retrieval/Chunking Profile
- Lock 与 Manifest
- assets

### 可重建数据

- Chunk
- FTS
- relation index
- ChromaDB
- 派生摘要
- 缓存

## Snapshot Orchestrator

```text
暂停新发布
→ 等待写事务结束
→ SQLite checkpoint
→ 记录 Git HEAD
→ 生成 Manifest
→ 打包
→ 计算校验和
→ 验证
→ 恢复写入
```

## 备份类型

- Full Snapshot
- Workspace Snapshot
- Incremental Snapshot
- Emergency Snapshot

## .rhine 包

`.rhine` 是可移植备份格式，至少包含：

- manifest.yaml
- checksums.sha256
- metadata.sqlite
- Git bundle
- working tree
- staging
- external changes
- configs
- assets
- library locks

## 导入

导入必须：

- 校验包与文件 hash；
- 检查 Schema；
- 检查 Workspace ID；
- 检查 Git 历史；
- 生成 Import Plan；
- 在临时区验证；
- 用户确认后正式挂载。

## 降级模式

- 向量索引损坏：降级为精确 + FTS；
- SQLite 损坏：Emergency Read-Only；
- Git 损坏：冻结写入并恢复；
- 三方不一致：inconsistent；
- 严重损坏：recovery_required。

## 健康状态

- healthy
- degraded
- read_only
- inconsistent
- recovery_required

## 自动备份

建议默认：

- 每日增量；
- 每周完整；
- Migration 前强制；
- Library 升级前强制；
- 破坏性操作前强制。

## 加密与验证

支持成熟加密工具，不自行设计算法。每个快照必须可执行恢复演练。
