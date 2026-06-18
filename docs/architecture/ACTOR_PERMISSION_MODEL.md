# Actor、权限与审批模型

## User 与 Actor

- User：真实操作者；
- Actor：实际执行动作的主体。

Actor 类型：

- human
- ui
- agent
- external_editor
- git
- system
- indexer
- migration
- plugin

## V1 角色

- viewer
- editor
- reviewer
- admin

V1 可只有一个 `local-owner`，但仍必须区分不同 Actor。

## Agent Capability

Agent 不继承本地管理员权限。可授予：

- read_nodes
- search_nodes
- build_context
- submit_staging
- revise_own_staging

禁止：

- approve_staging
- publish_node
- rollback_node
- execute_git
- modify_permissions

## 审批策略

Workspace 可配置：

- required_reviewers；
- self_approval_allowed；
- require_diff_viewed；
- require_validation_passed；
- require_git_clean；
- require_relation_check；
- require_impact_analysis。

Library 默认比 Project 更严格。

## 审计

所有关键操作记录：

- user_id；
- actor_type / actor_id；
- on_behalf_of；
- workspace；
- action；
- resource；
- before/after hash；
- request_id；
- Git commit；
- result。

MCP 根据 Session Capability 动态暴露工具。
