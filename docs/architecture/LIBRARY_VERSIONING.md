# Library 发布、版本与依赖锁定

## 四种标识

- Semantic Version：人类可读发布版本；
- Git Tag：仓库发布锚点；
- Commit Hash：精确复现；
- Node Revision：单节点内部版本。

## 依赖文件

`workspace.yaml` 表达用户意图：

```yaml
dependencies:
  - workspace_id: library-neoforge-1.21.1
    version: "~1.3.0"
```

`rhine-lock.yaml` 保存解析结果：

```yaml
dependencies:
  library-neoforge-1.21.1:
    resolved_version: 1.3.2
    git_tag: v1.3.2
    commit: 3a79c18f
    manifest_hash: sha256:...
```

## 发布流程

```text
节点 ChangeSet
→ 审批
→ 选择 SemVer
→ Git commit
→ 创建不可变 Tag
→ 生成 Manifest
→ 发布只读 Snapshot
```

## 发布快照

下游项目只能读取 Published Snapshot，不得读取 Library 当前工作树。

## 升级

检测到新版本后：

- 生成升级报告；
- 列出实际引用节点变化；
- 分析 canonical、relation、supersedes；
- 生成升级 ChangeSet；
- 用户批准；
- 更新 lock；
- Git commit；
- 重建相关索引。

禁止静默升级。

## V1 限制

- 不实现传递依赖自动解算；
- 所有可检索 Library 显式声明；
- 同一 Context Bundle 不混入同一 Library 的两个版本；
- 已发布版本不可重写。
