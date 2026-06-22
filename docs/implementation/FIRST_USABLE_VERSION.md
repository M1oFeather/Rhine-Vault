# First Usable Version

## 状态

Rhine-Vault 的第一个可用版本定义为：

```text
本地启动 API / WebUI
-> 创建候选知识
-> 保存 staging
-> 人工批准
-> 正式节点进入检索
-> Context Bundle / Bot Context / MCP 读取可用
```

本版本仍属于 `Phase 4 — Formal UI and MCP`，不推进到 Phase 5。

## 默认运行数据

无显式配置时，运行数据放在当前启动目录：

```text
.rhine/rhine-vault.db
data/workspaces/<workspace_id>/nodes/*.md
```

可通过环境变量覆盖：

| 变量 | 用途 |
|---|---|
| `RHINE_VAULT_HOME` | 指定默认 `.rhine` 运行目录 |
| `RHINE_VAULT_DB` | 指定 SQLite 数据库路径 |
| `RHINE_VAULT_HOST` | 指定 API host，默认 `127.0.0.1` |
| `RHINE_VAULT_PORT` | 指定 API port，默认 `8765` |
| `RHINE_VAULT_IMPORT_ROOTS` | 额外允许导入/扫描的本地目录 |
| `RHINE_VAULT_UI_DIST` | 指定 Element UI 构建产物目录 |
| `RHINE_VAULT_ENABLE_MCP_HTTP` | 设置为 `1` 后显式启用 Streamable HTTP MCP |

## 启动

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe main.py
```

打开：

```text
http://127.0.0.1:8765/
http://127.0.0.1:8765/webui
http://127.0.0.1:8765/docs
```

健康检查：

```text
GET /api/health
```

健康检查会返回版本、阶段、数据库路径、vault root、WebUI/Element 状态和 MCP bridge 状态。

## 最小冒烟流程

1. 打开 `/webui`。
2. 在“采集 / 手动节点编辑”创建一条知识。
3. 在“审核”选择 proposal，保存为 staging。
4. 在“审核”批准 staging。
5. 在“节点”查看已批准节点。
6. 在“检索 / Retrieval Lab”搜索刚才的内容。
7. 在“对话”使用 FakeLLM 离线模型验证回答链路。
8. 在“MCP 能力”查看工具白名单，确认候选写入和禁止工具边界。

## 可用能力

- Core-only 安装仍然只依赖 Pydantic。
- API / WebUI 可选安装。
- Element UI 可以构建后由 API 托管，未构建时根路径回落到 WebUI。
- FakeLLM 可以离线测试，不需要真实模型密钥。
- OpenAI-compatible / DeepSeek 配置只通过请求或浏览器本地设置传入，不进入正式知识库。
- MCP bridge 允许读取正式知识、读取 bounded resource、提交或修订候选。

## 已知限制

- 未实现 ChromaDB / 生产向量索引。
- 未实现生产级图谱 UI。
- 未实现 Library 发布。
- 未实现 PDF/DOCX/OCR。
- 未实现完整 Obsidian 插件。
- 未实现云同步、Redis、PostgreSQL 或 Neo4j。
- 当前权限模型仍是本地单用户开发形态，没有多用户登录系统。

