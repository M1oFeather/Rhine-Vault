# V1.0 验收标准

## 工作区

- 创建两个 Project 和一个 Library；
- 无声明依赖时无法跨库搜索；
- 非法 workspace_id 和路径穿越被拒绝。

## 编辑与审批

- UI 编辑不会直接改正式文件；
- 保存只进入 staging；
- 批准生成 revision、Git commit、AuditEvent、IndexJob；
- revision 冲突被阻止；
- 外部编辑生成 ExternalChange；
- 未批准内容不进入检索。

## 检索

- 精确、FTS、metadata 可用；
- Weighted RRF 可解释；
- Context Bundle 四层输出；
- profile 可切换；
- canonical 冲突产生 warning 或阻断；
- relation depth 与 token budget 生效。

## Git

- 单节点批准一个 commit；
- 回滚产生新 revision 和新 commit；
- 外部 Git 修改不自动发布；
- dirty tree 状态可见。

## Library

- Library 发布 Snapshot 可被项目锁定；
- lock 记录 version/tag/commit/manifest；
- Library 更新不自动影响项目；
- 升级需报告与批准。

## 恢复

- 可导出 `.rhine`；
- 可在临时目录验证；
- SQLite 删除后可重建当前正式节点；
- 向量索引删除后系统仍可运行；
- inconsistent 状态阻止发布。


# Phase 1.5 补充验收

- 可通过极简 UI 创建或导入节点；
- 可保存 staging；
- 可人工批准；
- 已批准节点可被 FTS 检索；
- 可生成 Context Bundle v0；
- FakeLLM 可完成端到端集成测试；
- OpenAI-compatible Provider 可选启用；
- UI 显示引用来源；
- 未配置真实 LLM 时系统仍可完整测试；
- 不依赖 ChromaDB；
- 不提前实现正式 Git 事务和 MCP。


# Knowledge Capture 验收

## 对话录入

- 用户可提交一段对话；
- 系统生成 Capture Proposal；
- 候选节点可编辑；
- 来源 session/message 范围可追溯；
- 未批准候选不进入正式检索；
- 批准后可被搜索和引用。

## 文档导入

- 支持 Markdown/TXT；
- 文件 hash 被记录；
- heading path 与 line range 可追溯；
- 可批量审核；
- 同一文件重复导入可被识别。

## 项目导入

- 支持本地目录扫描；
- ignore 规则生效；
- 文件树可预览和筛选；
- Source Index 与 Curated Knowledge 分离；
- 至少可生成项目概览、模块说明和约束候选。

## LLM

- FakeLLM 完成端到端测试；
- 真实 LLM 未配置时不影响系统测试；
- 回答显示引用节点和来源。
