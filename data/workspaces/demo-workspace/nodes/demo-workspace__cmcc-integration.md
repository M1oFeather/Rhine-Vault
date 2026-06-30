---
workspace_id: demo-workspace
node_id: demo-workspace.cmcc-integration
node_type: IntegrationBoundary
title: CMCC 对接用途
authority: approved
status: active
revision: 1
tags: ["ptilopsis", "cmcc", "integration", "bot"]
source_refs: [{"type": "seed_pack", "source_id": "5651982b-6179-49bd-bb3c-a45bc66823b5"}, {"type": "web", "url": "https://prts.wiki/w/%E7%99%BD%E9%9D%A2%E9%B8%AE"}]
relations: [{"relation_type": "references", "target_node_id": "demo-workspace.dialogue-style"}]
---

# CMCC 对接用途

Ptilopsis 的 CMCCPlugin 更适合作为前端 AI 记忆与人格防线；Rhine-Vault 更适合作为可审计、可修改、可引用的后端知识库。对接时 CMCCPlugin 应请求 Rhine-Vault 的 approved context，并把返回内容作为可引用资料加入 prompt，而不是让机器人插件直接修改 Rhine-Vault 正式知识。
