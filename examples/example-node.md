---
node_id: spectrum.mechanic.rgb-complement
workspace_id: spectrum-protocol
node_type: GameMechanic
title: RGB 补色与 White 终结
status: active
revision: 1
schema_version: 1
created_at: 2026-06-17T13:00:00+08:00
updated_at: 2026-06-17T13:00:00+08:00
tags:
  - combat
  - rgb
  - core-mechanic
relations:
  - target: spectrum.mechanic.white-finish
    type: interacts_with
    direction: outgoing
    description: 当颜色通道补全后进入 White 终结条件
source:
  type: human_reviewed
  origin: architecture-package
  reference: design-baseline-v2.1
---

玩家使用 R、G、B 三类攻击补全目标缺失的颜色通道。当目标达到完整白光状态后，可触发 White 终结。

该机制不是简单的属性克制，而是战斗、救赎叙事与敌人模块状态的统一底层规则。
