# 分阶段实施计划 v1.1

## Phase 0：仓库与质量基线

- Python 3.12+
- src layout
- pytest
- ruff
- mypy
- pre-commit
- CI
- AGENTS.md

## Phase 1：领域、Schema 与 Markdown

- Pydantic 模型
- Schema
- Markdown parser/serializer
- path resolver
- deterministic chunking
- unit tests

## Phase 1.5：Knowledge Capture Vertical Slice

目标：尽早验证知识采集、审核、检索和问答闭环。

### 四种入口

1. 手动录入
2. 对话录入
3. Markdown/TXT 文档导入
4. 本地项目目录扫描

### 最小后端

- 单 Workspace
- 最小 Node Repository
- 最小 SQLite
- SourceRecord
- CaptureProposal
- 简化 staging
- 简化 approve
- 基础 FTS5
- Context Bundle v0

### 对话录入

- 会话消息输入
- AI 候选节点提取
- 候选关系
- 来源消息范围
- 人工修改
- staging / approve

### 文档导入

- `.md`
- `.txt`
- 章节解析
- 候选拆分
- 批量审核
- 文件 hash 和来源位置

### 项目导入

- 本地目录选择
- `.gitignore` / ignore 规则
- 文件树预览
- 用户选择范围
- README / Markdown / 配置 / 源码结构提取
- Source Index 与 Curated Knowledge 分离

### LLM

- `LLMProvider` 抽象
- `FakeLLMProvider`
- OpenAI-compatible Provider
- 自动测试不依赖真实 LLM

### 极简 UI

- Workspace
- Manual Node Editor
- Conversation Capture
- Document Import
- Project Import
- Capture Proposal Review
- Search Lab
- Context Bundle Viewer
- LLM Playground

### 成功条件

```text
对话 / 文档 / 项目
→ Capture Proposal
→ Review
→ Staging
→ Approve
→ FTS
→ Context Bundle
→ Fake/Real LLM
→ 查看来源
```

## Phase 2：正式工作流

- 完整 revision
- Git commit
- AuditEvent
- ExternalChange
- base_revision
- compensation transaction
- full diff

## Phase 3：正式检索

- Weighted RRF
- rule reranking
- relation expansion
- Retrieval Profile
- Retrieval Lab
- explain trace

## Phase 4：正式 UI 与 MCP

- production UI
- MCP stdio
- Streamable HTTP
- dynamic capabilities
- Obsidian optional integration

## Phase 5：Library 与跨工作区

- Project/Library
- published snapshot
- manifest
- lock file
- dependency upgrade report

## Phase 6：向量、迁移与恢复

- EmbeddingProvider
- Chroma adapter
- `.rhine`
- snapshot/import
- migration center
- recovery mode
