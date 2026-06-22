"""Formal retrieval pipeline for Phase 3."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rhine_vault.context import ContextBundle
from rhine_vault.domain.models import RetrievalProfile
from rhine_vault.storage.sqlite import SQLiteStore
from rhine_vault.vector import HashEmbeddingProvider, search_index_chunks

PROFILE_PRESETS: dict[str, dict[str, Any]] = {
    "technical-documentation": {
        "name": "Technical Documentation",
        "exact_weight": 2.0,
        "metadata_weight": 1.3,
        "fts_weight": 1.8,
        "vector_weight": 0.0,
        "rrf_k": 60,
        "relation_depth": 1,
        "result_limit": 8,
        "mandatory_limit": 4,
        "relevant_limit": 6,
        "supporting_limit": 6,
        "conflict_strategy": "block",
    },
    "worldbuilding": {
        "name": "Worldbuilding",
        "exact_weight": 1.2,
        "metadata_weight": 1.4,
        "fts_weight": 1.2,
        "vector_weight": 0.0,
        "rrf_k": 70,
        "relation_depth": 1,
        "result_limit": 10,
        "mandatory_limit": 3,
        "relevant_limit": 8,
        "supporting_limit": 8,
        "conflict_strategy": "warn",
    },
    "semantic-knowledge-base": {
        "name": "AI Knowledge Base",
        "exact_weight": 1.4,
        "metadata_weight": 1.2,
        "fts_weight": 1.6,
        "vector_weight": 1.1,
        "rrf_k": 60,
        "relation_depth": 1,
        "result_limit": 8,
        "mandatory_limit": 4,
        "relevant_limit": 6,
        "supporting_limit": 6,
        "conflict_strategy": "warn",
    },
}

AUTHORITY_BONUS = {
    "canonical": 0.05,
    "approved": 0.03,
    "reference": 0.01,
    "historical": -0.02,
    "experimental": -0.03,
}
RELATION_TYPE_WEIGHTS = {
    "depends_on": 0.9,
    "implements": 0.85,
    "extends": 0.8,
    "supersedes": 0.75,
    "conflicts_with": 0.75,
    "references": 0.55,
}
NON_EXPANDING_RELATION_TYPES = {"related_to"}


@dataclass(frozen=True)
class RetrievalOverrides:
    profile_id: str | None = None
    relation_depth: int | None = None
    result_limit: int | None = None
    include_deprecated: bool | None = None
    node_type: str | None = None
    authority: str | None = None
    tags: tuple[str, ...] = ()
    enable_vector: bool = False


@dataclass
class ChannelCandidate:
    node: dict[str, Any]
    channel: str
    rank: int
    raw_score: float
    matched: tuple[str, ...] = ()


@dataclass
class FusedCandidate:
    node: dict[str, Any]
    channel_contributions: dict[str, dict[str, Any]] = field(default_factory=dict)
    rrf_score: float = 0.0
    rule_score: float = 0.0
    final_score: float = 0.0
    include_reason: str = "ranked"
    exclude_reason: str | None = None
    expanded_from: str | None = None
    relation_type: str | None = None


def default_retrieval_profiles(workspace_id: str) -> dict[str, RetrievalProfile]:
    return {
        profile_id: RetrievalProfile(
            profile_id=profile_id,
            workspace_id=workspace_id,
            **values,
        )
        for profile_id, values in PROFILE_PRESETS.items()
    }


def resolve_retrieval_profile(
    *,
    workspace_id: str,
    profile_id: str | None = None,
    overrides: RetrievalOverrides | None = None,
) -> RetrievalProfile:
    selected_id = profile_id or overrides.profile_id if overrides else profile_id
    profiles = default_retrieval_profiles(workspace_id)
    profile = profiles.get(
        selected_id or "technical-documentation", profiles["technical-documentation"]
    )
    updates: dict[str, Any] = {}
    if overrides is not None:
        if overrides.relation_depth is not None:
            updates["relation_depth"] = min(max(overrides.relation_depth, 0), 1)
        if overrides.result_limit is not None:
            updates["result_limit"] = min(max(overrides.result_limit, 1), 30)
        if overrides.include_deprecated is not None:
            updates["include_deprecated"] = overrides.include_deprecated
    return profile.model_copy(update=updates)


def retrieve_context_bundle(
    *,
    store: SQLiteStore,
    workspace_id: str,
    query: str,
    profile_id: str | None = None,
    overrides: RetrievalOverrides | None = None,
) -> ContextBundle:
    profile = resolve_retrieval_profile(
        workspace_id=workspace_id,
        profile_id=profile_id,
        overrides=overrides,
    )
    lab = retrieve_lab(
        store=store,
        workspace_id=workspace_id,
        query=query,
        profile=profile,
        overrides=overrides or RetrievalOverrides(),
    )
    bundle = lab["context_bundle"]
    return ContextBundle(
        workspace_id=workspace_id,
        question=query,
        mandatory_constraints=tuple(bundle["mandatory_constraints"]),
        relevant_context=tuple(bundle["relevant_context"]),
        supporting_references=tuple(bundle["supporting_references"]),
        warnings=tuple(bundle["warnings"]),
        retrieval_profile=lab["profile"],
        explain_trace=lab["explain_trace"],
    )


def retrieve_lab(
    *,
    store: SQLiteStore,
    workspace_id: str,
    query: str,
    profile: RetrievalProfile | None = None,
    overrides: RetrievalOverrides | None = None,
) -> dict[str, Any]:
    active_overrides = overrides or RetrievalOverrides()
    selected_profile = profile or resolve_retrieval_profile(
        workspace_id=workspace_id,
        profile_id=active_overrides.profile_id,
        overrides=active_overrides,
    )
    nodes = _filtered_nodes(
        store.list_memory_nodes(workspace_id),
        node_type=active_overrides.node_type,
        authority=active_overrides.authority,
        tags=active_overrides.tags,
    )
    node_by_id = {node["node_id"]: node for node in nodes}
    vector_candidates, vector_channel = _vector_candidates(
        store=store,
        workspace_id=workspace_id,
        query=query,
        node_by_id=node_by_id,
        enabled=active_overrides.enable_vector,
        weight=selected_profile.vector_weight,
    )
    channels = {
        "exact": _exact_candidates(nodes, query),
        "metadata": _metadata_candidates(nodes, query),
        "fts": _fts_candidates(store, workspace_id, query, node_by_id),
        "vector": vector_candidates,
    }
    fused = _weighted_rrf(channels=channels, profile=selected_profile)
    reranked, filtered, warnings = _rerank_and_filter(fused, selected_profile)
    expanded = _expand_relations(
        seeds=reranked,
        nodes=nodes,
        relation_depth=min(selected_profile.relation_depth, 1),
    )
    final_candidates = _merge_expanded(reranked, expanded, selected_profile.result_limit)
    final_candidates, conflict_filtered, conflict_warnings = _apply_conflict_strategy(
        final_candidates,
        node_by_id,
        selected_profile,
    )
    filtered.extend(conflict_filtered)
    warnings.extend(conflict_warnings)
    bundle = _context_bundle_payload(
        candidates=final_candidates,
        profile=selected_profile,
        warnings=warnings,
    )
    explain_trace = {
        "query": query,
        "profile_id": selected_profile.profile_id,
        "vector_channel": vector_channel,
        "channels": {
            name: [_candidate_trace(candidate) for candidate in candidates]
            for name, candidates in channels.items()
        },
        "fused_ranking": [_fused_trace(candidate) for candidate in reranked],
        "filtered": filtered,
        "relation_expansion": [_fused_trace(candidate) for candidate in expanded],
        "context_layers": {
            key: [item["node_id"] for item in value]
            for key, value in bundle.items()
            if key in {"mandatory_constraints", "relevant_context"}
        },
    }
    return {
        "profile": selected_profile.model_dump(),
        "channel_candidates": explain_trace["channels"],
        "fused_ranking": explain_trace["fused_ranking"],
        "filtered": filtered,
        "relation_expansion": explain_trace["relation_expansion"],
        "context_bundle": bundle,
        "explain_trace": explain_trace,
    }


def _filtered_nodes(
    nodes: list[dict[str, Any]],
    *,
    node_type: str | None,
    authority: str | None,
    tags: tuple[str, ...],
) -> list[dict[str, Any]]:
    required_tags = {tag.lower() for tag in tags}
    result = []
    for node in nodes:
        if node_type and node["node_type"] != node_type:
            continue
        if authority and node["authority"] != authority:
            continue
        node_tags = {str(tag).lower() for tag in node.get("tags", [])}
        if required_tags and not required_tags.issubset(node_tags):
            continue
        result.append(node)
    return result


def _exact_candidates(nodes: list[dict[str, Any]], query: str) -> list[ChannelCandidate]:
    normalized_query = _normalize(query)
    terms = _terms(query)
    candidates: list[tuple[float, dict[str, Any], tuple[str, ...]]] = []
    for node in nodes:
        score = 0.0
        matched: list[str] = []
        if normalized_query and normalized_query == _normalize(node["node_id"]):
            score += 5.0
            matched.append("node_id")
        if normalized_query and normalized_query == _normalize(node["title"]):
            score += 4.0
            matched.append("title_exact")
        elif normalized_query and normalized_query in _normalize(node["title"]):
            score += 2.5
            matched.append("title_phrase")
        node_tags = {_normalize(str(tag)) for tag in node.get("tags", [])}
        for term in terms:
            if term in node_tags:
                score += 1.5
                matched.append(f"tag:{term}")
            if term and term in _normalize(node["node_id"]):
                score += 1.0
                matched.append(f"node_id_term:{term}")
        if score > 0:
            candidates.append((score, node, tuple(matched)))
    return [
        ChannelCandidate(
            node=node, channel="exact", rank=index + 1, raw_score=score, matched=matched
        )
        for index, (score, node, matched) in enumerate(
            sorted(candidates, key=lambda item: (-item[0], item[1]["node_id"]))
        )
    ]


def _metadata_candidates(nodes: list[dict[str, Any]], query: str) -> list[ChannelCandidate]:
    terms = _terms(query)
    candidates: list[tuple[float, dict[str, Any], tuple[str, ...]]] = []
    for node in nodes:
        score = 0.0
        matched: list[str] = []
        metadata = {
            "node_type": _normalize(node["node_type"]),
            "authority": _normalize(node["authority"]),
            "title": _normalize(node["title"]),
            "tags": {_normalize(str(tag)) for tag in node.get("tags", [])},
        }
        for term in terms:
            if term == metadata["node_type"]:
                score += 2.0
                matched.append("node_type")
            if term == metadata["authority"]:
                score += 1.5
                matched.append("authority")
            if term in metadata["tags"]:
                score += 1.5
                matched.append(f"tag:{term}")
            if term and term in metadata["title"]:
                score += 0.8
                matched.append("title")
        if score > 0:
            candidates.append((score, node, tuple(matched)))
    return [
        ChannelCandidate(
            node=node,
            channel="metadata",
            rank=index + 1,
            raw_score=score,
            matched=matched,
        )
        for index, (score, node, matched) in enumerate(
            sorted(candidates, key=lambda item: (-item[0], item[1]["node_id"]))
        )
    ]


def _fts_candidates(
    store: SQLiteStore,
    workspace_id: str,
    query: str,
    node_by_id: dict[str, dict[str, Any]],
) -> list[ChannelCandidate]:
    hits = store.search(workspace_id=workspace_id, query=query, limit=30)
    candidates = []
    for index, hit in enumerate(hits):
        node = node_by_id.get(hit.node_id)
        if node is None:
            continue
        candidates.append(
            ChannelCandidate(
                node=node,
                channel="fts",
                rank=index + 1,
                raw_score=hit.score,
                matched=("content",),
            )
        )
    return candidates


def _vector_candidates(
    *,
    store: SQLiteStore,
    workspace_id: str,
    query: str,
    node_by_id: dict[str, dict[str, Any]],
    enabled: bool,
    weight: float,
) -> tuple[list[ChannelCandidate], dict[str, Any]]:
    provider = HashEmbeddingProvider()
    if not enabled:
        return [], {
            "enabled": False,
            "provider_id": provider.provider_id,
            "source": "index_chunks",
            "reason": "Vector channel is disabled unless enable_vector=true.",
        }
    if weight <= 0:
        return [], {
            "enabled": False,
            "provider_id": provider.provider_id,
            "source": "index_chunks",
            "reason": "Selected Retrieval Profile has vector_weight=0.",
        }
    chunks = store.list_index_chunks(workspace_id=workspace_id)
    if not chunks:
        return [], {
            "enabled": True,
            "provider_id": provider.provider_id,
            "source": "index_chunks",
            "candidate_count": 0,
            "reason": "No derived index chunks are available. Process IndexJobs first.",
        }
    result = search_index_chunks(
        chunks=chunks,
        workspace_id=workspace_id,
        query=query,
        limit=30,
        node_ids=set(node_by_id),
        provider=provider,
    )
    best_by_node: dict[str, dict[str, Any]] = {}
    for hit in result["hits"]:
        node_id = str(hit["node_id"])
        existing = best_by_node.get(node_id)
        if existing is None or float(hit["score"]) > float(existing["score"]):
            best_by_node[node_id] = hit
    ranked_hits = sorted(
        best_by_node.values(),
        key=lambda hit: (-float(hit["score"]), str(hit["node_id"])),
    )
    candidates = [
        ChannelCandidate(
            node=node_by_id[str(hit["node_id"])],
            channel="vector",
            rank=index + 1,
            raw_score=float(hit["score"]),
            matched=(f"chunk:{hit['chunk_id']}",),
        )
        for index, hit in enumerate(ranked_hits)
        if str(hit["node_id"]) in node_by_id
    ]
    return candidates, {
        "enabled": True,
        "provider_id": result["provider_id"],
        "dimension": result["dimension"],
        "source": result["source"],
        "candidate_count": len(candidates),
        "reason": "Local deterministic vector search over rebuildable index_chunks.",
    }


def _weighted_rrf(
    *,
    channels: dict[str, list[ChannelCandidate]],
    profile: RetrievalProfile,
) -> list[FusedCandidate]:
    weights = {
        "exact": profile.exact_weight,
        "metadata": profile.metadata_weight,
        "fts": profile.fts_weight,
        "vector": profile.vector_weight,
    }
    fused_by_id: dict[str, FusedCandidate] = {}
    for channel, candidates in channels.items():
        weight = weights[channel]
        if weight <= 0:
            continue
        for candidate in candidates:
            node_id = candidate.node["node_id"]
            fused = fused_by_id.setdefault(node_id, FusedCandidate(node=candidate.node))
            contribution = weight / (profile.rrf_k + candidate.rank)
            fused.rrf_score += contribution
            fused.channel_contributions[channel] = {
                "rank": candidate.rank,
                "weight": weight,
                "contribution": contribution,
                "raw_score": candidate.raw_score,
                "matched": list(candidate.matched),
            }
    for fused in fused_by_id.values():
        fused.final_score = fused.rrf_score
    return sorted(fused_by_id.values(), key=lambda item: (-item.final_score, item.node["node_id"]))


def _rerank_and_filter(
    candidates: list[FusedCandidate],
    profile: RetrievalProfile,
) -> tuple[list[FusedCandidate], list[dict[str, Any]], list[str]]:
    included: list[FusedCandidate] = []
    filtered: list[dict[str, Any]] = []
    warnings: list[str] = []
    for candidate in candidates:
        node = candidate.node
        status = node.get("status", "active")
        if status == "archived":
            candidate.exclude_reason = "archived nodes are excluded from formal retrieval"
        elif status == "deprecated" and not profile.include_deprecated:
            candidate.exclude_reason = "deprecated nodes are warning-only by default"
            warnings.append(f"{node['node_id']} is deprecated and was excluded.")
        elif status == "superseded":
            candidate.exclude_reason = "superseded nodes are warning-only by default"
            warnings.append(f"{node['node_id']} is superseded and was excluded.")
        if candidate.exclude_reason is not None:
            filtered.append(
                {
                    "node_id": node["node_id"],
                    "title": node["title"],
                    "reason": candidate.exclude_reason,
                    "status": status,
                }
            )
            continue
        exact = candidate.channel_contributions.get("exact", {})
        exact_bonus = 0.04 if exact else 0.0
        if "node_id" in exact.get("matched", []) or "title_exact" in exact.get("matched", []):
            exact_bonus = 0.08
        authority_bonus = AUTHORITY_BONUS.get(str(node.get("authority", "approved")), 0.0)
        candidate.rule_score = exact_bonus + authority_bonus
        candidate.final_score = candidate.rrf_score + candidate.rule_score
        candidate.include_reason = _include_reason(candidate)
        included.append(candidate)
    return (
        sorted(included, key=lambda item: (-item.final_score, item.node["node_id"])),
        filtered,
        warnings,
    )


def _expand_relations(
    *,
    seeds: list[FusedCandidate],
    nodes: list[dict[str, Any]],
    relation_depth: int,
) -> list[FusedCandidate]:
    if relation_depth <= 0:
        return []
    node_by_id = {node["node_id"]: node for node in nodes}
    seed_ids = {candidate.node["node_id"] for candidate in seeds}
    expanded: dict[str, FusedCandidate] = {}
    for seed in seeds:
        for relation in _relation_edges(seed.node, nodes):
            relation_type = str(relation.get("type", ""))
            target_id = str(relation.get("target", ""))
            if relation_type in NON_EXPANDING_RELATION_TYPES:
                continue
            if relation_type not in RELATION_TYPE_WEIGHTS:
                continue
            if target_id in seed_ids or target_id in expanded:
                continue
            target = node_by_id.get(target_id)
            if target is None or target.get("status", "active") in {"archived", "deprecated"}:
                continue
            score = seed.final_score * RELATION_TYPE_WEIGHTS[relation_type] * 0.65
            expanded[target_id] = FusedCandidate(
                node=target,
                rrf_score=0.0,
                rule_score=score,
                final_score=score,
                include_reason=f"expanded via {relation_type} from {seed.node['node_id']}",
                expanded_from=seed.node["node_id"],
                relation_type=relation_type,
            )
    return sorted(expanded.values(), key=lambda item: (-item.final_score, item.node["node_id"]))


def _merge_expanded(
    ranked: list[FusedCandidate],
    expanded: list[FusedCandidate],
    result_limit: int,
) -> list[FusedCandidate]:
    merged: dict[str, FusedCandidate] = {}
    for candidate in ranked + expanded:
        merged.setdefault(candidate.node["node_id"], candidate)
    return sorted(merged.values(), key=lambda item: (-item.final_score, item.node["node_id"]))[
        :result_limit
    ]


def _context_bundle_payload(
    *,
    candidates: list[FusedCandidate],
    profile: RetrievalProfile,
    warnings: list[str],
) -> dict[str, list[Any]]:
    mandatory: list[dict[str, Any]] = []
    relevant: list[dict[str, Any]] = []
    supporting: list[dict[str, Any]] = []
    for candidate in candidates:
        item = _bundle_item(candidate, profile)
        if _is_mandatory(candidate.node):
            if len(mandatory) < profile.mandatory_limit:
                mandatory.append(item)
        elif len(relevant) < profile.relevant_limit:
            relevant.append(item)
        for ref in candidate.node.get("source_refs", []):
            if len(supporting) < profile.supporting_limit:
                supporting.append(
                    {
                        **ref,
                        "node_id": candidate.node["node_id"],
                        "revision": candidate.node["revision"],
                    }
                )
    if not candidates:
        warnings.append("No approved MemoryNode matched the question.")
    return {
        "mandatory_constraints": mandatory,
        "relevant_context": relevant,
        "supporting_references": supporting,
        "warnings": warnings,
    }


def _bundle_item(candidate: FusedCandidate, profile: RetrievalProfile) -> dict[str, Any]:
    node = candidate.node
    source_channels = sorted(candidate.channel_contributions)
    if not source_channels and candidate.expanded_from:
        source_channels = ["relation_expansion"]
    return {
        "node_id": node["node_id"],
        "title": node["title"],
        "node_type": node["node_type"],
        "authority": node["authority"],
        "status": node.get("status", "active"),
        "revision": node["revision"],
        "score": round(candidate.final_score, 6),
        "source_channels": source_channels,
        "profile_id": profile.profile_id,
        "include_reason": candidate.include_reason,
        "content": node["content"],
        "source_refs": node.get("source_refs", []),
    }


def _candidate_trace(candidate: ChannelCandidate) -> dict[str, Any]:
    return {
        "node_id": candidate.node["node_id"],
        "title": candidate.node["title"],
        "channel": candidate.channel,
        "rank": candidate.rank,
        "raw_score": candidate.raw_score,
        "matched": list(candidate.matched),
    }


def _fused_trace(candidate: FusedCandidate) -> dict[str, Any]:
    return {
        "node_id": candidate.node["node_id"],
        "title": candidate.node["title"],
        "score": round(candidate.final_score, 6),
        "rrf_score": round(candidate.rrf_score, 6),
        "rule_score": round(candidate.rule_score, 6),
        "channels": candidate.channel_contributions,
        "include_reason": candidate.include_reason,
        "expanded_from": candidate.expanded_from,
        "relation_type": candidate.relation_type,
    }


def _include_reason(candidate: FusedCandidate) -> str:
    channels = ", ".join(sorted(candidate.channel_contributions))
    if channels:
        return f"ranked by {channels}"
    return candidate.include_reason


def _relation_edges(node: dict[str, Any], nodes: list[dict[str, Any]]) -> list[dict[str, str]]:
    outgoing = [
        {"target": str(relation.get("target")), "type": str(relation.get("type"))}
        for relation in node.get("relations", [])
        if relation.get("target") and relation.get("type")
    ]
    incoming = []
    node_id = node["node_id"]
    for candidate in nodes:
        for relation in candidate.get("relations", []):
            if relation.get("target") == node_id and relation.get("type") in RELATION_TYPE_WEIGHTS:
                incoming.append(
                    {
                        "target": candidate["node_id"],
                        "type": str(relation.get("type")),
                    }
                )
    return outgoing + incoming


def _apply_conflict_strategy(
    candidates: list[FusedCandidate],
    node_by_id: dict[str, dict[str, Any]],
    profile: RetrievalProfile,
) -> tuple[list[FusedCandidate], list[dict[str, Any]], list[str]]:
    candidate_ids = {candidate.node["node_id"] for candidate in candidates}
    candidate_by_id = {candidate.node["node_id"]: candidate for candidate in candidates}
    blocked_ids: set[str] = set()
    filtered: list[dict[str, Any]] = []
    warnings: list[str] = []
    for candidate in candidates:
        for relation in candidate.node.get("relations", []):
            relation_type = relation.get("type")
            target_id = relation.get("target")
            if relation_type == "conflicts_with" and target_id in node_by_id:
                scope = "selected bundle" if target_id in candidate_ids else "approved node"
                warnings.append(f"{candidate.node['node_id']} conflicts with {scope} {target_id}.")
                if profile.conflict_strategy == "block" and target_id in candidate_by_id:
                    blocked = _lower_ranked_conflict(candidate, candidate_by_id[target_id])
                    if blocked.node["node_id"] not in blocked_ids:
                        blocked_ids.add(blocked.node["node_id"])
                        filtered.append(
                            {
                                "node_id": blocked.node["node_id"],
                                "title": blocked.node["title"],
                                "reason": "blocked by conflict_strategy=block",
                                "status": blocked.node.get("status", "active"),
                                "conflict_strategy": profile.conflict_strategy,
                            }
                        )
            if relation_type == "supersedes" and target_id in node_by_id:
                warnings.append(f"{candidate.node['node_id']} supersedes {target_id}.")
    if not blocked_ids:
        return candidates, filtered, warnings
    return (
        [candidate for candidate in candidates if candidate.node["node_id"] not in blocked_ids],
        filtered,
        warnings,
    )


def _lower_ranked_conflict(left: FusedCandidate, right: FusedCandidate) -> FusedCandidate:
    if left.final_score == right.final_score:
        return max((left, right), key=lambda item: item.node["node_id"])
    return left if left.final_score < right.final_score else right


def _is_mandatory(node: dict[str, Any]) -> bool:
    return (
        node["authority"] == "canonical"
        or node["node_type"] == "Constraint"
        or _looks_like_constraint(node["content"])
    )


def _looks_like_constraint(content: str) -> bool:
    lowered = content.lower()
    return any(term in lowered for term in ("must", "cannot", "不得", "必须", "禁止"))


def _terms(query: str) -> list[str]:
    return [_normalize(term) for term in query.replace(",", " ").split() if term.strip()]


def _normalize(value: str) -> str:
    return value.strip().lower()
