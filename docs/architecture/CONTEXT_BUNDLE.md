# Context Bundle 任务上下文规范

## 目标

Agent 执行任务时不直接消费未经整理的搜索结果，而由 Rhine-Vault 生成结构化上下文包。

## 四层结构

1. `mandatory_constraints`：不可违反的规范、契约和冻结决策。
2. `relevant_context`：与任务直接相关但非强制的背景。
3. `supporting_references`：示例、历史记录和辅助材料。
4. `warnings`：冲突、废弃、缺失依赖、索引不完整等风险。

## 默认检索与组装流程

```text
任务解析
→ 精确标识符匹配
→ 全文检索
→ 向量检索
→ 候选融合与去重
→ 关系扩展
→ 状态过滤
→ 冲突检测
→ 优先级排序
→ 按预算裁剪
→ Context Bundle
```

## 关系扩展

- 默认深度：1；
- 可由 Retrieval Profile 调整；
- 服务端必须设置硬上限；
- `depends_on`、`implements`、`extends`、`supersedes`、`conflicts_with` 优先；
- `related_to` 默认不自动扩展。

## 状态规则

- `active`：默认允许进入；
- `deprecated`：仅进入 warning；
- `superseded`：返回替代节点；
- `archived`：默认排除；
- `staging`：正式 Agent 检索默认绝对排除。

## 冲突规则

强制约束发生未解决冲突时，系统不得自行选边。可根据 Profile：

- 阻止自动执行；
- 降级为只读建议；
- 返回双方及冲突说明。

## 预算策略

按优先级分配，而不是简单尾部截断：

- Mandatory：最高优先级；
- Relevant：次高；
- Supporting：优先裁剪；
- Warnings：必须保留关键风险。

## 可追溯性

每个 Bundle 记录：

- workspace_id；
- retrieval_profile_id 与 revision；
- query/task；
- 命中节点与评分；
- 关系扩展路径；
- 排除原因；
- token 预算与裁剪结果。
