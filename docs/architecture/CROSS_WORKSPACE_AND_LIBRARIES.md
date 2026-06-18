# 跨工作区、Library 与共享知识

## 工作区类型

### Project Workspace

项目私有知识域，可编辑并拥有独立 Git 历史。

### Library Workspace

共享知识域，供多个项目只读依赖。下游不得直接修改，只能提交 LibraryChangeProposal。

## 跨工作区原则

- 默认关闭跨工作区访问；
- 只能通过显式 dependency 启用；
- 引用必须包含依赖别名与 NodeID；
- 实际版本由 `rhine-lock.yaml` 解析；
- Context Bundle 必须标记来源工作区和版本。

## 本地覆盖

项目可建立 override 节点，但必须同时保留：

- Library 原规则；
- Project override；
- 最终 effective rule；
- 覆盖原因。

## 跨库检索

由 Retrieval Profile 控制：

- allowed dependencies；
- max library nodes；
- library score multiplier；
- prefer local nodes。

## Git

V1 默认每个工作区独立 Git 仓库。Library 使用独立仓库和发布标签。
