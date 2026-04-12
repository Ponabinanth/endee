from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.chunking import ChunkRecord, build_chunk_records
from app.config import Settings
from app.embeddings import Embedder
from app.filters import build_endee_filter
from app.rag import extractive_answer, openai_answer, truncate
from app.sample_corpus import SAMPLE_DOCUMENTS, example_questions, filter_catalog

logger = logging.getLogger(__name__)


class KnowledgeBase:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.embedder = Embedder(settings.embedding_model)
        self._client = None
        self._index = None
        self._bootstrapped = False
        self._bootstrap_error: str | None = None
        self._seeded_chunk_count = 0
        self._last_bootstrap_at: float | None = None

    @property
    def client(self):
        if self._client is not None:
            return self._client

        from endee import Endee

        if self.settings.endee_auth_token:
            self._client = Endee(self.settings.endee_auth_token)
        else:
            self._client = Endee()
        self._client.set_base_url(self.settings.endee_base_url)
        return self._client

    @property
    def index(self):
        if self._index is None:
            self._index = self.client.get_index(name=self.settings.endee_index_name)
        return self._index

    def ensure_index(self) -> None:
        from endee import Precision

        try:
            self.client.create_index(
                name=self.settings.endee_index_name,
                dimension=384,
                space_type="cosine",
                precision=Precision.INT8,
            )
        except Exception as exc:
            message = str(exc).lower()
            if "already exists" not in message and "exists" not in message:
                raise
        self._index = self.client.get_index(name=self.settings.endee_index_name)

    def _upsert_batch(self, records: list[dict[str, Any]]) -> None:
        if records:
            self.index.upsert(records)

    def _upsert_in_batches(self, records: list[dict[str, Any]], batch_size: int = 1000) -> None:
        for start in range(0, len(records), batch_size):
            self._upsert_batch(records[start : start + batch_size])

    def _chunk_to_upsert_record(self, record: ChunkRecord) -> dict[str, Any]:
        vector = self.embedder.embed(record.text)
        return {
            "id": record.id,
            "vector": vector,
            "meta": {
                "title": record.title,
                "source": record.source,
                "department": record.department,
                "doc_type": record.doc_type,
                "audience": record.audience,
                "chunk_index": record.chunk_index,
                "text": record.text,
                "excerpt": truncate(record.text, 220),
            },
            "filter": {
                "department": record.department,
                "doc_type": record.doc_type,
                "audience": record.audience,
            },
        }

    def upsert_document(
        self,
        *,
        document_id: str,
        title: str,
        source: str,
        department: str,
        doc_type: str,
        audience: str,
        body: str,
    ) -> int:
        chunk_records = build_chunk_records(
            document_id=document_id,
            title=title,
            source=source,
            department=department,
            doc_type=doc_type,
            audience=audience,
            body=body,
        )
        records = [self._chunk_to_upsert_record(record) for record in chunk_records]
        self._upsert_in_batches(records)
        return len(records)

    def seed_sample_corpus(self) -> int:
        total_chunks = 0
        for document in SAMPLE_DOCUMENTS:
            total_chunks += self.upsert_document(
                document_id=document.id,
                title=document.title,
                source=document.source,
                department=document.department,
                doc_type=document.doc_type,
                audience=document.audience,
                body=document.body,
            )
        self._seeded_chunk_count = total_chunks
        return total_chunks

    def bootstrap(self, retries: int = 8, delay_seconds: float = 1.0) -> None:
        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                self.ensure_index()
                if self.settings.seed_sample_data:
                    self.seed_sample_corpus()
                self._bootstrapped = True
                self._bootstrap_error = None
                self._last_bootstrap_at = time.time()
                return
            except Exception as exc:  # pragma: no cover - depends on Endee runtime state
                last_error = exc
                self._bootstrap_error = str(exc)
                logger.warning("Endee bootstrap attempt %s/%s failed: %s", attempt, retries, exc)
                time.sleep(delay_seconds)
        self._bootstrapped = False
        if last_error is not None:
            raise last_error

    async def bootstrap_async(self) -> None:
        try:
            await asyncio.to_thread(self.bootstrap)
        except Exception as exc:  # pragma: no cover - startup failure path
            logger.exception("Endee bootstrap failed")
            self._bootstrap_error = str(exc)

    def _normalize_filter_params(self, department: str, doc_type: str, audience: str) -> dict[str, str]:
        return {
            "department": department or "all",
            "doc_type": doc_type or "all",
            "audience": audience or "all",
        }

    def search(
        self,
        *,
        query: str,
        department: str = "all",
        doc_type: str = "all",
        audience: str = "all",
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        vector = self.embedder.embed(query)
        clauses = build_endee_filter(department=department, doc_type=doc_type, audience=audience)
        kwargs: dict[str, Any] = {
            "vector": vector,
            "top_k": top_k,
            "ef": 128,
            "include_vectors": False,
        }
        if clauses:
            kwargs["filter"] = clauses

        results = self.index.query(**kwargs)
        normalized: list[dict[str, Any]] = []
        for item in results:
            meta = item.get("meta") or item.get("metadata") or {}
            normalized.append(
                {
                    "id": item.get("id", ""),
                    "title": meta.get("title", "Untitled"),
                    "department": meta.get("department", ""),
                    "doc_type": meta.get("doc_type", ""),
                    "audience": meta.get("audience", ""),
                    "source": meta.get("source", ""),
                    "score": float(item.get("similarity") or item.get("score") or 0.0),
                    "chunk_index": int(meta.get("chunk_index") or 0),
                    "text": meta.get("text") or meta.get("excerpt") or "",
                    "excerpt": meta.get("excerpt") or truncate(meta.get("text") or "", 220),
                }
            )
        return normalized

    def related(
        self,
        *,
        text: str,
        department: str = "all",
        doc_type: str = "all",
        audience: str = "all",
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        return self.search(query=text, department=department, doc_type=doc_type, audience=audience, top_k=top_k)

    def answer(
        self,
        *,
        question: str,
        department: str = "all",
        doc_type: str = "all",
        audience: str = "all",
        top_k: int = 4,
    ) -> dict[str, Any]:
        hits = self.search(query=question, department=department, doc_type=doc_type, audience=audience, top_k=top_k)
        if self.settings.openai_api_key:
            result = openai_answer(question, hits, api_key=self.settings.openai_api_key, model=self.settings.openai_model)
        else:
            result = extractive_answer(question, hits)

        result["filters"] = self._normalize_filter_params(department, doc_type, audience)
        result["hits"] = hits
        return result

    def status(self) -> dict[str, Any]:
        filters = filter_catalog()
        examples = example_questions()
        return {
            "ready": self._bootstrapped,
            "app_name": self.settings.app_name,
            "index_name": self.settings.endee_index_name,
            "endee_base_url": self.settings.endee_base_url,
            "embedding_model": self.settings.embedding_model,
            "embedding_backend": self.embedder.backend,
            "sample_documents": len(SAMPLE_DOCUMENTS),
            "sample_chunks": self._seeded_chunk_count,
            "openai_enabled": bool(self.settings.openai_api_key),
            "error": self._bootstrap_error,
            "filters": filters,
            "examples": examples,
        }

