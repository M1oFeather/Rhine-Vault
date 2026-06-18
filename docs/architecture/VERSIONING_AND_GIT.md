# 节点版本、Git、Diff 与回滚规范

## 双层版本体系

### Rhine-Vault 业务 revision

负责：

- 节点级版本；
- 审批链；
- base_revision 冲突；
- 状态、关系和正文变更；
- 回滚来源；
- ChangeSet。

### Git 内置版本层

负责：

- Vault 级提交历史；
- 批量变更原子快照；
- Diff 与备份；
- 灾难恢复；
- 外部协作变更检测。

两者并存，互不替代。

## revision 规则

每次正式内容变化都递增 revision，包括：

- 正文；
- Frontmatter；
- tags；
- authority；
- status；
- relations；
- source。

重新索引、重建 Chunk、切换嵌入模型不增加节点 revision。

## 普通修订与语义替代

- 同一实体的修正：NodeID 不变，revision + 1。
- 概念被新概念取代：新建节点，并通过 `supersedes` 连接旧节点。
- NodeID 正式发布后不可原地修改。

## 历史目录

```text
.history/{node_id}/rev-0001.md
.history/{node_id}/rev-0002.md
```

`.history` 保存同一节点旧 revision；`.archive` 保存退出当前知识体系的节点。

## base_revision

更新草稿必须绑定 base_revision。批准时若当前正式 revision 已变化，返回 `REVISION_CONFLICT`，不得自动覆盖。

## Diff

必须支持：

1. 元数据 Diff；
2. 关系 Diff；
3. 章节 Diff；
4. 行级正文 Diff。

## 回滚

回滚不删除后续历史，而是生成新 revision：

```yaml
change_type: rollback
restored_from_revision: 5
previous_revision: 8
```

## Git 提交

- 单节点批准：一个 commit；
- ChangeSet：一个原子 commit；
- 回滚：一个新 commit；
- 禁止使用 `git reset --hard` 改写正式历史；
- Git commit 失败时标记 `versioning_failed`，不得静默忽略。

建议提交格式：

```text
node(spectrum.enemy.shield-crawler): approve revision 4

Workspace: spectrum-protocol
Node: spectrum.enemy.shield-crawler
Revision: 4
Change-Type: update
Staging-Entry: <id>
Actor: <actor>
```

## ChangeSet

领域模型预留多节点原子审批能力。角色改名、接口迁移等跨节点修改应通过 ChangeSet 一次校验、一次批准、一次 Git commit。
