# Phase 4 — Formal UI and MCP

## 目的

Phase 4 将 Phase 3 的正式检索链路开放给受限 Agent 与管理界面。

这一阶段不是让 Agent 获得管理员权限，而是建立清晰、可测试、可解释的 MCP 边界：

```text
approved MemoryNode / retrieval
→ bounded MCP read tools and resources
→ candidate-only MCP write tools
→ human review remains required
```

## 正式边界

Core 仍然是最小安装层。MCP SDK 只作为 optional extra：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[mcp]"
```

如果没有安装 MCP SDK：

- `rhine_vault.mcp_bridge` 仍可作为普通 Python bridge 使用；
- FastAPI `/api/mcp/*` 仍可返回同一套能力清单和普通 HTTP 调用；
- `rhine-vault-mcp` 会给出明确安装提示。

## MCP 工具白名单

只允许以下工具：

- `list_workspaces`
- `get_node`
- `search_nodes`
- `get_local_graph`
- `get_related_context`
- `submit_staging_node`
- `revise_staging_node`

其中 `submit_staging_node` 与 `revise_staging_node` 只影响候选区或 pending staging，不直接写入正式知识库。

## 明确禁止

Phase 4 MCP 不提供以下能力：

- `approve_staging_node`
- `write_formal_node`
- `delete_formal_node`
- `execute_raw_sql`
- `read_arbitrary_file`
- `publish_library`
- `git_commit`

如果调用这些名字，bridge 必须拒绝。

## MCP Resources

Phase 4 暴露三个受限资源模板：

```text
rhine://workspace/{workspace_id}/node/{node_id}
rhine://workspace/{workspace_id}/graph/{node_id}?depth=1
rhine://workspace/{workspace_id}/schema/memory-node
```

限制：

- node resource 只返回已批准 formal MemoryNode；
- graph resource 只返回 bounded one-hop local graph；
- schema resource 只返回 MemoryNode 结构说明；
- 不允许 arbitrary file URI。

## HTTP 与 Streamable HTTP

FastAPI 始终提供普通 HTTP 管理端点：

- `GET /api/mcp/capabilities`
- `POST /api/mcp/tools/{tool_name}`
- `GET /api/mcp/resources?uri=...`

正式 MCP Streamable HTTP 入口通过环境变量显式启用：

```powershell
$env:RHINE_VAULT_ENABLE_MCP_HTTP="1"
```

启用后挂载路径为：

```text
/mcp
```

如果没有安装 `rhine-vault[mcp]`，该挂载不会强制失败 API server，能力状态会报告错误原因。

## SDK 依据

Phase 4 采用官方 Python MCP SDK 的 FastMCP 入口：

- package: `mcp`
- recommended range before v2 stable: `mcp>=1.27,<2`
- stdio server: `server.run(transport="stdio")`
- Streamable HTTP app: `server.streamable_http_app()`

参考官方仓库：[modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk)

## 本轮实现记录

- 新增 `src/rhine_vault/mcp_bridge.py`，作为不依赖 MCP SDK 的受限能力桥。
- 新增 `src/rhine_vault/mcp_server.py`，使用 lazy import 适配可选 FastMCP。
- 新增 `rhine-vault-mcp` console script。
- 新增 `mcp` optional extra: `mcp>=1.27,<2`。
- 新增 `SQLiteStore.list_workspaces()`、`get_staging_entry()`、`update_staging_node()` 支持 Phase 4 边界。
- FastAPI 新增 `/api/mcp/capabilities`、`/api/mcp/tools/{tool_name}` 和 `/api/mcp/resources`。
- Streamable HTTP MCP 挂载由 `RHINE_VAULT_ENABLE_MCP_HTTP=1` 显式开启。
- 内置 WebUI 新增 MCP 能力边界页，可查看工具白名单、禁止工具、资源模板，并调用受限工具或读取 resource。
- Element UI 新增 MCP activity，可展示 Streamable HTTP 状态、工具表、禁止工具、资源模板、受限工具调用器与 resource 读取器。
- 新增 Phase 4 测试，覆盖能力白名单、候选写入边界、资源读取、HTTP wrapper、UI surface 和可选 SDK lazy import。

## 成功条件

```text
approved MemoryNode
→ MCP read tools
→ Context Bundle / local graph / node resource
→ candidate-only staging write
→ human approval remains outside MCP
```

并且：

- core-only 默认安装不变；
- 未批准内容不会进入 `search_nodes` 或 `get_related_context`；
- forbidden tool names 明确拒绝；
- MCP SDK 未安装时 API server 不被拖垮；
- 测试覆盖协议边界和审批边界。
