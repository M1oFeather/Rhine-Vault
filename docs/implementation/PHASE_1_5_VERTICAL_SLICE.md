# Phase 1.5 — Knowledge Capture Vertical Slice

## 核心目标

验证 Rhine-Vault 最核心的用户价值：

```text
通过对话、文档或现有项目录入知识，
经过人工审核后，
能够被搜索、组装为 Context Bundle，
并用于 LLM 回答。
```

## 术语

### Source

原始输入：

- conversation
- document
- project file
- manual input

### Capture Proposal

AI 或规则系统从 Source 中提取的候选知识。

### MemoryNode

经过人工批准后的稳定正式知识。

## 统一流程

```text
Source
→ Parse / Analyze
→ Capture Proposal
→ Human Review
→ Staging
→ Approve
→ MemoryNode
→ Index
```

## 入口一：手动录入

支持：

- 标题
- NodeType
- authority
- tags
- relations
- Markdown 正文
- 保存 staging
- 批准

## 入口二：对话录入

### 第一版能力

- 用户输入一段或多轮对话；
- 用户明确触发“提取知识”；
- AI 生成候选节点；
- AI 生成候选关系；
- 显示提取理由和置信度；
- 用户编辑；
- 批量保存 staging；
- 人工批准。

### 来源要求

```yaml
source:
  type: conversation
  session_id: ...
  message_ids:
    - ...
  message_range: ...
```

### 原则

- 原始对话不进入默认正式检索；
- 正式检索使用批准后的 MemoryNode；
- 原始对话仅用于追溯和重新提取。

## 入口三：文档导入

### Phase 1.5 格式

- Markdown
- TXT

### 流程

```text
选择文件
→ hash
→ parse
→ section preview
→ split proposal
→ batch review
→ staging
→ approve
```

### 来源要求

- source file path
- source hash
- heading path
- line range

### 暂缓

- PDF
- DOCX
- HTML
- OCR
- 图片理解

## 入口四：项目导入

### Phase 1.5 能力

- 选择本地项目目录；
- 读取 ignore 规则；
- 展示文件树；
- 用户选择导入范围；
- 扫描 README、Markdown、配置文件和源码结构；
- 生成候选项目概览、模块说明、接口、约束和已知问题。

### 双层数据

#### Source Index

原始文件和可搜索 Chunk，用于源码细节查询。

#### Curated Knowledge

经过审核的稳定 MemoryNode。

项目导入不能等于“把全部文件直接变成正式知识”。

### Phase 2 再实现

- 增量扫描
- rename/delete detection
- Git commit source
- file watcher
- source-to-node update impact
- re-import merge
- batch ChangeSet

## 建议数据模型

```python
SourceRecord(
    source_id,
    workspace_id,
    source_type,
    locator,
    content_hash,
    metadata,
)
```

```python
CaptureProposal(
    proposal_id,
    workspace_id,
    source_ids,
    proposed_nodes,
    proposed_relations,
    rationale,
    confidence,
    status,
)
```

```python
ProposedNode(
    temporary_id,
    title,
    node_type,
    content,
    tags,
    authority,
    source_refs,
)
```

```python
ProposedRelation(
    source_temporary_id,
    target_reference,
    relation_type,
    confidence,
)
```

## LLM Provider

实现：

- FakeLLMProvider
- OpenAICompatibleProvider

自动测试必须使用 FakeLLMProvider。

## 极简 UI

至少包含：

1. Workspace
2. Manual Node Editor
3. Conversation Capture
4. Document Import
5. Project Import
6. Proposal Review
7. Search Lab
8. Context Bundle Viewer
9. LLM Playground

## 端到端验收

### Conversation

```text
输入对话
→ 提取两个候选节点
→ 修改其中一个
→ 保存 staging
→ 批准
→ 搜索命中
→ LLM 回答引用该节点
```

### Document

```text
导入 Markdown
→ 按章节生成候选
→ 批量批准
→ 搜索并引用
```

### Project

```text
扫描示例项目
→ 选择 README 和 src
→ 生成项目概览与模块候选
→ 批准
→ 回答项目结构问题
```

## 明确推迟

- 完整 Git 发布事务
- ExternalChange
- MCP
- 多 Workspace
- Library
- Vector Search
- PDF/DOCX
- 实时项目同步
- 正式 UI 设计
