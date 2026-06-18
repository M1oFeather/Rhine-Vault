# REST 与 MCP 接口草案

## REST

### Health

- `GET /health`
- `GET /api/v1/index/health`

### Workspaces

- `GET /api/v1/workspaces`
- `POST /api/v1/workspaces`
- `GET /api/v1/workspaces/{workspace_id}`

### Nodes

- `GET /api/v1/workspaces/{workspace_id}/nodes`
- `GET /api/v1/workspaces/{workspace_id}/nodes/{node_id}`
- `GET /api/v1/workspaces/{workspace_id}/nodes/{node_id}/graph`
- `POST /api/v1/workspaces/{workspace_id}/search`

### Staging

- `GET /api/v1/workspaces/{workspace_id}/staging`
- `POST /api/v1/workspaces/{workspace_id}/staging`
- `GET /api/v1/workspaces/{workspace_id}/staging/{entry_id}`
- `PUT /api/v1/workspaces/{workspace_id}/staging/{entry_id}`
- `GET /api/v1/workspaces/{workspace_id}/staging/{entry_id}/diff`
- `POST /api/v1/workspaces/{workspace_id}/staging/{entry_id}/approve`
- `POST /api/v1/workspaces/{workspace_id}/staging/{entry_id}/reject`

## MCP Tools

### 只读工具

- `list_workspaces`
- `get_node`
- `search_nodes`
- `get_local_graph`
- `get_related_context`

### 候选写入工具

- `submit_staging_node`
- `revise_staging_node`

### 明确禁止

不注册以下面向 Agent 的工具：

- `approve_staging_node`
- `write_formal_node`
- `delete_formal_node`
- `execute_raw_sql`
- `read_arbitrary_file`

## MCP Resources

可选 URI 方案：

```text
rhine://workspace/{workspace_id}/node/{node_id}
rhine://workspace/{workspace_id}/graph/{node_id}?depth=1
rhine://workspace/{workspace_id}/schema/memory-node
```

## Tool Annotations

读取工具应标注为只读；草稿提交工具应明确具有写入副作用，但不改变正式知识。

## 错误模型

统一错误码建议：

- `WORKSPACE_NOT_FOUND`
- `INVALID_WORKSPACE_ID`
- `NODE_NOT_FOUND`
- `DUPLICATE_NODE_ID`
- `SCHEMA_VALIDATION_FAILED`
- `RELATION_TARGET_NOT_FOUND`
- `REVISION_CONFLICT`
- `PATH_TRAVERSAL_BLOCKED`
- `INDEX_NOT_READY`
