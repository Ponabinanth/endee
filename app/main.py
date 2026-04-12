from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import load_settings
from app.knowledge_base import KnowledgeBase
from app.models import (
    AnswerRequest,
    AnswerResponse,
    FraudScoreRequest,
    FraudScoreResponse,
    InterviewEvaluationRequest,
    InterviewEvaluationResponse,
    InterviewPlanRequest,
    InterviewPlanResponse,
    JobSnapshot,
    RankRequest,
    RankResponse,
    RelatedRequest,
    ResumeFeedbackRequest,
    ResumeFeedbackResponse,
    ResumeUploadRequest,
    SearchRequest,
    SearchResponse,
    StatusResponse,
    UploadResponse,
    ResultItem,
    AnswerCitation,
)

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
    await app.state.kb.bootstrap_async()
    status = app.state.kb.status()
    app.state.ready = bool(status["ready"])
    app.state.bootstrap_error = status.get("error")
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


def get_kb(request: Request) -> KnowledgeBase:
    return request.app.state.kb


def ensure_ready(request: Request) -> None:
    if not request.app.state.ready:
        error = request.app.state.bootstrap_error or "Vector store is not ready yet."
        raise HTTPException(
            status_code=503,
            detail={
                "message": f"{request.app.title} is still initializing.",
                "error": error,
                "suggestion": "The app will fall back to the local vector store if Endee is unavailable.",
            },
        )


def _to_result_item(result: dict[str, object]) -> ResultItem:
    return ResultItem(
        id=str(result.get("id", "")),
        name=str(result.get("name", "Untitled candidate")),
        headline=str(result.get("headline", "")),
        target_role=str(result.get("target_role", "")),
        location=str(result.get("location", "")),
        years_experience=float(result.get("years_experience") or 0.0),
        skills=list(result.get("skills") or []),
        source=str(result.get("source", "")),
        score=float(result.get("score") or 0.0),
        text=str(result.get("text", "")),
        excerpt=str(result.get("excerpt", "")),
        similarity_label=str(result.get("similarity_label", f"{float(result.get('score') or 0.0):.3f}")),
        reasons=list(result.get("reasons") or []),
    )


def _to_citation(result: dict[str, object], label: str) -> AnswerCitation:
    return AnswerCitation(
        label=label,
        title=str(result.get("title") or result.get("name") or "Untitled candidate"),
        source=str(result.get("source", "")),
        target_role=str(result.get("target_role") or result.get("department") or ""),
        location=str(result.get("location") or result.get("audience") or ""),
        score=float(result.get("score") or 0.0),
        excerpt=str(result.get("excerpt", "")),
        reasons=list(result.get("reasons") or []),
    )


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    status = request.app.state.kb.status()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "app_name": settings.app_name,
            "status": status,
        },
    )


@app.get("/api/status", response_model=StatusResponse)
async def api_status(request: Request):
    return request.app.state.kb.status()


@app.get("/api/candidates")
async def api_candidates(request: Request):
    ensure_ready(request)
    return request.app.state.kb.candidate_snapshots()


@app.get("/api/jobs")
async def api_jobs(request: Request):
    ensure_ready(request)
    return request.app.state.kb.job_snapshots()


@app.post("/api/search", response_model=SearchResponse)
async def api_search(payload: SearchRequest, request: Request):
    ensure_ready(request)
    kb = get_kb(request)
    results = kb.search(query=payload.query, role=payload.role, location=payload.location, stage=payload.stage, top_k=payload.top_k)
    return SearchResponse(
        query=payload.query,
        filters={"role": payload.role, "location": payload.location, "stage": payload.stage},
        results=[_to_result_item(result) for result in results],
    )


@app.post("/api/related", response_model=SearchResponse)
async def api_related(payload: RelatedRequest, request: Request):
    ensure_ready(request)
    kb = get_kb(request)
    results = kb.related(text=payload.text, role=payload.role, location=payload.location, stage=payload.stage, top_k=payload.top_k)
    return SearchResponse(
        query=payload.text,
        filters={"role": payload.role, "location": payload.location, "stage": payload.stage},
        results=[_to_result_item(result) for result in results],
    )


@app.post("/api/answer", response_model=AnswerResponse)
async def api_answer(payload: AnswerRequest, request: Request):
    ensure_ready(request)
    kb = get_kb(request)
    result = kb.answer(question=payload.question, role=payload.role, location=payload.location, stage=payload.stage, top_k=payload.top_k)
    return AnswerResponse(
        question=payload.question,
        mode=result["mode"],
        answer=result["answer"],
        citations=[_to_citation(item, str(item.get("label") or f"[{index}]")) for index, item in enumerate(result["citations"], start=1)],
        context=result["context"],
        filters=result.get("filters", {}),
        raw=result.get("raw", {}),
    )


@app.post("/api/rank", response_model=RankResponse)
async def api_rank(payload: RankRequest, request: Request):
    ensure_ready(request)
    kb = get_kb(request)
    result = kb.rank_candidates(
        job=payload.job.model_dump(),
        query=payload.query,
        role=payload.role,
        location=payload.location,
        stage=payload.stage,
        top_k=payload.top_k,
    )
    return RankResponse(**result)


@app.post("/api/interview/questions", response_model=InterviewPlanResponse)
async def api_interview_questions(payload: InterviewPlanRequest, request: Request):
    ensure_ready(request)
    kb = get_kb(request)
    result = kb.plan_interview(
        candidate=payload.candidate.model_dump(),
        job=payload.job.model_dump(),
        num_questions=payload.num_questions,
    )
    return InterviewPlanResponse(**result)


@app.post("/api/interview/evaluate", response_model=InterviewEvaluationResponse)
async def api_interview_evaluate(payload: InterviewEvaluationRequest, request: Request):
    ensure_ready(request)
    kb = get_kb(request)
    result = kb.evaluate_interview(
        candidate=payload.candidate.model_dump(),
        job=payload.job.model_dump(),
        answers=[item.model_dump() for item in payload.answers],
        telemetry=payload.telemetry.model_dump(),
    )
    return InterviewEvaluationResponse(**result)


@app.post("/api/resume-feedback", response_model=ResumeFeedbackResponse)
async def api_resume_feedback(payload: ResumeFeedbackRequest, request: Request):
    ensure_ready(request)
    kb = get_kb(request)
    result = kb.resume_feedback(candidate=payload.candidate.model_dump(), job=payload.job.model_dump())
    return ResumeFeedbackResponse(**result)


@app.post("/api/fraud-score", response_model=FraudScoreResponse)
async def api_fraud_score(payload: FraudScoreRequest, request: Request):
    ensure_ready(request)
    kb = get_kb(request)
    result = kb.score_fraud(payload.telemetry.model_dump())
    return FraudScoreResponse(**result)


@app.post("/api/vector-store/reconnect", response_model=StatusResponse)
async def api_vector_store_reconnect(request: Request):
    kb = get_kb(request)
    status = kb.reconnect_vector_store()
    return StatusResponse(**status)


@app.post("/api/jobs", response_model=JobSnapshot)
async def api_create_job(payload: JobSnapshot, request: Request):
    ensure_ready(request)
    kb = get_kb(request)
    result = kb.upsert_job(payload.model_dump())
    job_data = payload.model_dump()
    job_data["job_id"] = result.get("job_id")
    return JobSnapshot(**job_data)


@app.post("/api/upload", response_model=UploadResponse)
async def api_upload(payload: ResumeUploadRequest, request: Request):
    ensure_ready(request)
    kb = get_kb(request)
    if not payload.files:
        raise HTTPException(status_code=400, detail="Please upload at least one .txt or .md file.")

    total_chunks = 0
    candidate_ids: list[str] = []

    for upload in payload.files:
        filename = Path(upload.filename or "candidate.txt").name
        suffix = Path(filename).suffix.lower()
        if suffix not in {".txt", ".md", ".markdown"}:
            raise HTTPException(status_code=400, detail=f"Unsupported file type for {filename}. Use .txt or .md files.")
        text = (upload.content or "").strip()
        if not text:
            continue

        resolved_name = (payload.name or Path(filename).stem).strip()
        record = {
            "candidate_id": None,
            "name": resolved_name,
            "headline": payload.target_role,
            "target_role": payload.target_role,
            "years_experience": float(payload.years_experience or 0.0),
            "location": payload.location or "Remote",
            "skills": list(payload.skills or []),
            "resume_text": text,
            "source": f"{payload.source_prefix}/{filename}",
            "stage": payload.stage or "screening",
        }
        result = kb.upsert_candidate(record)
        total_chunks += int(result.get("chunks_indexed") or 0)
        if result.get("candidate_id"):
            candidate_ids.append(str(result["candidate_id"]))

    return UploadResponse(
        uploaded_files=len(payload.files),
        uploaded_chunks=total_chunks,
        message="Resume(s) uploaded and indexed for semantic candidate search.",
        candidate_ids=candidate_ids,
    )
