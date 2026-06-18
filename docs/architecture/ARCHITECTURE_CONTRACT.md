# Rhine-Vault v1.0 架构契约

本文件是实现阶段的最高级项目约束摘要。

## 1. 权威边界

- Markdown：已批准正式知识内容。
- SQLite：工作流、审核、revision、审计、运行状态。
- Git：Vault 级版本历史与不可无痕改写的发布记录。
- FTS/Chunk/ChromaDB：可重建派生索引。

磁盘文件变化不等于正式知识变化。未审批内容不得进入正式检索。

## 2. 写入链

```text
unsaved
→ staging
→ validation
→ diff
→ human approval
→ new revision
→ markdown
→ sqlite
→ git commit
→ index job
```

Agent、插件、Obsidian、外部编辑器、外部 Git 操作均不得绕过此链。

## 3. 工作区

- 所有操作显式携带 workspace_id。
- Project 与 Library 分离。
- 跨工作区访问默认关闭。
- Library 通过显式 dependency、lock 与 published snapshot 使用。
- V1 不实现传递依赖自动解算。

## 4. Agent 边界

Agent 可：

- 读取正式节点；
- 搜索；
- 构建 Context Bundle；
- 提交或修改 staging。

Agent不可：

- 批准；
- 发布；
- 回滚；
- Git commit；
- 修改权限；
- 写正式节点；
- 绕过 workspace scope。

## 5. 检索

- 多通道召回；
- Weighted RRF；
- 规则重排；
- 关系扩展；
- Context Bundle；
- 评分可解释；
- profile 可配置；
- 强制冲突不静默选边。

## 6. Chunk

- Node 是正式知识单位；
- Chunk 是派生检索单位；
- Markdown AST 与标题优先；
- deterministic；
- 与 revision 强绑定。

## 7. 版本

- 每次正式变更产生新 revision；
- 回滚也产生新 revision；
- NodeID 发布后不可原地修改；
- Git 是内置能力；
- ChangeSet 对应原子审批意图。

## 8. 外部修改

- UI 未保存状态不写正式文件；
- UI 保存只进入 staging；
- Obsidian/VS Code/脚本/Git 外部变化进入 ExternalChange；
- 未批准外部修改不得索引。

## 9. 恢复

- `.rhine` 为备份格式；
- 导入先生成 Import Plan；
- 向量损坏可降级；
- SQLite 或 Git 异常进入只读/恢复模式；
- Migration 和破坏性操作前必须快照。

## 10. 变更控制

违反本契约的实现不得合并。需要变更时，先新增 ADR，再更新冻结包。
