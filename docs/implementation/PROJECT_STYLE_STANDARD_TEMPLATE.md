# M1oFeather Project Style Standard Template

> 适用于 Rhine-Vault、Ptilopsis、AcgDraw 以及后续个人 Python 项目。
>
> 这份文档是“项目结构与代码风格模板”，不是单个项目的产品架构决策。具体项目可以在保留核心标准的前提下，按自身技术栈补充细节。

## 1. 目标

统一项目的外观、入口、目录职责、模块命名和代码纪律，让多个项目看起来像同一个作者长期维护的作品，而不是互不相关的临时脚本集合。

本标准优先吸收 `Ptilopsis` 中较成熟的组织方式，保留 `AcgDraw` 中有价值的项目形状，同时修正早期项目中不稳定或不规范的写法。

## 2. 适用级别

### 必须遵守

- 项目根目录必须有清晰的 `README.md`，用于公开介绍项目，而不是保存本地启动提示词。
- 项目必须有单一、清晰、很薄的启动入口，优先使用根目录 `main.py`。
- 业务逻辑必须放入项目包内，不能长期堆在 `main.py`。
- 测试、运行数据、配置样例、文档、静态资源必须分开存放。
- 对外边界代码必须有明确异常处理，不能使用无意义的裸 `except`。
- 新代码必须保持格式化、lint、类型检查或等价的质量检查可运行。
- AI 协作、临时讨论、本地私有配置和运行产物必须进入 `.gitignore`。
- Markdown 文档建议使用 UTF-8 with BOM，避免 Windows PowerShell 读取中文时乱码。

### 推荐遵守

- 新 Python 项目优先使用 `src/<package_name>/` 布局。
- 已存在的历史项目可以保留原包名和根目录形状，不为了形式统一进行高风险迁移。
- 保留根目录 `main.py` 作为用户习惯入口，内部只调用包内 `app` / `core` / `server`。
- 模块分层可以优先使用 `core`、`api`、`adapter`、`event`、`plugin`、`manager`、`domain`、`storage`、`io`、`web` 等名称。
- 面向用户的日志、README、错误提示可以使用中文；代码命名保持英文。
- 小项目可以先保持简单，但要给未来拆分留下清楚边界。

### 明确避免

- 避免把启动逻辑、业务逻辑、配置读取、交互输入全部写在 `main.py`。
- 避免用全局变量保存复杂运行态，尤其是服务、管理器、数据库连接和用户配置。
- 避免魔法 debug 标志，例如 `debug_mode = 1`、`debug=False` 到处散落。
- 避免 `dir`、`list`、`type` 等内置名作为变量名。
- 避免宽泛 `except Exception` 后只打印或静默吞掉错误。
- 避免把运行时生成的数据、缓存、数据库、日志直接提交到仓库。
- 避免 `util.py` 变成杂物箱；只有跨模块、无业务归属的纯工具函数才放入 `util.py`。

## 3. 推荐根目录

```text
ProjectName/
├─ README.md
├─ LICENSE
├─ pyproject.toml
├─ main.py
├─ src/
│  └─ project_name/
│     ├─ __init__.py
│     ├─ core.py
│     ├─ logger.py
│     ├─ api/
│     ├─ adapter/
│     ├─ domain/
│     ├─ event/
│     ├─ io/
│     ├─ plugin/
│     ├─ storage/
│     └─ web/
├─ tests/
├─ docs/
│  ├─ architecture/
│  ├─ implementation/
│  └─ local/
├─ examples/
├─ assets/
├─ web/
│  ├─ static/
│  └─ templates/
└─ data/
   └─ .gitkeep
```

说明：

- `src/project_name/` 是现代 Python 项目的默认推荐布局。
- 如果历史项目已经使用 `ProjectName/` 作为包目录，可以保留，但新代码仍应按模块职责拆分。
- `web/` 可以在根目录，也可以在包内；若需要打包发布，优先放入包内并明确资源加载方式。
- `data/` 默认只提交目录占位或示例，不提交真实运行数据。
- `docs/local/` 用于本地说明、启动包说明、AI 协作记录等不应公开的内容。

## 4. 入口标准

根目录 `main.py` 只负责：

- 设置最小必要的运行环境；
- 加载配置；
- 调用包内启动函数；
- 输出启动失败的明确错误。

示例：

```python
# -*- coding: utf-8 -*-
"""ProjectName startup entry."""

from project_name.core import run


def main() -> None:
    run()


if __name__ == "__main__":
    main()
```

不应在 `main.py` 中长期放置：

- 数据库表结构；
- API 路由；
- 大量命令行交互；
- 业务规则；
- 插件扫描细节；
- UI 资源拼接；
- 宽泛异常吞噬。

## 5. 模块职责

### `core.py`

项目运行编排层。负责把配置、服务、管理器连接起来，但不放具体业务细节。

### `api/`

HTTP API、MCP API、CLI API 等外部接口层。只做参数校验、权限检查、响应转换和服务调用。

### `adapter/`

外部系统适配层，例如 OneBot、MCP、文件系统观察器、第三方 API、模型 Provider。

### `domain/`

领域模型、ID、枚举、不可变规则、核心数据结构。这里的代码应该尽量不依赖框架。

### `event/`

事件定义、事件总线、内部通知。没有明确事件流时不要提前创建复杂事件系统。

### `plugin/`

插件基类、插件加载、插件注册。没有插件机制时不要为了目录完整而空放框架。

### `storage/`

数据库、文件存储、索引存储、仓库读写。这里负责持久化，但不直接决定业务审批规则。

### `io/`

路径解析、文件读取、导入导出、编码处理。安全边界必须集中在这里。

### `web/`

前端静态页面、模板、Web 面板相关资源。复杂前端项目可以独立成根目录 `web/`。

### `util.py`

只放纯工具函数。若一个函数已经属于路径、存储、领域、API、配置中的任何一类，不放入 `util.py`。

## 6. 命名标准

- Python 包名：新项目使用小写蛇形，如 `rhine_vault`。
- 历史包名：已有 `Ptilopsis`、`AcgDraw` 这类包名可以保留，不强制迁移。
- 模块名：小写蛇形，如 `capture_service.py`、`path_resolver.py`。
- 类名：大驼峰，如 `CaptureService`、`PluginManager`。
- 函数和变量：小写蛇形，如 `load_config`、`workspace_id`。
- 常量：大写蛇形，如 `DEFAULT_TIMEOUT`。
- 管理器：确实持有生命周期或注册表时使用 `Manager`，普通函数集合不要叫 Manager。
- 基类：用于扩展点时使用 `Base`，例如 `BaseAdapter`、`BasePlugin`。

## 7. 配置与运行数据

推荐：

```text
conf/
├─ config.example.json
└─ README.md

data/
└─ .gitkeep
```

规则：

- 提交示例配置，不提交私有配置。
- 私有配置使用 `.env`、`config.local.json` 或系统环境变量，并加入 `.gitignore`。
- 数据库、缓存、日志、用户上传文件、索引文件默认不提交。
- 配置读取集中在一个模块，不在各处直接读环境变量或 JSON 文件。

## 8. 日志与错误处理

- 面向用户的日志可以中文，便于自己调试和后续维护。
- 日志信息应说明“发生了什么”和“下一步可检查什么”。
- 不要静默吞错；如果要降级，必须记录原因。
- 捕获异常时尽量捕获具体类型。
- 服务端代码不要用 `print` 作为主要日志方式。

## 9. README 标准

README 推荐结构：

```text
居中标题 / Logo
徽章
一句话定位
项目简介
核心功能
项目结构
安装与启动
配置说明
开发命令
API 或使用示例
技术栈
当前状态
许可证
```

README 不应保存：

- Codex 首次启动提示词；
- 私有任务清单；
- 本地路径；
- 未公开的开发讨论；
- 临时迁移记录。

这些内容应放入 `docs/local/`、`docs/discussion/` 或对应实施文档。

## 10. 测试与质量检查

新项目推荐至少提供：

```text
tests/
├─ test_domain.py
├─ test_io.py
└─ test_api.py
```

推荐命令：

```powershell
pytest
ruff check .
ruff format --check .
mypy src
```

历史项目可以逐步补齐，不要求一次性完全迁移，但新改动应尽量带测试。

## 11. Git 忽略标准

至少忽略：

```gitignore
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
.mypy_cache/
.env
*.local.*
*.sqlite
*.sqlite3
data/*
!data/.gitkeep
logs/
docs/local/
docs/discussion/
```

项目若使用 AI 协作，还应忽略：

```gitignore
AGENTS.md
TASK.md
PROMPTS/
reference-packages/
```

是否忽略 `docs/discussion/` 取决于项目是否希望公开设计讨论。私有仓库可保留，公开仓库建议忽略。

## 12. 迁移清单

整理旧项目时按以下顺序做，避免一次性大爆炸式重构：

1. 固定当前行为，先补最小测试或手动验收脚本。
2. 整理 `.gitignore`，移出运行数据、缓存、本地配置。
3. 把 README 改成项目介绍，把私有说明迁到 `docs/local/`。
4. 建立或瘦身根目录 `main.py`。
5. 把业务逻辑从入口文件移入项目包。
6. 按职责拆分 `core`、`api`、`domain`、`storage`、`adapter` 等模块。
7. 替换宽泛异常、魔法 debug 标志和全局运行态。
8. 补充 lint、format、类型检查和测试命令。
9. 更新文档中的项目结构图。
10. 最后再考虑包名、构建系统或发布方式迁移。

## 13. 项目落地记录模板

每个项目可以在自己的 `docs/implementation/STYLE_ADOPTION.md` 中记录：

```text
# Style Adoption

## 项目

- Name:
- Repository:
- Current status:

## 已采用

- [ ] README 展示结构
- [ ] 根目录 main.py
- [ ] 清晰项目包
- [ ] docs / examples / tests 分离
- [ ] 运行数据忽略
- [ ] lint / format / test 命令

## 暂不迁移

- Reason:

## 已知历史问题

- Issue:
- Risk:
- Plan:

## 下一步

1.
2.
3.
```

## 14. Rhine-Vault 当前应用说明

Rhine-Vault 当前应保留 `src/rhine_vault` 现代包布局，不为了模仿历史项目改成根目录业务包。

可以优先补齐：

- 根目录 `main.py`；
- 包内 `core.py`；
- 更清晰的 Web/static 资源位置；
- README 与开发命令一致性；
- 后续 Phase 再决定是否引入 `adapter` / `event` / `plugin` 等扩展目录。

任何结构迁移都不得改变 Rhine-Vault 已冻结的架构约束，包括：

- 每个操作显式携带 `workspace_id`；
- AI 只能写 staging；
- 正式知识必须人工批准；
- Markdown、SQLite、Git 权威职责分离；
- Phase 1.5 不提前实现 Phase 2 能力。
