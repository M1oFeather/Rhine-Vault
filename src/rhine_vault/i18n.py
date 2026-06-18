"""Minimal native i18n catalog for the Phase 1.5 UI."""

from __future__ import annotations

from typing import Literal

Locale = Literal["zh", "en"]

DEFAULT_LOCALE: Locale = "zh"
SUPPORTED_LOCALES: tuple[Locale, ...] = ("zh", "en")

TRANSLATIONS: dict[Locale, dict[str, str]] = {
    "zh": {
        "app.title": "Rhine-Vault Phase 1.5",
        "language.label": "语言",
        "nav.manual": "手动节点编辑",
        "nav.conversation": "对话采集",
        "nav.document": "文档导入",
        "nav.project": "项目导入",
        "nav.review": "候选知识审核",
        "nav.search": "搜索实验台",
        "nav.context": "Context Bundle",
        "nav.llm": "LLM 调试台",
        "manual.title": "手动节点编辑",
        "manual.title.placeholder": "标题",
        "manual.type.label": "节点类型",
        "manual.content.placeholder": "Markdown 内容",
        "manual.save": "保存为候选知识",
        "manual.title.required": "请先填写标题。",
        "conversation.title": "对话采集",
        "conversation.session.label": "会话 ID",
        "conversation.role.label": "角色",
        "conversation.role.user": "用户",
        "conversation.role.assistant": "助手",
        "conversation.role.system": "系统",
        "conversation.message.placeholder": "输入一条对话消息",
        "conversation.add": "添加消息",
        "conversation.clear": "清空消息",
        "conversation.capture": "采集对话",
        "conversation.empty": "请先添加至少一条消息。",
        "conversation.seed.user": "Agent 能直接批准正式知识吗?",
        "conversation.seed.assistant": (
            "不能。Agent 只能生成候选知识和 staging, 正式知识必须人工批准。"
        ),
        "document.title": "文档导入",
        "document.path.placeholder": "Markdown/TXT 文件路径",
        "document.import": "导入",
        "project.title": "项目导入",
        "project.root.placeholder": "项目根目录",
        "project.scan": "扫描",
        "review.title": "候选知识审核",
        "review.load": "加载候选知识",
        "review.proposal.label": "选择 proposal",
        "review.temp_ids.label": "选择候选节点",
        "review.stage": "保存为 staging",
        "review.load_staging": "加载 staging",
        "review.entry_ids.label": "选择 staging 条目",
        "review.approve": "批准 staging",
        "review.reject": "驳回 proposal",
        "search.title": "搜索实验台",
        "search.query.placeholder": "查询",
        "search.submit": "搜索",
        "context.title": "Context Bundle 查看器",
        "context.query.placeholder": "问题",
        "context.build": "构建",
        "llm.title": "LLM 调试台",
        "llm.query.placeholder": "问题",
        "llm.ask": "询问 FakeLLM",
        "output.placeholder": "结果会显示在这里。",
    },
    "en": {
        "app.title": "Rhine-Vault Phase 1.5",
        "language.label": "Language",
        "nav.manual": "Manual Node Editor",
        "nav.conversation": "Conversation Capture",
        "nav.document": "Document Import",
        "nav.project": "Project Import",
        "nav.review": "Proposal Review",
        "nav.search": "Search Lab",
        "nav.context": "Context Bundle",
        "nav.llm": "LLM Playground",
        "manual.title": "Manual Node Editor",
        "manual.title.placeholder": "Title",
        "manual.type.label": "Node type",
        "manual.content.placeholder": "Markdown content",
        "manual.save": "Save Proposal",
        "manual.title.required": "Please enter a title first.",
        "conversation.title": "Conversation Capture",
        "conversation.session.label": "Session ID",
        "conversation.role.label": "Role",
        "conversation.role.user": "User",
        "conversation.role.assistant": "Assistant",
        "conversation.role.system": "System",
        "conversation.message.placeholder": "Enter one conversation message",
        "conversation.add": "Add message",
        "conversation.clear": "Clear messages",
        "conversation.capture": "Capture conversation",
        "conversation.empty": "Add at least one message first.",
        "conversation.seed.user": "Can an Agent approve formal knowledge directly?",
        "conversation.seed.assistant": (
            "No. Agents can only generate candidate knowledge and staging; "
            "formal knowledge requires human approval."
        ),
        "document.title": "Document Import",
        "document.path.placeholder": "Markdown/TXT path",
        "document.import": "Import",
        "project.title": "Project Import",
        "project.root.placeholder": "Project root",
        "project.scan": "Scan",
        "review.title": "Proposal Review",
        "review.load": "Load Proposals",
        "review.proposal.label": "Select proposal",
        "review.temp_ids.label": "Select proposed nodes",
        "review.stage": "Save Staging",
        "review.load_staging": "Load Staging",
        "review.entry_ids.label": "Select staging entries",
        "review.approve": "Approve Staging",
        "review.reject": "Reject Proposal",
        "search.title": "Search Lab",
        "search.query.placeholder": "Query",
        "search.submit": "Search",
        "context.title": "Context Bundle Viewer",
        "context.query.placeholder": "Question",
        "context.build": "Build",
        "llm.title": "LLM Playground",
        "llm.query.placeholder": "Question",
        "llm.ask": "Ask FakeLLM",
        "output.placeholder": "Results will appear here.",
    },
}


def normalize_locale(locale: str | None) -> Locale:
    if not locale:
        return DEFAULT_LOCALE
    normalized = locale.strip().lower().split(",", maxsplit=1)[0]
    if normalized.startswith("zh"):
        return "zh"
    if normalized.startswith("en"):
        return "en"
    return DEFAULT_LOCALE


def translation_catalog(locale: str | None = None) -> dict[str, str]:
    selected = normalize_locale(locale)
    return dict(TRANSLATIONS[selected])
