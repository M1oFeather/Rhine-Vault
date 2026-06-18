# Rhine-Vault V1.0 最终实施范围

## 必须实现

### 核心模型

- Workspace
- MemoryNode
- NodeRelation
- NodeRevision
- StagingEntry
- ChangeSet 基础结构
- ExternalChange
- IndexJob
- AuditEvent
- RetrievalProfile
- ChunkingProfile
- ActorContext

### 存储与版本

- Markdown + YAML
- SQLite
- Git 内置提交
- `.history`
- `.archive`
- approved hash
- base_revision 乐观锁

### 审批

- UI unsaved 状态
- 保存为 staging
- Diff
- 校验
- 批准/驳回
- 新 revision
- Git commit
- IndexJob
- 外部修改审批

### 检索

- 精确匹配
- SQLite FTS5
- metadata 检索
- Weighted RRF
- 规则重排
- 一层关系扩展
- Context Bundle
- Retrieval Profile
- Chunking Profile

### 接口

- REST
- MCP stdio
- MCP Streamable HTTP
- 动态 Tool Capability
- workspace 强隔离

### 工作区

- Project Workspace
- Library Workspace 基础结构
- 显式依赖
- rhine-lock.yaml
- Published Snapshot 读取
- 不做传递依赖自动解析

### Git

- 批准 commit
- 回滚 commit
- ChangeSet commit
- working tree 检测
- 外部 Git 变更转审批

### Obsidian

- Markdown/Frontmatter/Wiki Link 兼容
- UI 中可选“打开工作区/节点”
- 外部修改检测

### 恢复

- Workspace Snapshot
- Full Snapshot 基础版
- `.rhine` 导出
- Import Plan
- Emergency Read-Only
- 派生索引重建

## 明确推迟

- 全局图谱
- 多用户认证平台
- 复杂传递依赖解析
- 自动 LLM 重排
- 自动 AI 批准
- 分布式任务队列
- 云端同步平台
- 完整 Obsidian 插件
- Neo4j
- Redis
- PostgreSQL
