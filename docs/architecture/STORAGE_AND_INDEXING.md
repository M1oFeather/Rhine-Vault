# 存储、索引与一致性

## 推荐分层

### Markdown Vault

保存正式内容和人类可读元数据。

优点：

- Git 友好；
- Obsidian 兼容；
- 可直接迁移；
- 无数据库也能查看。

### SQLite

保存：

- 工作区登记；
- 节点索引表；
- 关系表；
- 草稿状态；
- 文件 hash；
- IndexJob；
- AuditLog；
- 冲突状态。

### ChromaDB

保存：

- chunk_id；
- embedding；
- chunk 文本；
- node_id；
- workspace_id；
- revision；
-标题路径；
-标签。

## 一致性原则

批准草稿推荐顺序：

1. 校验候选内容；
2. 获取工作区写锁；
3. 检查 `base_revision`；
4. 写临时 Markdown；
5. fsync；
6. 原子替换正式文件；
7. SQLite 事务登记新 revision；
8. 创建 IndexJob；
9. 释放锁；
10. 异步执行索引。

索引失败不回滚已批准的正式文件，而是保留失败任务并允许重试。

## 文件监听

watchdog 只负责发现外部变化，不应直接承载业务逻辑。

事件进入防抖队列后：

- 重新读取文件；
- 计算 hash；
- 与 SQLite 快照比较；
- 校验；
- 更新登记；
- 创建索引任务。

## 检索层级

建议 V1 检索顺序：

1. workspace 强过滤；
2. NodeID 精确匹配；
3. title/tag 关键词；
4. SQLite FTS5 正文全文；
5. 向量召回；
6. 关系扩展；
7. 统一重排。

## Chunking

暂定采用“Markdown AST 标题层级优先”：

- Frontmatter 不进入正文向量；
- 每个标题节点形成逻辑块；
- 超过阈值后再按段落或 token 窗口切分；
- 每块保留标题路径；
- 禁止把代码围栏从中间截断。

具体阈值仍待根据嵌入模型测试。
