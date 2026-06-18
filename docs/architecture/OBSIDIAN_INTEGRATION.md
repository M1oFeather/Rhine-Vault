# Obsidian 兼容与 UI 可选集成

## 定位

Obsidian 是可选外部 Markdown 编辑器，不是 Rhine-Vault 核心依赖。

Rhine-Vault 自带 UI 负责：

- 正式编辑；
- staging；
- Diff；
- 审批；
- Git；
- 版本历史；
- 关系管理；
- 检索配置；
- 索引状态。

## 基础兼容

- 标准 Markdown；
- YAML Frontmatter；
- 相对资源路径；
- `[[node_id]]`；
- `[[node_id|显示标题]]`；
- 稳定文件名；
- Obsidian 可直接打开 workspace 目录。

YAML relations 是正式关系源；Wiki Link 和 backlinks 只用于人工阅读与导航。

## UI 可选集成

可提供：

- 启用 Obsidian 兼容模式；
- 检测 Obsidian 是否安装；
- 在 Obsidian 中打开工作区；
- 在 Obsidian 中打开当前节点；
- 复制 Wiki Link；
- 展示外部修改待审批数量；
- 跳转 ExternalChange Diff。

## 可选插件

后续可开发轻量插件，仅负责：

- 显示当前 revision；
- 显示未批准修改状态；
- 提交当前文件为 staging；
- 打开 Rhine-Vault Diff/审批页面；
- 查看局部关系。

插件不得：

- 直接批准；
- 直接 Git commit；
- 修改正式数据库；
- 绕过 ExternalChange；
- 直接触发正式索引。
