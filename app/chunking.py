from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkRecord:
    id: str
    text: str
    chunk_index: int
    title: str
    source: str
    department: str
    doc_type: str
    audience: str


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(text: str, max_words: int = 180, overlap_words: int = 30) -> list[str]:
    words = normalize_text(text).split()
    if not words:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(len(words), start + max_words)
        chunk = " ".join(words[start:end]).strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(words):
            break
        start = max(0, end - overlap_words)
        if start == end:
            start += 1
    return chunks


def build_chunk_records(
    *,
    document_id: str,
    title: str,
    source: str,
    department: str,
    doc_type: str,
    audience: str,
    body: str,
) -> list[ChunkRecord]:
    records: list[ChunkRecord] = []
    for index, text in enumerate(chunk_text(body), start=1):
        records.append(
            ChunkRecord(
                id=f"{document_id}:{index:03d}",
                text=text,
                chunk_index=index,
                title=title,
                source=source,
                department=department,
                doc_type=doc_type,
                audience=audience,
            )
        )
    return records

