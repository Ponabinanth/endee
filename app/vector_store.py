from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Iterable

logger = logging.getLogger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    limit = min(len(a), len(b))
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for i in range(limit):
        av = float(a[i])
        bv = float(b[i])
        dot += av * bv
        norm_a += av * av
        norm_b += bv * bv
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return dot / math.sqrt(norm_a * norm_b)


def _matches_filter(record_filter: dict[str, Any], clauses: Any) -> bool:
    """
    Endee-style filter clauses:
      [{"department": {"$eq": "engineering"}}, {"doc_type": {"$eq": "candidate_resume"}}]
    Treated as AND across clauses.
    """
    if not clauses:
        return True
    if not isinstance(clauses, list):
        return True
    for clause in clauses:
        if not isinstance(clause, dict) or not clause:
            continue
        field, condition = next(iter(clause.items()))
        if not isinstance(condition, dict):
            return False
        if "$eq" in condition:
            if record_filter.get(field) != condition["$eq"]:
                return False
    return True


class VectorIndex:
    def upsert(self, records: list[dict[str, Any]]) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def query(self, **kwargs: Any) -> list[dict[str, Any]]:  # pragma: no cover - interface
        raise NotImplementedError


class VectorStore:
    backend: str = "unknown"

    def create_index(self, **kwargs: Any) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def get_index(self, *, name: str) -> VectorIndex:  # pragma: no cover - interface
        raise NotImplementedError


class EndeeVectorStore(VectorStore):
    backend = "endee"

    def __init__(self, *, base_url: str, auth_token: str = "") -> None:
        from endee import Endee

        self._client = Endee(auth_token) if auth_token else Endee()
        self._client.set_base_url(base_url)

    def create_index(self, **kwargs: Any) -> None:
        self._client.create_index(**kwargs)

    def get_index(self, *, name: str) -> VectorIndex:
        return self._client.get_index(name=name)


@dataclass
class _InMemoryRecord:
    id: str
    vector: list[float]
    meta: dict[str, Any]
    filter: dict[str, Any]


class InMemoryVectorIndex(VectorIndex):
    def __init__(self, *, name: str, dimension: int) -> None:
        self.name = name
        self.dimension = dimension
        self._records: dict[str, _InMemoryRecord] = {}

    def upsert(self, records: list[dict[str, Any]]) -> None:
        for record in records:
            record_id = str(record.get("id") or "")
            vector = list(record.get("vector") or [])
            meta = dict(record.get("meta") or record.get("metadata") or {})
            filt = dict(record.get("filter") or {})
            if not record_id:
                continue
            self._records[record_id] = _InMemoryRecord(id=record_id, vector=vector, meta=meta, filter=filt)

    def query(self, **kwargs: Any) -> list[dict[str, Any]]:
        vector = list(kwargs.get("vector") or [])
        top_k = int(kwargs.get("top_k") or 5)
        clauses = kwargs.get("filter")

        scored: list[tuple[float, _InMemoryRecord]] = []
        for record in self._records.values():
            if not _matches_filter(record.filter, clauses):
                continue
            score = _cosine_similarity(vector, record.vector)
            scored.append((score, record))

        scored.sort(key=lambda item: item[0], reverse=True)
        results: list[dict[str, Any]] = []
        for score, record in scored[:top_k]:
            results.append(
                {
                    "id": record.id,
                    "similarity": float(score),
                    "meta": record.meta,
                }
            )
        return results


class InMemoryVectorStore(VectorStore):
    backend = "memory"

    def __init__(self) -> None:
        self._indexes: dict[str, InMemoryVectorIndex] = {}

    def create_index(self, **kwargs: Any) -> None:
        name = str(kwargs.get("name") or "")
        dimension = int(kwargs.get("dimension") or 384)
        if not name:
            raise ValueError("Index name is required")
        self._indexes.setdefault(name, InMemoryVectorIndex(name=name, dimension=dimension))

    def get_index(self, *, name: str) -> VectorIndex:
        if name not in self._indexes:
            self._indexes[name] = InMemoryVectorIndex(name=name, dimension=384)
        return self._indexes[name]


def select_vector_store(
    *,
    backend: str,
    endee_base_url: str,
    endee_auth_token: str,
) -> VectorStore:
    """
    backend:
      - "endee": always attempt Endee, but caller can still fall back on errors
      - "memory": always local in-memory
      - "auto": prefer Endee, fallback to memory if Endee import/connection fails
    """
    normalized = (backend or "auto").strip().lower()
    if normalized == "memory":
        return InMemoryVectorStore()

    if normalized in {"auto", "endee"}:
        try:
            return EndeeVectorStore(base_url=endee_base_url, auth_token=endee_auth_token)
        except Exception as exc:
            if normalized == "endee":
                raise
            logger.warning("Endee client unavailable, using in-memory vector store: %s", exc)
            return InMemoryVectorStore()

    logger.warning("Unknown VECTOR_STORE_BACKEND=%r, using in-memory vector store", backend)
    return InMemoryVectorStore()


def batched(items: Iterable[dict[str, Any]], batch_size: int) -> Iterable[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    for item in items:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch

