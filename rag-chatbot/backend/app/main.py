from __future__ import annotations

import logging
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.document_loader import chunk_text, read_upload
from app.embeddings import HashEmbedder
from app.rag_chain import RagChain, truncate
from app.schemas import ChatRequest, ChatResponse, DocumentSummary, HealthResponse, IngestRequest, MetricsResponse, UploadResponse
from app.vector_store import LocalVectorStore


settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

embedder = HashEmbedder(dimension=settings.embedding_dimension)
store = LocalVectorStore(settings.index_path)
rag_chain = RagChain(
    store=store,
    embedder=embedder,
    openai_api_key=settings.openai_api_key,
    openai_model=settings.openai_model,
)
metrics = {
    "chats_served": 0,
    "total_latency_ms": 0.0,
    "total_retrieval_ms": 0.0,
}


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "request method=%s path=%s status=%s latency_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        latency_ms,
    )
    return response


def summarize_document(document_id: str) -> DocumentSummary:
    document = store.documents[document_id]
    chunk_count = sum(1 for chunk in store.chunks.values() if chunk.document_id == document_id)
    return DocumentSummary(
        document_id=document.document_id,
        filename=document.filename,
        title=document.title,
        source=document.source,
        chunk_count=chunk_count,
        character_count=len(document.text),
    )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        documents=len(store.documents),
        chunks=len(store.chunks),
        openai_enabled=bool(settings.openai_api_key),
    )


@app.get("/documents", response_model=list[DocumentSummary])
async def list_documents() -> list[DocumentSummary]:
    return [summarize_document(document_id) for document_id in store.documents]


@app.get("/metrics", response_model=MetricsResponse)
async def get_metrics() -> MetricsResponse:
    chats_served = int(metrics["chats_served"])
    return MetricsResponse(
        documents=len(store.documents),
        chunks=len(store.chunks),
        chats_served=chats_served,
        average_latency_ms=round(metrics["total_latency_ms"] / chats_served, 2) if chats_served else 0.0,
        average_retrieval_ms=round(metrics["total_retrieval_ms"] / chats_served, 2) if chats_served else 0.0,
    )


async def _index_files(files: list[tuple[str, bytes]]) -> UploadResponse:
    summaries: list[DocumentSummary] = []
    chunks_indexed = 0

    for filename, content in files:
        filename = Path(filename or "document.txt").name
        try:
            text = (await read_upload(filename, content)).strip()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if not text:
            continue

        raw_chunks = chunk_text(text)
        indexed_chunks = [
            (index, chunk, embedder.embed(chunk))
            for index, chunk in enumerate(raw_chunks, start=1)
        ]
        document = store.add_document(
            filename=filename,
            title=Path(filename).stem,
            source=f"uploads/{filename}",
            text=text,
            chunks=indexed_chunks,
        )
        chunks_indexed += len(indexed_chunks)
        summaries.append(summarize_document(document.document_id))

    if not summaries:
        raise HTTPException(status_code=400, detail="No readable document text was found.")

    return UploadResponse(
        documents=summaries,
        chunks_indexed=chunks_indexed,
        message="Documents uploaded, chunked, embedded, and indexed.",
    )


@app.post("/ingest", response_model=UploadResponse)
async def ingest_documents(payload: IngestRequest) -> UploadResponse:
    files = [(file.filename, file.content.encode("utf-8")) for file in payload.files]
    return await _index_files(files)


@app.post("/upload", response_model=UploadResponse)
async def upload_documents(request: Request) -> UploadResponse:
    try:
        form = await request.form()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Multipart upload requires python-multipart. Install backend requirements or use POST /ingest.",
        ) from exc

    files: list[tuple[str, bytes]] = []
    for value in form.getlist("files"):
        filename = Path(getattr(value, "filename", "") or "document.txt").name
        read = getattr(value, "read", None)
        if callable(read):
            files.append((filename, await read()))

    return await _index_files(files)


@app.delete("/documents/{document_id}")
async def delete_document(document_id: str) -> dict[str, str]:
    if not store.delete_document(document_id):
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"status": "deleted", "document_id": document_id}


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    response = rag_chain.answer(payload.question, top_k=payload.top_k, history=payload.history)
    metrics["chats_served"] += 1
    metrics["total_latency_ms"] += response.latency_ms
    metrics["total_retrieval_ms"] += response.retrieval_ms
    return response


@app.post("/chat/stream")
async def chat_stream(payload: ChatRequest) -> StreamingResponse:
    response = rag_chain.answer(payload.question, top_k=payload.top_k, history=payload.history)
    metrics["chats_served"] += 1
    metrics["total_latency_ms"] += response.latency_ms
    metrics["total_retrieval_ms"] += response.retrieval_ms

    async def stream_answer():
        for token in response.answer.split():
            yield token + " "

    return StreamingResponse(stream_answer(), media_type="text/plain")
