# 检索融合与重排规范

## 架构

```text
多通道候选召回
→ Weighted RRF 融合
→ 规则过滤
→ 规则重排
→ 关系扩展
→ Context Bundle 分层
```

## 通道

- NodeID、别名、代码符号精确匹配；
- SQLite FTS5 全文；
- 向量检索；
- metadata：标签、NodeType、标题。

## Weighted RRF

V1 使用加权倒数排名融合，不直接相加 BM25 和向量原始分数。

```text
score(node) = Σ channel_weight / (k + rank)
```

## 精确匹配

以下内容提供独立 bonus：

- NodeID 完全匹配；
- 别名完全匹配；
- 类名、方法名、配置键等代码符号；
- 标题短语完全匹配。

## authority

节点权威等级：

- `canonical`
- `approved`
- `reference`
- `historical`
- `experimental`

`status` 表示生命周期，`authority` 表示权威级别，两者不能混为一谈。

## 关系扩展

关系分数基于：

```text
seed_score
× relation_type_weight
× depth_decay
× confidence_weight
```

同时应用连接度归一化，避免超级节点长期霸榜。

## 重排阶段

- V1：规则重排；
- V1.5：可选本地 Cross-Encoder，仅重排前若干候选；
- V2：LLM 辅助重排只用于复杂、高价值任务，不作为基础依赖。

## 去重

- NodeID 去重；
- supersedes 去重；
- 内容 hash；
- 归一化文本 hash；
- 可选语义相似去重。

去重只影响检索结果，不自动删除正式节点。

## 可解释性

每个结果应展示：

- 各通道排名；
- RRF 分数；
- exact/authority/relation bonus；
- penalty；
- final score；
- Context Bundle 分层；
- 纳入原因。
