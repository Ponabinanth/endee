from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class Document:
    document_id: str
    filename: str
    title: str
    source: str
    text: str
    created_at: float


@dataclass
class VectorChunk:
    chunk_id: str
    document_id: str
    chunk_index: int
    text: str
    vector: list[float]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    limit = min(len(left), len(right))
    dot = sum(left[i] * right[i] for i in range(limit))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


class LocalVectorStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.documents: dict[str, Document] = {}
        self.chunks: dict[str, VectorChunk] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.documents = {
            item["document_id"]: Document(**item)
            for item in payload.get("documents", [])
        }
        self.chunks = {
            item["chunk_id"]: VectorChunk(**item)
            for item in payload.get("chunks", [])
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "documents": [asdict(document) for document in self.documents.values()],
            "chunks": [asdict(chunk) for chunk in self.chunks.values()],
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def add_document(
        self,
        *,
        filename: str,
        title: str,
        source: str,
        text: str,
        chunks: list[tuple[int, str, list[float]]],
    ) -> Document:
        document_id = f"doc_{uuid.uuid4().hex[:12]}"
        document = Document(
            document_id=document_id,
            filename=filename,
            title=title,
            source=source,
            text=text,
            created_at=time.time(),
        )
        self.documents[document_id] = document
        for chunk_index, chunk_text, vector in chunks:
            chunk_id = f"{document_id}:{chunk_index:04d}"
            self.chunks[chunk_id] = VectorChunk(
                chunk_id=chunk_id,
                document_id=document_id,
                chunk_index=chunk_index,
                text=chunk_text,
                vector=vector,
            )
        self.save()
        return document

    def delete_document(self, document_id: str) -> bool:
        if document_id not in self.documents:
            return False
        self.documents.pop(document_id)
        for chunk_id in [chunk_id for chunk_id, chunk in self.chunks.items() if chunk.document_id == document_id]:
            self.chunks.pop(chunk_id)
        self.save()
        return True

    def search(self, query_vector: list[float], top_k: int) -> list[dict[str, Any]]:
        scored = [
            (cosine_similarity(query_vector, chunk.vector), chunk)
            for chunk in self.chunks.values()
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        results: list[dict[str, Any]] = []
        for score, chunk in scored[:top_k]:
            document = self.documents.get(chunk.document_id)
            if not document:
                continue
            results.append({"score": score, "chunk": chunk, "document": document})
        return results
