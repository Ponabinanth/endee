from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import load_settings
from app.knowledge_base import KnowledgeBase
from app.models import AnswerRequest, AnswerResponse, RelatedRequest, ResultItem, SearchRequest, SearchResponse, StatusResponse, UploadResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = load_settings()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
static_dir = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.kb = KnowledgeBase(settings)
    app.state.ready = False
    app.state.bootstrap_error = None
    app.state.last_status = None
    await app.state.kb.bootstrap_async()
    status = app.state.kb.status()
    app.state.ready = bool(status["ready"])
    app.state.bootstrap_error = status["error"]
    app.state.last_status = status
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


def get_kb(request: Request) -> KnowledgeBase:
    return request.app.state.kb


def ensure_ready(request: Request) -> None:
    if not request.app.state.ready:
        error = request.app.state.bootstrap_error or "Endee is not ready yet."
        raise HTTPException(
            status_code=503,
            detail={
                "message": "InsightForge is waiting for Endee to become available.",
                "error": error,
                "suggestion": "Start the Endee server, then refresh the app.",
            },
        )


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    status = request.app.state.kb.status()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "status": status,
        },
    )


@app.get("/api/status", response_model=StatusResponse)
async def api_status(request: Request):
    return request.app.state.kb.status()


@app.post("/api/search", response_model=SearchResponse)
async def api_search(payload: SearchRequest, request: Request):
    ensure_ready(request)
    kb = get_kb(request)
    results = kb.search(
        query=payload.query,
        department=payload.department,
        doc_type=payload.doc_type,
        audience=payload.audience,
        top_k=payload.top_k,
    )
    items = [
        ResultItem(
            id=result["id"],
            title=result["title"],
            department=result["department"],
            doc_type=result["doc_type"],
            audience=result["audience"],
            source=result["source"],
            score=result["score"],
            chunk_index=result["chunk_index"],
            text=result["text"],
            similarity_label=f"{result['score']:.3f}",
        )
        for result in results
    ]
    return SearchResponse(
        query=payload.query,
        filters={
            "department": payload.department,
            "doc_type": payload.doc_type,
            "audience": payload.audience,
        },
        results=items,
    )


@app.post("/api/answer", response_model=AnswerResponse)
async def api_answer(payload: AnswerRequest, request: Request):
    ensure_ready(request)
    kb = get_kb(request)
    result = kb.answer(
        question=payload.question,
        department=payload.department,
        doc_type=payload.doc_type,
        audience=payload.audience,
        top_k=payload.top_k,
    )
    return AnswerResponse(
        question=payload.question,
        mode=result["mode"],
        answer=result["answer"],
        citations=result["citations"],
        context=result["context"],
        filters=result.get("filters", {}),
        raw=result.get("raw", {}),
    )


@app.post("/api/related", response_model=SearchResponse)
async def api_related(payload: RelatedRequest, request: Request):
    ensure_ready(request)
    kb = get_kb(request)
    results = kb.related(
        text=payload.text,
        department=payload.department,
        doc_type=payload.doc_type,
        audience=payload.audience,
        top_k=payload.top_k,
    )
    items = [
        ResultItem(
            id=result["id"],
            title=result["title"],
            department=result["department"],
            doc_type=result["doc_type"],
            audience=result["audience"],
            source=result["source"],
            score=result["score"],
            chunk_index=result["chunk_index"],
            text=result["text"],
            similarity_label=f"{result['score']:.3f}",
        )
        for result in results
    ]
    return SearchResponse(
        query=payload.text,
        filters={
            "department": payload.department,
            "doc_type": payload.doc_type,
            "audience": payload.audience,
        },
        results=items,
    )


@app.post("/api/upload", response_model=UploadResponse)
async def api_upload(
    request: Request,
    files: Annotated[list[UploadFile], File(...)],
    title: Annotated[str, Form("")] = "",
    department: Annotated[str, Form("engineering")] = "engineering",
    doc_type: Annotated[str, Form("guide")] = "guide",
    audience: Annotated[str, Form("internal")] = "internal",
    source_prefix: Annotated[str, Form("uploads")] = "uploads",
):
    ensure_ready(request)
    kb = get_kb(request)
    if not files:
        raise HTTPException(status_code=400, detail="Please upload at least one .txt or .md file.")

    total_chunks = 0
    valid_extensions = {".txt", ".md", ".markdown"}
    for upload in files:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in valid_extensions:
            raise HTTPException(status_code=400, detail=f"Unsupported file type for {upload.filename}. Use .txt or .md files.")
        raw = await upload.read()
        text = raw.decode("utf-8", errors="ignore").strip()
        if not text:
            continue
        document_title = title.strip() or Path(upload.filename or "uploaded-document").stem.replace("-", " ").replace("_", " ").title()
        document_id = f"{source_prefix}-{Path(upload.filename or 'document').stem}"
        total_chunks += kb.upsert_document(
            document_id=document_id,
            title=document_title,
            source=f"{source_prefix}/{upload.filename or 'document'}",
            department=department,
            doc_type=doc_type,
            audience=audience,
            body=text,
        )

    return UploadResponse(
        uploaded_files=len(files),
        uploaded_chunks=total_chunks,
        message="Document uploaded to Endee and indexed for semantic search.",
    )

