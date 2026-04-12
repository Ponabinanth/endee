from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FilterRequest(BaseModel):
    department: str = "all"
    doc_type: str = "all"
    audience: str = "all"
    top_k: int = Field(default=5, ge=1, le=10)


class SearchRequest(FilterRequest):
    query: str = Field(min_length=2, max_length=400)


class AnswerRequest(FilterRequest):
    question: str = Field(min_length=2, max_length=400)


class RelatedRequest(FilterRequest):
    text: str = Field(min_length=2)


class UploadResponse(BaseModel):
    uploaded_files: int
    uploaded_chunks: int
    message: str


class StatusResponse(BaseModel):
    ready: bool
    app_name: str
    index_name: str
    endee_base_url: str
    embedding_model: str
    embedding_backend: str
    sample_documents: int
    sample_chunks: int
    openai_enabled: bool
    error: str | None = None
    filters: dict[str, list[str]] = Field(default_factory=dict)
    examples: list[str] = Field(default_factory=list)


class ResultItem(BaseModel):
    id: str
    title: str
    department: str
    doc_type: str
    audience: str
    source: str
    score: float
    chunk_index: int
    text: str
    similarity_label: str


class SearchResponse(BaseModel):
    query: str
    filters: dict[str, str]
    results: list[ResultItem]


class AnswerCitation(BaseModel):
    label: str
    title: str
    source: str
    department: str
    doc_type: str
    audience: str
    score: float
    excerpt: str


class AnswerResponse(BaseModel):
    question: str
    mode: str
    answer: str
    citations: list[AnswerCitation]
    context: str
    filters: dict[str, str]
    raw: dict[str, Any] = Field(default_factory=dict)
