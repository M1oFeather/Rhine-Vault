# 关系图一致性规范

## 权威边界

- Markdown 中的已批准 outgoing relations：正式关系内容源；
- SQLite relation table：可重建查询索引；
- incoming edges：查询层动态计算。

## 关系类型 Schema

每种关系应定义：

- relation_type；
- label / inverse_label；
- symmetric；
- transitive；
- allow_cycles；
- allowed_source_types；
- allowed_target_types；
- default_weight；
- default_expand。

## 同步

节点批准后：

```text
解析正式 Markdown
→ 校验关系类型和目标
→ 删除旧 revision 边
→ 插入新 revision 边
→ 更新图索引
```

## 不一致处理

不能一律“Markdown 胜出”。

- 若 Markdown 是未批准外部修改：创建 ExternalChange，不更新正式边索引；
- 若 Markdown 与 approved hash 一致，仅 SQLite 边索引过期：自动重建；
- 若数据库 revision、Git commit、文件内容互相冲突：进入 inconsistent 状态并阻止发布。

## 悬空关系

- 技术结构关系默认不允许 unresolved；
- 世界观解释性关系可显式标记 unresolved；
- unresolved 默认不参与关系扩展；
- 目标归档不算真正悬空，但默认不扩展。

## 节点退役

正式节点默认不物理删除，使用：

- deprecated；
- archived；
- superseded。

退役前必须检查 incoming edges。强结构依赖可阻止归档。

## supersedes

具有特殊系统语义：

```text
new --supersedes--> old
```

旧节点必须为 `status: superseded` 并记录 `superseded_by`。系统校验双方一致。

## Git 变化

pull、merge、checkout 或外部 commit 后必须：

- 解析变化节点；
- 检查 NodeID；
- 检查关系目标；
- 检查循环；
- 检查 supersedes；
- 生成待审批外部变更或重建派生索引。
