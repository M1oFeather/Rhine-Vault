# 实施风险登记

## R-001 Git 与 SQLite 跨系统事务

风险：SQLite 已提交但 Git commit 失败，或反之。

要求：
- 设计发布状态机；
- 使用 operation_id；
- 支持补偿与恢复；
- 不宣称跨系统 ACID；
- 失败必须可见且可恢复。

## R-002 多文件 ChangeSet

风险：部分文件写入成功。

要求：
- 临时目录；
- 全量校验；
- 批量切换；
- 补偿事务；
- Git commit 前一致性验证。

## R-003 外部文件修改

风险：恢复 approved 文件时覆盖用户尚未保存的外部内容。

要求：
- 先复制 ExternalChange snapshot；
- 校验 snapshot hash；
- 再恢复 approved 内容；
- 保留 rejected recovery area。

## R-004 MCP SDK 演进

要求：
- 编码前锁定 SDK；
- 记录 protocol version；
- 使用官方 SDK；
- stdio 与 Streamable HTTP 分开测试。

## R-005 混合语料检索

要求：
- Phase 1 不引入向量；
- 先完成 FTS 与结构化检索；
- 后续用真实中英代码样本评测 embedding。

## R-006 .rhine 加密

要求：
- 使用成熟库；
- 不自行设计算法；
- V1 可先完成未加密格式与接口预留。
