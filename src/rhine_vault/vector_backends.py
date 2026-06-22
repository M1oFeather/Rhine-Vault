"""Read-only vector backend capability reporting."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Any


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
    """Return the current vector backend matrix without activating optional backends."""

    chroma_installed = _module_available("chromadb")
    chroma_status = "available_not_enabled" if chroma_installed else "missing_optional_dependency"
    return {
        "phase": "Phase 6 - Chroma adapter evaluation",
        "active_backend": "local-hash",
        "default_backend": "local-hash",
        "constraints": [
            "Vector indexes are derived data and never formal knowledge authority.",
            "Production vector retrieval remains disabled in this slice.",
            "Embedding provider network calls remain disabled in this slice.",
            "ChromaDB is evaluated as an optional future backend, not activated here.",
        ],
        "backends": [
            VectorBackendCapability(
                backend_id="local-hash",
                display_name="Local Hash Embedding + InMemoryVectorIndex",
                status="enabled",
                installed=True,
                enabled=True,
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
                enabled=False,
                default=False,
                production_ready=False,
                formal_authority=False,
                notes=(
                    "Optional candidate for a future Phase 6 continuation.",
                    "No collection is created and no data is written by this probe.",
                ),
            ).to_dict(),
        ],
    }


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None
