# 架构一致性检查

## 已检查的核心边界

### Markdown / SQLite / Git

无冲突：

- Markdown 保存已批准内容；
- SQLite 保存业务状态与审批；
- Git 保存 Vault 级历史；
- 外部修改不自动生效。

### Revision / Git Commit

无冲突：

- revision 是节点级；
- commit 是仓库级；
- 一个 ChangeSet 可包含多个 revision；
- 回滚不改写历史。

### Staging / UI Save

无冲突：

- unsaved 不进入后端正式状态；
- save 进入 staging；
- approve 才发布。

### Chunk / Node

无冲突：

- Node 是正式知识；
- Chunk 是派生索引；
- Chunk 与 revision 强绑定。

### Library / Project

无冲突：

- Library 以发布快照供下游使用；
- Project 使用 lock；
- override 显式存在；
- 不自动升级。

### Obsidian

无冲突：

- 只做兼容与可选 UI 集成；
- 修改走 ExternalChange；
- 不替代 Rhine-Vault UI。

## 仍需实现阶段验证的风险

- Git commit 与 SQLite 事务不能真正做到单一 ACID，需要补偿事务；
- ExternalChange 恢复正式文件时需防止覆盖用户未保存内容；
- ChangeSet 跨多个文件的“原子性”需通过临时目录和补偿机制实现；
- Streamable HTTP 与 FastAPI 挂载方式需按锁定 SDK 版本验证；
- 中文、英文、代码混合嵌入模型需实测；
- `.rhine` 加密格式需选成熟库后冻结。
