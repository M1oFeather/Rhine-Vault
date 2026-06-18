# 领域模型

## Workspace

```python
Workspace(
    workspace_id: str,
    title: str,
    description: str | None,
    schema_version: int,
    created_at: datetime,
    updated_at: datetime,
)
```

建议 `workspace_id` 仅允许：

```regex
^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$
```

## MemoryNode

```python
MemoryNode(
    node_id: str,
    workspace_id: str,
    node_type: str,
    title: str,
    content: str,
    status: NodeStatus,
    revision: int,
    schema_version: int,
    tags: list[str],
    relations: list[NodeRelation],
    source: NodeSource,
    created_at: datetime,
    updated_at: datetime,
)
```

## NodeRelation

```python
NodeRelation(
    target: str,
    type: str,
    direction: Literal["outgoing", "incoming", "bidirectional"],
    description: str | None,
)
```

建议 V1 内置关系：

- `depends_on`
- `implements`
- `extends`
- `references`
- `conflicts_with`
- `supersedes`
- `causes`
- `affects`
- `belongs_to`
- `interacts_with`
- `related_to`

## StagingEntry

草稿不仅是文件路径，还需要独立状态：

```python
StagingEntry(
    entry_id: UUID,
    workspace_id: str,
    candidate_node_id: str,
    status: Literal["pending", "approved", "rejected", "superseded"],
    base_revision: int | None,
    created_by: str,
    created_at: datetime,
    updated_at: datetime,
    validation_errors: list[ValidationIssue],
)
```

`base_revision` 用于检测编辑期间正式节点是否已发生变化。

## IndexJob

```python
IndexJob(
    job_id: UUID,
    workspace_id: str,
    node_id: str,
    revision: int,
    operation: Literal["upsert", "delete", "rebuild"],
    status: Literal["queued", "running", "succeeded", "failed"],
    attempts: int,
    error_message: str | None,
)
```

## AuditLog

应记录：

- actor；
- action；
- workspace；
- node / staging entry；
- before hash；
- after hash；
- 时间；
-结果；
-错误。
