# Rhine-Vault Unified Project Starter v1.2

这是 Rhine-Vault 的统一项目启动包。将压缩包内容直接解压到代码项目根目录即可。

## 包含内容

- 最终架构冻结文档
- 讨论演进与历史理由
- Codex Phase 0–1 首轮任务
- 持续讨论同步机制
- ADR 模板
- 会话记录模板
- 阶段推进模板
- 使用提示词

## 首次使用

1. 将本包内容解压到项目根目录。
2. 在 Codex 中打开该项目目录。
3. 发送 `PROMPTS/01_FIRST_START.md` 中的提示词。
4. Codex 完成 Phase 0–1 后，使用 `PROMPTS/02_REVIEW_COMPLETION.md` 检查结果。
5. 后续讨论形成新结论时，使用 `PROMPTS/03_CONTINUE_DISCUSSION.md`。
6. 只有用户明确推进阶段后，才更新 `docs/implementation/CURRENT_PHASE.md`。

## 文档不是一次性交接

后续和 Codex 的架构讨论、实现修正、范围变化都必须持续写回本项目文档。项目目录本身就是最新事实来源。


## v1.2 路线调整

保留 Phase 0–1 作为基础，但在正式大规模后端实现前新增：

```text
Phase 1.5 — Developer Vertical Slice
```

目标是尽早跑通：

```text
Workspace
→ Node
→ Staging
→ Approve
→ FTS/Search
→ Context Bundle
→ Fake/Real LLM
→ Minimal UI
```

这样可以在早期验证整个产品闭环，而不是等到底层全部完成后才发现交互或检索设计不合适。


## v1.2 核心入口调整

Phase 1.5 从一般 Developer Vertical Slice 升级为：

```text
Phase 1.5 — Knowledge Capture Vertical Slice
```

必须尽早验证四种知识入口：

1. 手动录入
2. 对话录入
3. Markdown/TXT 文档导入
4. 项目目录扫描与候选知识提取

统一流程：

```text
Source
→ Parse / Analyze
→ Capture Proposal
→ Review
→ Staging
→ Approve
→ Search
→ Context Bundle
→ LLM Answer with Sources
```

“学习”指提取、审核和录入知识，不代表训练模型。


## Phase 0–1 开发入口

本仓库已包含最小 Python 3.12+ `src` layout 与 Phase 0–1 基础实现。

安装开发依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

运行验证：

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
```

启动 Phase 1.5 极简后端与 UI：

```powershell
.\.venv\Scripts\python.exe -m uvicorn rhine_vault.api.app:create_app --factory --host 127.0.0.1 --port 8765
```

打开：

```text
http://127.0.0.1:8765/
```
