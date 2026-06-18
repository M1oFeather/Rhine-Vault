<h1 align="center">Rhine-Vault</h1>

<p align="center">
  <em>莱茵档案室 · Local-first Knowledge Capture Engine</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/FastAPI-Phase%201.5-009688?style=flat-square" alt="FastAPI">
  <img src="https://img.shields.io/badge/SQLite-FTS5-003B57?style=flat-square" alt="SQLite FTS5">
  <img src="https://img.shields.io/badge/Pydantic-v2-E92063?style=flat-square" alt="Pydantic v2">
  <img src="https://img.shields.io/badge/Status-Knowledge%20Capture%20Slice-purple?style=flat-square" alt="Status">
</p>

---

## 简介

**Rhine-Vault** 是一个本地优先、数据主权优先的无头知识图谱与检索引擎。它把对话、文档和项目文件先转化为可审阅的候选知识，再通过人工批准进入正式知识库，最后用于搜索、Context Bundle 组装和 LLM 回答引用。

当前版本处于 **Phase 1.5 — Knowledge Capture Vertical Slice**：重点不是完整产品化，而是尽早验证从知识录入到可引用回答的最小闭环。

> Phase 1.5 不实现正式 Git 发布事务、MCP、ChromaDB、Library、PDF/DOCX/OCR 或实时项目同步。

---

## 前置依赖

| 依赖 | 说明 |
|---|---|
| **Python 3.12+** | 项目运行环境 |
| **FastAPI** | 极简后端与 API |
| **SQLite / FTS5** | Phase 1.5 存储与全文检索 |
| **Pydantic v2** | 领域模型与输入校验 |
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
- **来源引用** — LLM 回答保留 node citation 与 source reference
- **FakeLLMProvider** — 自动测试不依赖真实 LLM
- **界面 i18n** — 默认中文，支持中文 / English 切换

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
├── api/                         # FastAPI 后端与极简 Web UI
│   ├── app.py                   # API 路由、应用工厂、UI 入口
│   └── static/
│       └── index.html           # Phase 1.5 单页 UI
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
├── context.py                   # Context Bundle v0
├── core.py                      # 应用启动编排
├── i18n.py                      # UI 中文/英文翻译词表
├── logger.py                    # 日志初始化
├── node_types.py                # 节点类型配置加载与本地化
└── llm.py                       # FakeLLM 与 OpenAI-compatible Provider
```

---

## 使用指南

### 安装开发依赖

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

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
| `POST /api/llm/fake` | FakeLLM 回答 |
| `POST /api/llm/openai-compatible` | 可选真实 Provider |
| `GET /api/i18n` | 获取 UI 翻译词表 |
| `GET /api/node-types` | 获取节点类型配置和多语言显示名 |

---

## 技术亮点

- **本地优先** — Phase 1.5 默认可在无真实 LLM、无向量库、无云服务下完整测试
- **审批边界清晰** — Source、Proposal、Staging、MemoryNode 分层保存
- **检索不污染** — 未批准 proposal 不进入正式 FTS
- **可追溯来源** — 对话 message range、文档 heading / line range、项目文件 path 均可保留
- **确定性基础设施** — Markdown round-trip 与 chunking 不依赖 LLM
- **可替换 LLM** — FakeLLM 用于测试，OpenAI-compatible Provider 只在显式配置后启用
- **轻量 i18n** — 翻译词表由后端提供，UI 默认中文并支持英文切换

---

## 文档入口

| 文档 | 说明 |
|---|---|
| `docs/architecture/00_START_HERE.md` | 架构总览入口 |
| `docs/architecture/ARCHITECTURE_CONTRACT.md` | 最高级实现约束 |
| `docs/architecture/KNOWLEDGE_CAPTURE.md` | Knowledge Capture 边界 |
| `docs/implementation/CURRENT_PHASE.md` | 当前阶段 |
| `docs/implementation/PHASE_1_5_VERTICAL_SLICE.md` | Phase 1.5 规格 |
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
    <td>Phase 1.5 — Knowledge Capture Vertical Slice</td>
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
  <sub>Rhine-Vault 仍处于早期垂直切片阶段；正式工作流、Git 事务、MCP、Library 与向量索引将在后续阶段推进。</sub>
</p>
