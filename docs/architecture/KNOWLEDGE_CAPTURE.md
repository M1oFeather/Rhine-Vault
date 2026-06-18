# Knowledge Capture Architecture

## 核心边界

```text
Source ≠ Capture Proposal ≠ MemoryNode
```

### Source

原始材料，可能噪声高、结构不稳定。

### Capture Proposal

AI 或规则系统生成的候选知识，尚未批准。

### MemoryNode

人工审核后的正式稳定知识。

## 来源类型

- manual
- conversation
- document
- project_file
- external_import

## 录入原则

- 任何 AI 提取结果只能进入 proposal/staging；
- 不得自动发布；
- 必须保留来源定位；
- 必须允许用户修改；
- 批量操作应使用 Batch Review；
- 正式知识与原始 Source 可独立更新和归档。

## 项目摄取双层模型

```text
Project Source
├── Source Index
└── Curated Knowledge
```

Source Index 用于细节搜索；Curated Knowledge 用于稳定项目记忆。
