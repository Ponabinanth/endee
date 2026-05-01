from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentSummary(BaseModel):
    document_id: str
    filename: str
    title: str
    source: str
    chunk_count: int
    character_count: int


class UploadResponse(BaseModel):
    documents: list[DocumentSummary]
    chunks_indexed: int
    message: str


class IngestFile(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)


class IngestRequest(BaseModel):
    files: list[IngestFile] = Field(default_factory=list)


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=12)
    history: list["ChatTurn"] = Field(default_factory=list, max_length=12)


class ChatTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class Citation(BaseModel):
    label: str
    document_id: str
    title: str
    source: str
    chunk_index: int
    score: float
    excerpt: str


class ChatResponse(BaseModel):
    question: str
    answer: str
    mode: str
    citations: list[Citation]
    latency_ms: float
    retrieval_ms: float


class MetricsResponse(BaseModel):
    documents: int
    chunks: int
    chats_served: int
    average_latency_ms: float
    average_retrieval_ms: float


class HealthResponse(BaseModel):
    status: str
    app_name: str
    documents: int
    chunks: int
    openai_enabled: bool
