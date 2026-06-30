"""Novel Studio WebUI plugin helpers.

Novel Studio is intentionally layered above the formal knowledge core. It can
project, generate, and inspect writing artifacts, but any durable knowledge it
creates still enters Rhine-Vault through the normal proposal/staging workflow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rhine_vault.capture.service import CaptureService
from rhine_vault.context import ContextBundle

ARTIFACT_NODE_TYPES: dict[str, str] = {
    "worldbuilding": "Worldbuilding",
    "character": "CharacterCard",
    "timeline": "TimelineEvent",
    "outline": "OutlineBeat",
    "chapter": "ChapterDraft",
    "foreshadowing": "ForeshadowingThread",
}


@dataclass(frozen=True)
class NovelArtifactInput:
    artifact_type: str
    title: str
    content: str
    tags: tuple[str, ...] = ()
    fields: dict[str, Any] | None = None


@dataclass(frozen=True)
class ChapterGenerationInput:
    project_title: str
    chapter_title: str
    chapter_number: int = 1
    outline: str = ""
    pov_character: str = ""
    tone: str = ""
    target_words: int = 1200
    extra_constraints: tuple[str, ...] = ()


def create_novel_artifact_proposal(
    *,
    capture: CaptureService,
    workspace_id: str,
    artifact: NovelArtifactInput,
) -> dict[str, Any]:
    node_type = _node_type_for_artifact(artifact.artifact_type)
    body = _render_artifact_markdown(artifact)
    tags = _dedupe_tags(("novel", artifact.artifact_type, *artifact.tags))
    return capture.create_manual_proposal(
        workspace_id=workspace_id,
        title=artifact.title,
        node_type=node_type,
        content=body,
        authority="reference",
        tags=tags,
    )


def generate_chapter_draft(
    context_bundle: ContextBundle,
    *,
    generation: ChapterGenerationInput,
) -> dict[str, Any]:
    nodes = _bundle_nodes(context_bundle)
    citations = _node_ids(nodes)
    constraints = [_compact_node_line(node) for node in context_bundle.mandatory_constraints]
    knowledge = [_compact_node_line(node) for node in context_bundle.relevant_context]
    warnings = list(context_bundle.warnings)
    if not nodes:
        warnings.append("No approved story knowledge was available for this generation.")

    title = generation.chapter_title.strip() or f"Chapter {generation.chapter_number}"
    project_title = generation.project_title.strip() or context_bundle.workspace_id
    pov = generation.pov_character.strip() or "unspecified POV"
    tone = generation.tone.strip() or "stable, clear, and consistent with approved canon"
    outline = generation.outline.strip() or "Advance the chapter around approved context."

    draft_lines = [
        f"# {title}",
        "",
        f"- Project: {project_title}",
        f"- Chapter: {generation.chapter_number}",
        f"- POV: {pov}",
        f"- Tone: {tone}",
        f"- Target words: {max(generation.target_words, 1)}",
        "",
        "## Approved Context Anchors",
        "",
    ]
    if knowledge:
        draft_lines.extend(f"- {item}" for item in knowledge[:12])
    else:
        draft_lines.append(
            "- No approved context yet. Add worldbuilding, characters, or outline beats first."
        )
    if constraints or generation.extra_constraints:
        draft_lines.extend(["", "## Constraints", ""])
        draft_lines.extend(f"- {item}" for item in constraints)
        draft_lines.extend(f"- {item}" for item in generation.extra_constraints if item.strip())
    draft_lines.extend(
        [
            "",
            "## Outline",
            "",
            outline,
            "",
            "## Draft",
            "",
            _draft_opening(title=title, pov=pov, tone=tone, anchors=knowledge),
            "",
            _draft_middle(outline=outline, anchors=knowledge),
            "",
            _draft_close(title=title, anchors=knowledge),
            "",
            "## Revision Checklist",
            "",
            "- Check whether character motivation matches approved character cards.",
            "- Check whether chapter events violate approved worldbuilding rules.",
            "- Check whether foreshadowing has a clear payoff plan.",
            "- Reverse-extract confirmed new facts as candidates before treating them as canon.",
        ]
    )

    return {
        "kind": "novel-chapter-draft",
        "format": "markdown",
        "workspace_id": context_bundle.workspace_id,
        "title": title,
        "markdown": "\n".join(draft_lines),
        "citations": citations,
        "source_refs": list(context_bundle.supporting_references),
        "warnings": warnings,
        "context_bundle": context_bundle.to_dict(),
    }


def build_consistency_report(
    context_bundle: ContextBundle,
    *,
    manuscript: str,
    strictness: str = "normal",
) -> dict[str, Any]:
    text = manuscript.strip()
    nodes = _bundle_nodes(context_bundle)
    issues: list[dict[str, Any]] = []

    if not text:
        issues.append(
            {
                "severity": "error",
                "code": "EMPTY_MANUSCRIPT",
                "message": "Manuscript text is empty.",
            }
        )
    for marker in ("TODO", "???", "TBD", "placeholder"):
        if marker.lower() in text.lower():
            issues.append(
                {
                    "severity": "warning",
                    "code": "DRAFT_MARKER",
                    "message": f"Draft marker found: {marker}",
                }
            )

    for node in nodes:
        node_type = str(node.get("node_type", ""))
        title = str(node.get("title", ""))
        if node_type in {"CharacterCard", "Worldbuilding", "TimelineEvent", "OutlineBeat"}:
            terms = _significant_terms(title)
            if terms and not any(term in text for term in terms):
                issues.append(
                    {
                        "severity": "info" if strictness != "strict" else "warning",
                        "code": "UNUSED_APPROVED_CONTEXT",
                        "node_id": node.get("node_id"),
                        "message": f"Approved {node_type} may not be reflected: {title}",
                    }
                )
        content = str(node.get("content", ""))
        for forbidden in _forbidden_terms(content):
            if forbidden and forbidden in text:
                issues.append(
                    {
                        "severity": "error",
                        "code": "FORBIDDEN_TERM_PRESENT",
                        "node_id": node.get("node_id"),
                        "message": f"Manuscript contains a forbidden approved term: {forbidden}",
                    }
                )

    return {
        "kind": "novel-consistency-report",
        "workspace_id": context_bundle.workspace_id,
        "strictness": strictness,
        "issue_count": len(issues),
        "issues": issues,
        "checked_node_ids": _node_ids(nodes),
        "warnings": list(context_bundle.warnings),
        "context_bundle": context_bundle.to_dict(),
    }


def build_foreshadowing_report(
    context_bundle: ContextBundle,
    *,
    manuscript: str,
    planned_payoffs: tuple[str, ...] = (),
) -> dict[str, Any]:
    text = manuscript.strip()
    cues = _foreshadowing_cues(text)
    planned = [item.strip() for item in planned_payoffs if item.strip()]
    callbacks = [payoff for payoff in planned if payoff and payoff in text]
    unresolved = [cue for cue in cues if not any(_shares_term(cue, payoff) for payoff in planned)]
    context_threads = [
        node
        for node in _bundle_nodes(context_bundle)
        if str(node.get("node_type")) == "ForeshadowingThread"
    ]
    return {
        "kind": "novel-foreshadowing-report",
        "workspace_id": context_bundle.workspace_id,
        "cues": cues,
        "planned_payoffs": planned,
        "callbacks": callbacks,
        "unresolved_cues": unresolved,
        "approved_threads": [
            {
                "node_id": node.get("node_id"),
                "title": node.get("title"),
                "authority": node.get("authority"),
            }
            for node in context_threads
        ],
        "citations": _node_ids(context_threads),
        "warnings": list(context_bundle.warnings),
    }


def extract_chapter_knowledge_proposal(
    *,
    capture: CaptureService,
    workspace_id: str,
    chapter_title: str,
    chapter_text: str,
    tags: tuple[str, ...] = (),
) -> dict[str, Any]:
    cleaned_title = chapter_title.strip() or "Chapter extracted knowledge"
    extracted = _chapter_extraction_markdown(cleaned_title, chapter_text)
    return capture.create_manual_proposal(
        workspace_id=workspace_id,
        title=f"{cleaned_title} extracted knowledge",
        node_type="ChapterKnowledge",
        content=extracted,
        authority="experimental",
        tags=_dedupe_tags(("novel", "chapter-extraction", *tags)),
    )


def _node_type_for_artifact(artifact_type: str) -> str:
    cleaned = artifact_type.strip().lower()
    if cleaned not in ARTIFACT_NODE_TYPES:
        raise ValueError(f"unknown novel artifact type: {artifact_type}")
    return ARTIFACT_NODE_TYPES[cleaned]


def _render_artifact_markdown(artifact: NovelArtifactInput) -> str:
    fields = artifact.fields or {}
    lines = [artifact.content.strip()]
    if fields:
        lines.extend(["", "## Structured Fields", ""])
        for key in sorted(fields):
            value = fields[key]
            if isinstance(value, list):
                rendered = ", ".join(str(item) for item in value)
            else:
                rendered = str(value)
            lines.append(f"- {key}: {rendered}")
    return "\n".join(line for line in lines if line is not None).strip()


def _bundle_nodes(context_bundle: ContextBundle) -> list[dict[str, Any]]:
    return list(context_bundle.mandatory_constraints) + list(context_bundle.relevant_context)


def _node_ids(nodes: list[dict[str, Any]]) -> list[str]:
    return [str(node["node_id"]) for node in nodes if "node_id" in node]


def _compact_node_line(node: dict[str, Any]) -> str:
    title = str(node.get("title", node.get("node_id", "Untitled")))
    node_id = str(node.get("node_id", "unknown"))
    content = " ".join(str(node.get("content", "")).split())
    if len(content) > 160:
        content = f"{content[:160]}..."
    return f"{title} (`{node_id}`): {content}"


def _draft_opening(*, title: str, pov: str, tone: str, anchors: list[str]) -> str:
    anchor = anchors[0] if anchors else "the current scene still lacks an approved anchor"
    return (
        f"{title} opens through {pov}, keeping the tone {tone}. "
        f"The first movement should ground the reader in approved context: {anchor}"
    )


def _draft_middle(*, outline: str, anchors: list[str]) -> str:
    anchor = anchors[1] if len(anchors) > 1 else "advance the current chapter conflict"
    return (
        f"The middle develops the outline: {outline} "
        f"Character action must create traceable consequences. Preferred anchor: {anchor}"
    )


def _draft_close(*, title: str, anchors: list[str]) -> str:
    anchor = anchors[2] if len(anchors) > 2 else "leave one recoverable clue"
    return (
        f"{title} closes the visible chapter goal while leaving a checkable hook "
        f"for the next chapter. Closing anchor: {anchor}"
    )


def _significant_terms(title: str) -> list[str]:
    parts = [
        item.strip(" ,.?!()[]`")
        for item in title.replace("/", " ").replace("-", " ").split()
    ]
    if len(parts) == 1 and len(parts[0]) > 8:
        return [parts[0]]
    return [part for part in parts if len(part) >= 2][:4]


def _forbidden_terms(content: str) -> list[str]:
    terms: list[str] = []
    markers = ("must not", "cannot", "forbid", "forbidden", "never use")
    for line in content.splitlines():
        lowered = line.lower()
        if any(marker in lowered for marker in markers):
            terms.extend(_quoted_terms(line))
    return terms


def _quoted_terms(line: str) -> list[str]:
    terms: list[str] = []
    for left, right in (('"', '"'), ("'", "'"), ("`", "`")):
        cursor = 0
        while True:
            start = line.find(left, cursor)
            if start < 0:
                break
            end = line.find(right, start + len(left))
            if end < 0:
                break
            term = line[start + len(left) : end].strip()
            if term:
                terms.append(term)
            cursor = end + len(right)
    return terms


def _foreshadowing_cues(text: str) -> list[dict[str, str]]:
    cues: list[dict[str, str]] = []
    keywords = ("foreshadow", "clue", "omen", "hint", "suspense", "anomaly", "mark")
    for index, sentence in enumerate(_sentences(text), start=1):
        if any(keyword in sentence.lower() for keyword in keywords):
            cues.append({"id": f"cue-{index}", "text": sentence})
    return cues[:20]


def _sentences(text: str) -> list[str]:
    normalized = text.replace(". ", ".\n").replace("! ", "!\n").replace("? ", "?\n")
    return [line.strip() for line in normalized.splitlines() if line.strip()]


def _shares_term(cue: dict[str, str], payoff: str) -> bool:
    cue_text = cue.get("text", "")
    return any(term and term.lower() in cue_text.lower() for term in _significant_terms(payoff))


def _chapter_extraction_markdown(chapter_title: str, chapter_text: str) -> str:
    lines = [
        f"# {chapter_title} extracted knowledge",
        "",
        "## Candidate Facts",
        "",
    ]
    sentences = _sentences(chapter_text)
    extraction_keywords = (
        "setting",
        "rule",
        "character",
        "place",
        "time",
        "relationship",
        "promise",
        "foreshadow",
        "clue",
    )
    candidates = [
        sentence
        for sentence in sentences
        if any(keyword in sentence.lower() for keyword in extraction_keywords)
    ][:12]
    if candidates:
        lines.extend(f"- {candidate}" for candidate in candidates)
    else:
        lines.append("- No explicit candidate fact was detected. Add review notes manually.")
    lines.extend(
        [
            "",
            "## Review Notes",
            "",
            "- This node is extracted from a chapter draft and starts as experimental knowledge.",
            "- Human review must split, rewrite, or reject items before they become canon.",
        ]
    )
    return "\n".join(lines)


def _dedupe_tags(tags: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        cleaned = tag.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return tuple(result)
