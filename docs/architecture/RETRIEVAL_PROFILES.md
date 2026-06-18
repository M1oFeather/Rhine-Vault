# Retrieval Profile 与 UI 参数

## 定义

Retrieval Profile 是一组可版本化的检索、关系扩展、上下文预算和冲突处理参数。

一个工作区可以拥有多个 Profile，并指定默认 Profile。

## 四级覆盖

```text
系统默认
→ 工作区 Profile
→ 客户端配置
→ 单次请求覆盖
```

单次请求优先级最高，但安全和资源上限由服务端强制，客户端不可绕过。

## 预设

### technical-documentation

- 精确匹配与全文权重高；
- 向量权重较低；
- 关系深度默认 1；
- 冲突可阻断执行；
- 新版本优先。

### worldbuilding

- 向量与关系权重较高；
- 关系深度可为 2；
- 不普遍使用时间衰减；
- 冲突警告并保留双方。

### semantic-knowledge-base

- 向量检索优先；
- 全文检索次之；
- 关系扩展较浅；
- 内容去重更重要。

## UI

普通模式：

- 技术文档；
- 世界观设定；
- AI 知识库；
- 自定义。

高级模式：

- 各通道权重；
- 关系深度；
- 种子和扩展节点数量；
- Context Token 上限；
- 四层预算比例；
- 关系类型；
- 冲突策略；
- 最低相关阈值；
- 去重阈值；
- 是否启用本地重排器。

## 检索实验台

必须显示：

- 每个通道的候选；
- 融合排名；
- 关系扩展；
- 状态过滤；
- 冲突；
- 最终 Context Bundle；
- 评分拆解；
- 节点纳入和排除原因。

## 配置存储

```text
vaults/{workspace_id}/retrieval-profiles/
```

每次 Context Bundle 都记录 Profile ID 和 revision。
