# CMCC / Ptilopsis / Rhine-Vault Integration Plan

## 背景

用户希望之后将本地 CMCC 项目做成 bot 插件，并与 Rhine-Vault 对接：

```text
Ptilopsis bot adapter
-> CMCC persona runtime
-> Rhine-Vault curated knowledge backend
-> LLM reply
```

目标不是把两个项目合并，而是模拟一个更像“有笔记的人物设定系统”：

- CMCC 负责即时人格运行、对话状态、发言风格和前端记忆调度；
- Rhine-Vault 负责经过审核的后端知识库、人物设定、规则、资料来源和长期可修正笔记；
- Ptilopsis 负责 bot 框架接入和消息事件适配。

## 当前 CMCC 观察

CMCC 当前是原型形态，主要文件：

- `main.py`：核心 `PersonaSystem`、ChromaDB、Mem0、DeepSeek 调用、CLI 命令；
- `api.py`：FastAPI wrapper，提供 `/api/chat`、`/api/proactive`、`/api/command`、`/api/status`；
- `console.py`：Streamlit 数据面板；
- `filters.txt`：安全/过滤词；
- `user_mapping.json`：用户 ID 到显示名映射；
- `ptilopsis_samples*.csv`：角色语料样本；
- `chroma_lore_db/`、`chroma_mem0_db/`：本地 Chroma 数据；
- `backups/`：自动备份 zip。

CMCC 已经包含三个记忆层：

| 层 | 当前实现 | 适合迁移方向 |
|---|---|---|
| 角色设定 / lore | `persona_lore` Chroma collection | Rhine formal MemoryNode |
| 语气样本 / few-shot | `persona_samples` Chroma collection | Rhine MemoryNode + sample projection |
| 用户长期印象 | Mem0 + `mem0_memory` Chroma | CMCC runtime memory，重要结论回流 Rhine staging |

## 必须先处理的风险

1. 当前 CMCC 源码中存在硬编码 API key。正式插件化前必须：
   - 立即轮换该 key；
   - 改为环境变量或本地私有配置；
   - 确认 Git 历史和备份包没有继续暴露密钥。
2. `main.py` 和 `console.py` 重复配置 LLM key/base URL，应集中配置。
3. 当前核心逻辑集中在单个 `main.py`，导入时会初始化外部客户端和后台线程，不利于 bot 插件加载。
4. Chroma 数据库和 backups 是运行数据，不应进入插件包。
5. Windows 控制台显示存在明显编码问题，需要统一 UTF-8 文件和终端读取方式。
6. `api.py` 通过 `from main import PersonaSystem` 直接导入运行文件，会产生强 side effect。

## 推荐分层

### Ptilopsis 插件层

职责：

- 接收 bot 框架消息事件；
- 映射 `uid`、`display_name`、群聊/私聊上下文；
- 调用 CMCC runtime；
- 将回复发回 bot；
- 不直接管理 Rhine 数据库。

建议模块名：

```text
plugins/ptilopsis_rhine_memory/
├─ __init__.py
├─ adapter.py
├─ config.py
├─ client.py
└─ models.py
```

### CMCC Runtime 层

职责：

- 角色运行时；
- 智能回复判断；
- prompt 组装；
- 短期会话历史；
- Mem0 / runtime memory；
- 主动发言；
- 修正、归档、训练等候选生成。

建议拆分：

```text
cmcc/
├─ core/
│  ├─ persona_runtime.py
│  ├─ prompt_builder.py
│  ├─ memory_runtime.py
│  └─ safety_filter.py
├─ adapters/
│  ├─ rhine_client.py
│  └─ llm_client.py
├─ api/
│  └─ app.py
└─ data/
   └─ .gitkeep
```

### Rhine-Vault 后端知识库

职责：

- 人物设定；
- 世界观资料；
- 行为约束；
- 用户关系设定；
- 语气样本；
- 修正后的长期规则；
- 来源和审核。

Rhine 只接收候选，不让 bot 直接写正式知识。

## 推荐数据流

### 普通聊天

```text
bot event
-> Ptilopsis plugin
-> CMCC PersonaRuntime.chat()
-> Rhine /api/context or MCP get_related_context
-> CMCC prompt_builder merges runtime memory + Rhine Context Bundle
-> LLM
-> reply to bot
-> optional runtime memory add
```

### 用户纠错

```text
user correction
-> CMCC handle_correction()
-> submit correction as Rhine Capture Proposal
-> human review in Rhine
-> approved MemoryNode becomes future backend note
```

### 对话归档

```text
session history
-> CMCC archive_memory()
-> Rhine conversation capture proposal
-> review / edit / approve
-> future retrieval context
```

### 角色设定导入

```text
CMCC lore / samples / CSV
-> conversion script
-> Rhine proposals
-> human review
-> approved persona notebook
```

## Rhine API 使用建议

初期优先使用普通 REST：

- `POST /api/context`
- `POST /api/integrations/bot/context`
- `POST /api/conversations/capture`
- `POST /api/manual`

后续如果需要 Agent/工具协议，再使用 Phase 4 MCP：

- `get_related_context`
- `search_nodes`
- `submit_staging_node`
- `revise_staging_node`

不要给插件提供：

- staging approval；
- direct formal write；
- raw SQL；
- arbitrary file read；
- Git commit。

## 人物设定模拟方式

建议把“人物卡”拆成可审核节点，而不是一个巨大 prompt：

| 节点类型 | 示例 |
|---|---|
| `PersonaIdentity` | 白面鸮身份、称呼、核心气质 |
| `PersonaSpeechStyle` | 语言风格、禁用语气、句式习惯 |
| `PersonaConstraint` | 绝对不能做的行为、出戏防护 |
| `RelationshipRule` | 对特定用户/角色的称呼与关系 |
| `SceneState` | 当前场景、时间、事件状态 |
| `SampleDialogue` | few-shot 问答或场景对话 |
| `CorrectionRule` | 用户纠错沉淀出的长期规则 |

CMCC prompt builder 每轮根据消息检索这些节点，组合成 Context Bundle。

## 迁移顺序

1. 轮换泄露的 DeepSeek API key；
2. 在 CMCC 增加 `.gitignore`，排除 `.venv/`、Chroma DB、backups、本地配置；
3. 把密钥、base URL、模型名移入配置层；
4. 把 `PersonaSystem` 从 `main.py` 拆到 `cmcc/core/persona_runtime.py`；
5. 把 LLM 调用拆到 `cmcc/adapters/llm_client.py`；
6. 把 Rhine 调用拆到 `cmcc/adapters/rhine_client.py`；
7. 为 `/api/chat` 写最小测试；
8. 实现 Rhine Context Bundle 注入；
9. 实现 correction/archive 到 Rhine proposal；
10. 再把 Ptilopsis 侧做成插件。

## 结论

CMCC 很适合做“人物前端记忆/人格运行时”，Rhine-Vault 适合做“后端知识库/人物笔记本”。

真正的产品形态应是：

```text
Ptilopsis = 消息入口和 bot 适配
CMCC = 角色即时意识和运行时记忆
Rhine-Vault = 可审核、可修正、可引用的长期知识
```

这样可以保留 CMCC 当前已经验证过的角色对话实验，又把长期知识从模糊向量库提升为 Rhine 中可见、可审、可改的笔记系统。
