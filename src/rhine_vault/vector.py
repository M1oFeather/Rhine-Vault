"""Local vector adapter primitives for rebuildable derived indexes."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse, urlunparse

TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
DEFAULT_EMBEDDINGS_BASE_URL = "https://api.openai.com/v1"
DEFAULT_EMBEDDINGS_MODEL = "text-embedding-3-small"


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


@dataclass(frozen=True)
class OpenAICompatibleEmbeddingProvider:
    """OpenAI-compatible embeddings provider, activated only by explicit config."""

    base_url: str
    api_key: str
    model: str = DEFAULT_EMBEDDINGS_MODEL
    dimension: int = 1536
    timeout_seconds: float = 30.0

    @property
    def provider_id(self) -> str:
        return f"openai-compatible:{self.model}"

    @classmethod
    def from_env(cls) -> OpenAICompatibleEmbeddingProvider:
        base_url = (
            os.getenv("RHINE_EMBEDDINGS_BASE_URL")
            or os.getenv("RHINE_OPENAI_EMBEDDINGS_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or DEFAULT_EMBEDDINGS_BASE_URL
        )
        api_key = (
            os.getenv("RHINE_EMBEDDINGS_API_KEY")
            or os.getenv("RHINE_OPENAI_EMBEDDINGS_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or ""
        )
        model = (
            os.getenv("RHINE_EMBEDDINGS_MODEL")
            or os.getenv("RHINE_OPENAI_EMBEDDINGS_MODEL")
            or DEFAULT_EMBEDDINGS_MODEL
        )
        dimension = int(os.getenv("RHINE_EMBEDDINGS_DIMENSION") or "1536")
        if not api_key.strip():
            raise RuntimeError("OpenAI-compatible embeddings provider is not configured")
        return cls(
            base_url=base_url.strip(),
            api_key=api_key.strip(),
            model=model.strip(),
            dimension=dimension,
        )

    @classmethod
    def environment_status(cls) -> dict[str, Any]:
        return {
            "provider": "openai-compatible-embeddings",
            "configured": bool(
                os.getenv("RHINE_EMBEDDINGS_API_KEY")
                or os.getenv("RHINE_OPENAI_EMBEDDINGS_API_KEY")
                or os.getenv("OPENAI_API_KEY")
            ),
            "base_url": _redact_url(
                os.getenv("RHINE_EMBEDDINGS_BASE_URL")
                or os.getenv("RHINE_OPENAI_EMBEDDINGS_BASE_URL")
                or os.getenv("OPENAI_BASE_URL")
                or DEFAULT_EMBEDDINGS_BASE_URL
            ),
            "model": (
                os.getenv("RHINE_EMBEDDINGS_MODEL")
                or os.getenv("RHINE_OPENAI_EMBEDDINGS_MODEL")
                or DEFAULT_EMBEDDINGS_MODEL
            ),
        }

    @property
    def embeddings_url(self) -> str:
        return _embeddings_url(self.base_url)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload: dict[str, Any] = {"model": self.model, "input": texts}
        request = urllib.request.Request(
            self.embeddings_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        vectors = _extract_embeddings_response(data)
        if vectors:
            object.__setattr__(self, "dimension", len(vectors[0]))
        return vectors


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


def _extract_embeddings_response(data: dict[str, Any]) -> list[list[float]]:
    items = data.get("data")
    if not isinstance(items, list):
        raise RuntimeError("OpenAI-compatible embeddings response did not include data")
    ordered = sorted(
        (item for item in items if isinstance(item, dict)),
        key=lambda item: int(item.get("index", 0)),
    )
    vectors: list[list[float]] = []
    for item in ordered:
        embedding = item.get("embedding")
        if not isinstance(embedding, list) or not all(
            isinstance(value, int | float) for value in embedding
        ):
            raise RuntimeError("OpenAI-compatible embedding item is invalid")
        vectors.append([float(value) for value in embedding])
    return vectors


def _embeddings_url(base_url: str) -> str:
    cleaned = base_url.strip().rstrip("/") or DEFAULT_EMBEDDINGS_BASE_URL
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError("OpenAI-compatible embeddings base URL must be an http(s) URL")
    if parsed.username or parsed.password:
        raise RuntimeError("OpenAI-compatible embeddings base URL must not include credentials")
    if cleaned.endswith("/embeddings"):
        return cleaned
    if cleaned.endswith("/v1"):
        return f"{cleaned}/embeddings"
    if not parsed.path or parsed.path == "/":
        return f"{cleaned}/v1/embeddings"
    return f"{cleaned}/embeddings"


def _redact_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if not parsed.username and not parsed.password:
        return base_url
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return urlunparse(
        (
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )
