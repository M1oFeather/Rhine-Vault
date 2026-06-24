"""Read-only vector backend capability reporting."""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from typing import Any

from rhine_vault.vector import OpenAICompatibleEmbeddingProvider


@dataclass(frozen=True)
class VectorBackendCapability:
    backend_id: str
    display_name: str
    status: str
    installed: bool
    enabled: bool
    default: bool
    production_ready: bool
    formal_authority: bool
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "display_name": self.display_name,
            "status": self.status,
            "installed": self.installed,
            "enabled": self.enabled,
            "default": self.default,
            "production_ready": self.production_ready,
            "formal_authority": self.formal_authority,
            "notes": list(self.notes),
        }


def vector_backend_capabilities() -> dict[str, Any]:
    """Return the current vector backend matrix without writing derived vector data."""

    active_backend = os.getenv("RHINE_VAULT_VECTOR_BACKEND", "local-hash").strip() or "local-hash"
    chroma_installed = _module_available("chromadb")
    chroma_selected = active_backend == "chroma"
    chroma_status = _backend_status(
        installed=chroma_installed,
        selected=chroma_selected,
    )
    embedding_status = OpenAICompatibleEmbeddingProvider.environment_status()
    return {
        "phase": "Full Implementation - Vector Backends",
        "active_backend": active_backend,
        "default_backend": "local-hash",
        "constraints": [
            "Vector indexes are derived data and never formal knowledge authority.",
            "Network embeddings run only when an embedding provider is explicitly configured.",
            "ChromaDB is optional and must be selected through RHINE_VAULT_VECTOR_BACKEND=chroma.",
            "Formal MemoryNode approval remains the authority boundary.",
        ],
        "embedding_provider": embedding_status,
        "backends": [
            VectorBackendCapability(
                backend_id="local-hash",
                display_name="Local Hash Embedding + InMemoryVectorIndex",
                status="enabled" if active_backend == "local-hash" else "available",
                installed=True,
                enabled=active_backend == "local-hash",
                default=True,
                production_ready=False,
                formal_authority=False,
                notes=(
                    "Deterministic offline adapter for plumbing, tests and explain traces.",
                    "Reads rebuildable index_chunks only.",
                ),
            ).to_dict(),
            VectorBackendCapability(
                backend_id="chroma",
                display_name="ChromaDB",
                status=chroma_status,
                installed=chroma_installed,
                enabled=chroma_selected and chroma_installed,
                default=False,
                production_ready=chroma_selected and chroma_installed,
                formal_authority=False,
                notes=(
                    "Optional production vector backend for derived indexes.",
                    "The capability probe does not create collections by itself.",
                ),
            ).to_dict(),
        ],
    }


def _backend_status(*, installed: bool, selected: bool) -> str:
    if selected and installed:
        return "enabled"
    if selected and not installed:
        return "selected_missing_optional_dependency"
    if installed:
        return "available"
    return "missing_optional_dependency"


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None
