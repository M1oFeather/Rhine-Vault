# Chunking 与节点正文规范

## 基本定义

- MemoryNode：人工审核、维护和引用的知识单元。
- Chunk：为检索生成的可删除、可重建派生片段。

Chunk 不拥有业务 NodeID，不允许 Agent 直接修改。

## 分块流程

```text
Markdown AST
→ 标题层级拆分
→ 块类型识别
→ 超长块二次拆分
→ 语义上下文补全
```

## 原子块

尽量保持完整：

- fenced code block；
- Markdown 表格；
- 层级列表；
- 引用块；
- 警告与约束块；
- 数学公式。

## 元数据

每个 Chunk 至少保存：

- chunk_id；
- workspace_id；
- node_id；
- node_revision；
- heading_path；
- chunk_type；
- sequence；
- token_count；
- source line range；
- chunking_profile_id 与 revision；
- parser_version。

## 语义重叠

不使用机械固定 overlap 作为首选，而是重复：

- 标题路径；
- 父级摘要；
- 必要的前后逻辑句；
- 结构上下文。

## Chunking Profile

### technical

- 目标块较小；
- 代码块与接口原子化；
- target 约 450 tokens；
- max 约 900 tokens。

### worldbuilding

- 目标块较大；
- 保持事件因果和人物动机；
- target 约 700 tokens；
- max 约 1400 tokens。

### semantic-kb

- 块较短；
- 适合问答；
- target 约 350 tokens；
- max 约 700 tokens。

具体数值由 UI 和实验台调整，服务端设硬上限。

## 返回策略

- `get_node`：完整节点；
- `search_nodes`：摘要与最佳命中 Chunk；
- `build_task_context`：根据 authority、长度和预算决定完整节点、局部 Chunk 或摘要。

## 版本绑定

Chunk 必须与 Node Revision 强绑定。节点更新后旧 Chunk 不得混入新版本正式结果。

## 确定性

相同 Node、Revision、Chunking Profile 和 parser version 应产生相同 Chunk。基础分块不得依赖 LLM。

## 语义块

正文支持显式标记：

- constraint；
- warning；
- example；
- rationale；
- deprecated；
- note。

这些标记用于 Context Bundle 分层。
