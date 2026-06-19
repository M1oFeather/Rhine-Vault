<h1 align="center">Rhine-Vault</h1>

<p align="center">
  <em>莱茵档案室 · Local-first Knowledge Capture Engine</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/FastAPI-optional-009688?style=flat-square" alt="FastAPI">
  <img src="https://img.shields.io/badge/SQLite-FTS5-003B57?style=flat-square" alt="SQLite FTS5">
  <img src="https://img.shields.io/badge/Pydantic-v2-E92063?style=flat-square" alt="Pydantic v2">
  <img src="https://img.shields.io/badge/Status-Phase%204%20MCP-purple?style=flat-square" alt="Status">
</p>

---

## 简介

**Rhine-Vault** 是一个本地优先、数据主权优先的无头知识图谱与检索引擎。它把对话、文档和项目文件先转化为可审阅的候选知识，再通过人工批准进入正式知识库，最后用于搜索、Context Bundle 组装和 LLM 回答引用。

当前版本已推进至 **Phase 4 — Formal UI and MCP**：在正式审批、可解释检索和 Context Bundle 基础上，补齐受限 MCP 能力边界、候选写入工具、资源读取和 HTTP 管理入口。

> Phase 4 不实现 ChromaDB / 生产向量索引、Library 发布、PDF/DOCX/OCR、生产级图谱 UI、完整 Obsidian 插件或云端同步。

---

## 前置依赖

| 依赖 | 说明 |
|---|---|
| **Python 3.12+** | 项目运行环境 |
| **FastAPI** | 极简后端与 API |
| **SQLite / FTS5** | 工作流存储与全文检索 |
| **Pydantic v2** | 领域模型与输入校验 |
| **MCP SDK** | 可选 MCP stdio / Streamable HTTP adapter |
| **pytest / ruff / mypy** | 测试、lint 与类型检查 |
| **MkDocs** | 项目文档站点 |

---

## 核心特性

### Knowledge Capture

- **手动录入** — 通过极简编辑入口创建 Capture Proposal
- **对话录入** — 从多条聊天消息组成的 conversation source 中生成候选节点与候选关系
- **文档导入** — 支持 Markdown / TXT，保留文件 hash、heading path 与 line range
- **项目扫描** — 受控扫描 README、docs、src 与配置文件，区分 Source Index 和 Curated Knowledge

### Review & Staging

- **Source ≠ Proposal ≠ MemoryNode** — 原始材料、候选知识和正式知识严格分层
- **AI 不直接批准** — AI 只能生成 proposal / staging，正式知识必须人工批准
- **未批准不检索** — 未批准候选不会进入正式 FTS 搜索
- **workspace 隔离** — 关键操作显式携带 `workspace_id`

### Retrieval & Context

- **基础 FTS5 检索** — 已批准 MemoryNode 可被全文搜索
- **Context Bundle v0** — 输出 Mandatory Constraints、Relevant Context、Supporting References、Warnings
- **Formal Retrieval** — Retrieval Profile、Weighted RRF、规则重排、关系扩展与 explain trace
- **MCP 边界** — Agent 可读正式知识并提交/修订候选，但不能批准或直接写正式节点
- **来源引用** — LLM 回答保留 node citation 与 source reference
- **FakeLLMProvider** — 自动测试不依赖真实 LLM
- **界面 i18n** — 默认中文，支持中文 / English 切换
- **类 VS Code 侧栏** — 采集、节点、审核、检索按活动栏组织

### Markdown Foundation

- **YAML Frontmatter 往返** — 确定性解析与序列化
- **Markdown block chunking** — 标题、代码块、表格、列表和语义块保持稳定
- **稳定 Chunk ID** — Chunk 与 workspace、node、revision、profile 强绑定

---

## 项目架构

```text
main.py                           # 根目录薄启动入口

src/rhine_vault/
│
├── core/                        # core-only 入口与运行时边界
│   └── runtime.py               # API server lazy import，core 安装安全
│
├── api/                         # 可选 FastAPI REST/UI adapter
│   ├── app.py                   # API 路由、应用工厂、UI 路由与 docs 入口
│   └── static/
│       └── index.html           # 内置 WebUI 管理面板
│
├── capture/                     # Knowledge Capture 编排
│   ├── service.py               # 手动、对话、文档、项目扫描入口
│   └── rules.py                 # Phase 1.5 确定性提取规则
│
├── domain/                      # 领域模型
│   ├── ids.py                   # workspace_id / node_id / relation 校验
│   ├── models.py                # Workspace、MemoryNode、StagingEntry 等
│   └── capture.py               # SourceRecord、CaptureProposal 等模型
│
├── io/                          # I/O 安全边界
│   └── paths.py                 # 服务端路径解析与路径穿越防护
│
├── markdown/                    # Markdown 基础能力
│   ├── frontmatter.py           # Frontmatter 解析
│   ├── serializer.py            # 确定性序列化
│   ├── blocks.py                # 行级 Markdown block parser
│   └── chunking.py              # 确定性 Chunking
│
├── storage/                     # 最小持久层
│   └── sqlite.py                # Source / Proposal / Staging / Node / FTS5
│
├── config/
│   └── node_types.json          # 节点类型与多语言显示名配置
│
├── retrieval.py                 # Phase 3 正式检索链路
├── mcp_bridge.py                # Phase 4 MCP 受限能力桥
├── mcp_server.py                # 可选 FastMCP adapter
├── context.py                   # Context Bundle
├── i18n.py                      # UI 中文/英文翻译词表
├── logger.py                    # 日志初始化
├── node_types.py                # 节点类型配置加载与本地化
└── llm.py                       # FakeLLM 与 OpenAI-compatible Provider

ui/
├── package.json                 # Vite + Vue + Element Plus 客户端
├── vite.config.ts
└── src/
    ├── assets/icons/            # 面板图标资源
    ├── components/              # Vue 共享组件
    ├── icons/                   # 图标注册表
    ├── App.vue
    ├── api.ts
    └── main.ts
```

---

## 使用指南

### 安装开发依赖

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

### 仅安装 Core

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
```

默认安装只包含核心领域模型、Markdown、SQLite、正式工作流和检索能力，不强制安装 FastAPI、uvicorn 或前端工具链。

### 安装 API Server

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[api]"
```

### 安装 MCP Adapter

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[mcp]"
```

MCP SDK 是可选依赖。未安装时，core 与 API server 仍可正常工作，`/api/mcp/capabilities` 仍可查看同一套受限能力边界。

### 安装 WebUI 层

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[webui]"
```

WebUI 层包含 API server 依赖，并保留 `/webui` 作为可扩展远程管理面板入口。世界观生成器、小说编写管理、Bot/机器人控制面板等适合优先放在这一层，避免污染 core。

### 安装 Desktop 层

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[desktop]"
```

Desktop 层面向完整本地工作台，后续可承载更多本地文件、顶部菜单、帮助文档、本地编辑器和 Element Plus 独有能力。

### 启动后端与 UI

```powershell
.\.venv\Scripts\python.exe main.py
```

或使用显式 ASGI 入口：

```powershell
.\.venv\Scripts\python.exe -m uvicorn rhine_vault.api.app:create_app --factory --host 127.0.0.1 --port 8765
```

访问：

```text
http://127.0.0.1:8765/
```

### 启动 MCP stdio

```powershell
.\.venv\Scripts\rhine-vault-mcp.exe
```

可通过 `RHINE_VAULT_DB` 指定 SQLite 数据库路径。Streamable HTTP MCP 需要先安装 `rhine-vault[mcp]`，并显式启用：

```powershell
$env:RHINE_VAULT_ENABLE_MCP_HTTP="1"
.\.venv\Scripts\python.exe main.py
```

挂载路径为 `/mcp`。普通管理端点始终是 `/api/mcp/*`。

### 启动 Element Plus UI

```powershell
cd ui
npm install
npm run dev
```

开发时 Vite 会把 `/api` 代理到 `http://127.0.0.1:8765`。

构建后端托管产物：

```powershell
cd ui
npm run build
```

FastAPI 会优先托管 `ui/dist/index.html`；也可通过 `RHINE_VAULT_UI_DIST` 指定外部构建目录。内置 WebUI 始终可通过 `/webui` 打开，用于轻量远程管理；Element 构建产物可通过 `/element` 打开。未构建 Element UI 时，`/` 会回落到 WebUI；设置 `RHINE_VAULT_API_DOCS_ONLY=1` 时，`/` 只显示 FastAPI 自带 `/docs`、`/redoc` 和 `/openapi.json` 入口。

UI 迁移原则：WebUI 与 Element UI 可以都使用 Vue，但必须先保证 WebUI 功能等价，再做视觉升级。面板图标采用 `M1oFeather/Game-Icon-Pack` 精选 SVG 子集，通过 `GameIcon.vue` 引用。

### 最小流程

```text
Source
  ↓
Capture Proposal
  ↓
Review
  ↓
Staging
  ↓
Approve
  ↓
MemoryNode
  ↓
FTS Search
  ↓
Context Bundle
  ↓
FakeLLM Answer with Sources
```

---

## 开发指南

### 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m mkdocs build --strict
```

### 新增采集入口

参照 `capture/service.py` 中现有入口：

1. 创建 SourceRecord，保留来源定位和 hash
2. 生成 CaptureProposal，而不是直接创建 MemoryNode
3. 候选节点保留 `source_refs`
4. 通过 staging / approve 进入正式知识
5. 为端到端流程补测试

### 新增 Markdown 能力

参照 `markdown/` 下现有结构：

1. 保持解析与序列化确定性
2. 代码块、表格、列表和语义块尽量原子化
3. Chunk ID 不依赖 LLM
4. 新行为必须覆盖测试

---

## API 一览

| API | 用途 |
|---|---|
| `POST /api/manual` | 手动录入 Capture Proposal |
| `POST /api/conversations/capture` | 对话录入 |
| `POST /api/documents/import` | Markdown/TXT 文档导入 |
| `POST /api/projects/scan` | 受控项目扫描 |
| `GET /api/proposals` | 查看待审核 proposal |
| `PATCH /api/proposals/{proposal_id}/nodes/{temporary_id}` | 修改候选节点 |
| `POST /api/proposals/{proposal_id}/stage` | 保存为 staging |
| `POST /api/staging/approve` | 人工批准 staging |
| `POST /api/search` | FTS 搜索已批准节点 |
| `POST /api/context` | 构建 Context Bundle v0 |
| `POST /api/integrations/bot/context` | 为 Bot/Ptilopsis 适配器生成轻量 Context payload |
| `POST /api/documents/generate` | 基于已批准知识生成可检查 Markdown 文档 |
| `GET /api/mcp/capabilities` | 查看 Phase 4 MCP 白名单、资源和禁止能力 |
| `POST /api/mcp/tools/{tool_name}` | 通过 HTTP 调用同一套受限 MCP bridge |
| `GET /api/mcp/resources` | 读取受限 `rhine://` MCP resources |
| `POST /api/llm/fake` | FakeLLM 回答 |
| `POST /api/llm/openai-compatible` | 可选真实 Provider |
| `GET /api/i18n` | 获取 UI 翻译词表 |
| `GET /api/node-types` | 获取节点类型配置和多语言显示名 |
| `GET /api/nodes` | 获取已批准节点目录 |

---

## 技术亮点

- **本地优先** — 默认 core-only，可在无真实 LLM、无向量库、无云服务下完整测试
- **审批边界清晰** — Source、Proposal、Staging、MemoryNode 分层保存
- **检索不污染** — 未批准 proposal 不进入正式 FTS
- **受限 MCP** — MCP 只能读正式知识和写候选区，不能批准、删除、raw SQL 或任意读文件
- **可追溯来源** — 对话 message range、文档 heading / line range、项目文件 path 均可保留
- **确定性基础设施** — Markdown round-trip 与 chunking 不依赖 LLM
- **可替换 LLM** — FakeLLM 用于测试，OpenAI-compatible Provider 只在显式配置后启用
- **轻量 i18n** — 翻译词表由后端提供，UI 默认中文并支持英文切换
- **节点目录** — UI 可浏览已批准节点，生产图谱连线面板留待后续阶段

---

## 文档入口

| 文档 | 说明 |
|---|---|
| `docs/architecture/00_START_HERE.md` | 架构总览入口 |
| `docs/architecture/ARCHITECTURE_CONTRACT.md` | 最高级实现约束 |
| `docs/architecture/KNOWLEDGE_CAPTURE.md` | Knowledge Capture 边界 |
| `docs/implementation/CURRENT_PHASE.md` | 当前阶段 |
| `docs/implementation/PHASE_1_5_VERTICAL_SLICE.md` | Phase 1.5 规格 |
| `docs/implementation/PHASE_2_FORMAL_WORKFLOW.md` | Phase 2 规格 |
| `docs/implementation/PHASE_3_FORMAL_RETRIEVAL.md` | Phase 3 规格 |
| `docs/implementation/PHASE_4_FORMAL_UI_MCP.md` | Phase 4 规格 |
| `docs/implementation/PROJECT_STYLE_STANDARD_TEMPLATE.md` | 个人项目统一风格模板 |
| `mkdocs.yml` | MkDocs 文档站点配置 |

### 本地预览文档

```powershell
.\.venv\Scripts\python.exe -m mkdocs serve
```

---

## 作者与状态

<table>
  <tr>
    <td align="center"><b>项目</b></td>
    <td>Rhine-Vault / 莱茵档案室</td>
  </tr>
  <tr>
    <td align="center"><b>阶段</b></td>
    <td>Phase 4 — Formal UI and MCP</td>
  </tr>
  <tr>
    <td align="center"><b>定位</b></td>
    <td>Local-first knowledge graph and retrieval engine</td>
  </tr>
  <tr>
    <td align="center"><b>许可</b></td>
    <td>未声明</td>
  </tr>
</table>

---

<p align="center">
  <sub>Rhine-Vault 已进入受限 MCP 与正式 UI 阶段；Library、生产向量索引与生产级图谱 UI 将在后续阶段推进。</sub>
</p>
