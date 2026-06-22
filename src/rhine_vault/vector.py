"""Local vector adapter primitives for rebuildable derived indexes."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any, Protocol

TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


class EmbeddingProvider(Protocol):
    provider_id: str
    dimension: int

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts into deterministic vectors."""


@dataclass(frozen=True)
class VectorHit:
    chunk_id: str
    workspace_id: str
    node_id: str
    revision: int
    score: float
    content: str
    heading_path: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "workspace_id": self.workspace_id,
            "node_id": self.node_id,
            "revision": self.revision,
            "score": round(self.score, 6),
            "content": self.content,
            "heading_path": list(self.heading_path),
        }


class HashEmbeddingProvider:
    """Deterministic local embedding for tests and offline vector plumbing."""

    provider_id = "hash-local-v1"

    def __init__(self, *, dimension: int = 64) -> None:
        if dimension < 8:
            raise ValueError("dimension must be >= 8")
        self.dimension = dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def _embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in _tokens(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        return _normalize_vector(vector)


class InMemoryVectorIndex:
    """Search derived index chunks without making vectors formal state."""

    def __init__(
        self,
        *,
        provider: EmbeddingProvider,
        rows: list[dict[str, Any]],
        vectors: list[list[float]],
    ) -> None:
        self.provider = provider
        self.rows = rows
        self.vectors = vectors

    @classmethod
    def from_chunks(
        cls,
        chunks: list[dict[str, Any]],
        *,
        provider: EmbeddingProvider | None = None,
    ) -> InMemoryVectorIndex:
        active_provider = provider or HashEmbeddingProvider()
        texts = [str(chunk.get("content", "")) for chunk in chunks]
        return cls(
            provider=active_provider,
            rows=chunks,
            vectors=active_provider.embed_texts(texts),
        )

    def search(
        self,
        *,
        query: str,
        workspace_id: str,
        limit: int = 10,
        node_ids: set[str] | None = None,
    ) -> list[VectorHit]:
        query_vector = self.provider.embed_texts([query])[0]
        if not any(query_vector):
            return []
        hits: list[VectorHit] = []
        for row, vector in zip(self.rows, self.vectors, strict=True):
            if row["workspace_id"] != workspace_id:
                continue
            if node_ids is not None and row["node_id"] not in node_ids:
                continue
            score = _cosine_similarity(query_vector, vector)
            if score <= 0:
                continue
            hits.append(
                VectorHit(
                    chunk_id=str(row["chunk_id"]),
                    workspace_id=str(row["workspace_id"]),
                    node_id=str(row["node_id"]),
                    revision=int(row["revision"]),
                    score=score,
                    content=str(row["content"]),
                    heading_path=tuple(row.get("heading_path", ())),
                )
            )
        return sorted(hits, key=lambda hit: (-hit.score, hit.node_id, hit.chunk_id))[:limit]


def search_index_chunks(
    *,
    chunks: list[dict[str, Any]],
    workspace_id: str,
    query: str,
    limit: int = 10,
    node_ids: set[str] | None = None,
    provider: EmbeddingProvider | None = None,
) -> dict[str, Any]:
    active_index = InMemoryVectorIndex.from_chunks(chunks, provider=provider)
    hits = active_index.search(
        query=query,
        workspace_id=workspace_id,
        limit=limit,
        node_ids=node_ids,
    )
    return {
        "provider_id": active_index.provider.provider_id,
        "dimension": active_index.provider.dimension,
        "source": "index_chunks",
        "hits": [hit.to_dict() for hit in hits],
    }


def _tokens(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(text)]


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    return sum(
        left_value * right_value for left_value, right_value in zip(left, right, strict=True)
    )
