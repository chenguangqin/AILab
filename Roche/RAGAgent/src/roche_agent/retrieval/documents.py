from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from roche_agent.contracts import Chunk, IndexConfig


@dataclass(frozen=True)
class SourceDocument:
    document_id: str
    text: str
    metadata: dict[str, Any]
    path: Path


def load_markdown_documents(directory: str | Path) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    for path in sorted(Path(directory).glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        metadata: dict[str, Any] = {}
        text = raw
        if raw.startswith("---\n"):
            _, frontmatter, text = raw.split("---\n", 2)
            metadata = yaml.safe_load(frontmatter) or {}
        document_id = metadata.get("document_id", path.stem)
        documents.append(
            SourceDocument(
                document_id=document_id,
                text=text.strip(),
                metadata=metadata,
                path=path,
            )
        )
    return documents


def _base_metadata(document: SourceDocument) -> dict[str, Any]:
    return {
        **document.metadata,
        "source_path": str(document.path),
    }


def fixed_chunks(document: SourceDocument, config: IndexConfig) -> list[Chunk]:
    text = document.text
    step = config.chunk_size - config.chunk_overlap
    chunks: list[Chunk] = []
    for index, start in enumerate(range(0, len(text), step)):
        piece = text[start : start + config.chunk_size].strip()
        if not piece:
            continue
        contained_evidence_ids = [
            item
            for item in re.findall(r"^#{1,6}\s+\[([^\]]+)\]", piece, flags=re.MULTILINE)
        ]
        chunks.append(
            Chunk(
                chunk_id=f"{document.document_id}::fixed::{index:03d}",
                document_id=document.document_id,
                text=piece,
                chunk_type="fixed",
                metadata={
                    **_base_metadata(document),
                    "char_start": start,
                    "contained_evidence_ids": contained_evidence_ids,
                },
            )
        )
        if start + config.chunk_size >= len(text):
            break
    return chunks


HEADING_RE = re.compile(r"^#{1,6}\s+(?:\[([^\]]+)\]\s*)?(.*)$")


def structure_chunks(document: SourceDocument) -> list[Chunk]:
    chunks: list[Chunk] = []
    current_id: str | None = None
    current_title = ""
    buffer: list[str] = []
    block_index = 0

    def flush() -> None:
        nonlocal block_index, buffer
        text = "\n".join(buffer).strip()
        if not text:
            buffer = []
            return
        evidence_id = current_id or f"{document.document_id}::section::{block_index:03d}"
        chunks.append(
            Chunk(
                chunk_id=evidence_id,
                document_id=document.document_id,
                text=f"{current_title}\n{text}".strip(),
                chunk_type="clause" if current_id else "section",
                metadata={
                    **_base_metadata(document),
                    "section_title": current_title,
                    "evidence_id": evidence_id,
                },
            )
        )
        block_index += 1
        buffer = []

    for line in document.text.splitlines():
        match = HEADING_RE.match(line.strip())
        if match:
            flush()
            current_id, current_title = match.groups()
            continue
        if line.lstrip().startswith("|") and line.count("|") >= 2:
            if set(line.replace("|", "").replace("-", "").replace(":", "").strip()) == set():
                continue
            flush()
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            row_key = cells[0] if cells else str(block_index)
            evidence_id = current_id or f"{document.document_id}::table::{row_key}"
            chunks.append(
                Chunk(
                    chunk_id=evidence_id,
                    document_id=document.document_id,
                    text=f"{current_title}\n" + " | ".join(cells),
                    chunk_type="table_row",
                    metadata={
                        **_base_metadata(document),
                        "section_title": current_title,
                        "evidence_id": evidence_id,
                        "table_row_key": row_key,
                        "table_cells": cells,
                    },
                )
            )
            current_id = None
            block_index += 1
            continue
        if line.strip():
            buffer.append(line.strip())
        elif buffer:
            flush()
    flush()
    return chunks


def chunk_documents(documents: list[SourceDocument], config: IndexConfig) -> list[Chunk]:
    chunks: list[Chunk] = []
    for document in documents:
        if config.chunk_strategy == "structure":
            chunks.extend(structure_chunks(document))
        else:
            chunks.extend(fixed_chunks(document, config))
    return chunks
