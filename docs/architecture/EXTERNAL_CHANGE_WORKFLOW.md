# UI 与外部编辑审批流程

## 核心原则

Markdown 是已批准知识的权威载体，但磁盘文件发生变化并不自动成为正式知识。

正式状态由以下三者共同校验：

- approved revision；
- approved content hash；
- Git commit。

## UI 编辑状态

```text
clean
→ editing
→ unsaved
→ staging_saved
→ pending_approval
→ approved/publishing
→ indexed
```

用户在 UI 内编辑时：

- 未点击保存：只存在于前端或本地恢复状态；
- 点击“保存草稿”：进入 staging；
- 点击“批准并发布”：新 revision、正式 Markdown、SQLite、Git、IndexJob。

“保存草稿”和“批准并发布”必须是两个独立业务动作。

## 外部修改

Obsidian、VS Code、脚本、外部 Git 操作对正式 Markdown 的修改：

```text
检测 hash 变化
→ 创建 ExternalChange
→ 保存外部内容快照
→ 恢复或继续提供最后批准版本
→ 生成 Diff
→ 等待审批
```

未批准外部内容不得进入正式索引或 Agent 上下文。

## 内部写入识别

系统受控写入需登记：

- operation_id；
- expected_hash；
- node_id；
- expires_at。

watchdog 收到事件后，只有 hash 与 pending write 一致时才认定为内部写入。

## 不一致分类

- `expected_internal_write`：等待事务完成；
- `external_content_change`：进入审批；
- `metadata_index_stale`：自动重建派生索引；
- `database_revision_ahead`：高危错误，阻止写入；
- `git_history_mismatch`：仓库进入 inconsistent 状态。

## 三方合并

审批外部修改时比较：

- Base：外部编辑开始时批准版本；
- External：外部内容；
- Current：当前最新批准版本。

若 Base 与 Current 不同，必须进入三方合并。
