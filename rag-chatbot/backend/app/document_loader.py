from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Chunk:
    document_id: str
    chunk_id: str
    chunk_index: int
    text: str


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(text: str, *, chunk_words: int = 220, overlap_words: int = 45) -> list[str]:
    words = normalize_text(text).split()
    if not words:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(len(words), start + chunk_words)
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = max(0, end - overlap_words)
    return chunks


def build_chunks(document_id: str, text: str) -> list[Chunk]:
    return [
        Chunk(
            document_id=document_id,
            chunk_id=f"{document_id}:{index:04d}",
            chunk_index=index,
            text=chunk,
        )
        for index, chunk in enumerate(chunk_text(text), start=1)
    ]


async def read_upload(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md", ".markdown"}:
        return content.decode("utf-8", errors="ignore")

    if suffix == ".pdf":
        from io import BytesIO
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    if suffix == ".docx":
        from io import BytesIO
        from docx import Document

        document = Document(BytesIO(content))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)

    raise ValueError(f"Unsupported file type: {suffix or 'unknown'}")
