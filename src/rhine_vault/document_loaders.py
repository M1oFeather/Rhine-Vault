"""Optional document text loaders used before capture proposals are created."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TEXT_SUFFIXES = frozenset({".md", ".txt"})
PDF_SUFFIX = ".pdf"
DOCX_SUFFIX = ".docx"
SUPPORTED_DOCUMENT_SUFFIXES = TEXT_SUFFIXES | frozenset({PDF_SUFFIX, DOCX_SUFFIX})


class UnsupportedDocumentTypeError(ValueError):
    """Raised when a document suffix has no loader."""


class OptionalDocumentDependencyError(RuntimeError):
    """Raised when an optional loader dependency is missing."""


@dataclass(frozen=True)
class LoadedDocument:
    text: str
    source_format: str
    metadata: dict[str, Any]


def load_document_text(path: Path) -> LoadedDocument:
    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        text = path.read_text(encoding="utf-8")
        return LoadedDocument(
            text=text,
            source_format=suffix.removeprefix(".") or "text",
            metadata={"loader": "text", "line_count": max(1, len(text.splitlines()))},
        )
    if suffix == PDF_SUFFIX:
        return _load_pdf(path)
    if suffix == DOCX_SUFFIX:
        return _load_docx(path)
    raise UnsupportedDocumentTypeError(
        f"unsupported document type: {suffix or '<no suffix>'}; supported: .md, .txt, .pdf, .docx"
    )


def document_loader_capabilities() -> dict[str, Any]:
    return {
        "supported_suffixes": sorted(SUPPORTED_DOCUMENT_SUFFIXES),
        "loaders": [
            {
                "loader_id": "markdown-text",
                "suffixes": sorted(TEXT_SUFFIXES),
                "available": True,
                "optional_dependency": None,
            },
            {
                "loader_id": "pdf-pypdf",
                "suffixes": [PDF_SUFFIX],
                "available": _can_import("pypdf"),
                "optional_dependency": "pypdf",
            },
            {
                "loader_id": "docx-python-docx",
                "suffixes": [DOCX_SUFFIX],
                "available": _can_import("docx"),
                "optional_dependency": "python-docx",
            },
        ],
        "authority": "loaded text becomes Capture Proposal source material only",
    }


def _load_pdf(path: Path) -> LoadedDocument:
    try:
        pypdf = importlib.import_module("pypdf")
    except ImportError as exc:
        raise OptionalDocumentDependencyError(
            "PDF import requires optional dependency: pip install 'rhine-vault[documents]'"
        ) from exc
    reader = pypdf.PdfReader(str(path))
    page_texts: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        extracted = str(page.extract_text() or "").strip()
        if extracted:
            page_texts.append(f"# Page {index}\n\n{extracted}")
    text = "\n\n".join(page_texts).strip()
    return LoadedDocument(
        text=text,
        source_format="pdf",
        metadata={"loader": "pypdf", "page_count": len(reader.pages)},
    )


def _load_docx(path: Path) -> LoadedDocument:
    try:
        docx = importlib.import_module("docx")
    except ImportError as exc:
        raise OptionalDocumentDependencyError(
            "DOCX import requires optional dependency: pip install 'rhine-vault[documents]'"
        ) from exc
    document = docx.Document(str(path))
    lines = [str(paragraph.text).strip() for paragraph in document.paragraphs]
    text = "\n\n".join(line for line in lines if line)
    return LoadedDocument(
        text=text,
        source_format="docx",
        metadata={"loader": "python-docx", "paragraph_count": len(document.paragraphs)},
    )


def _can_import(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
    except ImportError:
        return False
    return True
