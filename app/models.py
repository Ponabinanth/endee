from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=400)
    role: str = "all"
    location: str = "all"
    stage: str = "all"
    top_k: int = Field(default=5, ge=1, le=10)


class AnswerRequest(BaseModel):
    question: str = Field(min_length=2, max_length=400)
    role: str = "all"
    location: str = "all"
    stage: str = "all"
    top_k: int = Field(default=4, ge=1, le=10)


class RelatedRequest(BaseModel):
    text: str = Field(min_length=2, max_length=400)
    role: str = "all"
    location: str = "all"
    stage: str = "all"
    top_k: int = Field(default=5, ge=1, le=10)


class CandidateSnapshot(BaseModel):
    candidate_id: str | None = None
    name: str = "Anonymous Candidate"
    headline: str = ""
    target_role: str = ""
    years_experience: float = Field(default=0, ge=0, le=50)
    location: str = "Remote"
    skills: list[str] = Field(default_factory=list)
    resume_text: str = ""
    source: str = ""
    stage: str = "screening"


class JobSnapshot(BaseModel):
    job_id: str | None = None
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=2, max_length=6000)
    department: str = "engineering"
    location: str = "Remote"
    min_years_experience: float = Field(default=0, ge=0, le=50)
    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    interview_focus: list[str] = Field(default_factory=list)


class UploadResponse(BaseModel):
    uploaded_files: int
    uploaded_chunks: int
    message: str
    candidate_ids: list[str] = Field(default_factory=list)


class ResumeFilePayload(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=200_000)


class ResumeUploadRequest(BaseModel):
    files: list[ResumeFilePayload] = Field(default_factory=list)
    name: str = ""
    target_role: str = "AI Engineer"
    years_experience: float = Field(default=0, ge=0, le=50)
    location: str = "Remote"
    skills: list[str] = Field(default_factory=list)
    stage: str = "screening"
    source_prefix: str = "candidates"


class StatusResponse(BaseModel):
    ready: bool
    app_name: str
    index_name: str
    endee_base_url: str
    vector_store_backend: str
    embedding_model: str
    embedding_backend: str
    sample_candidates: int
    sample_jobs: int
    openai_enabled: bool
    error: str | None = None
    filters: dict[str, list[str]] = Field(default_factory=dict)
    examples: list[str] = Field(default_factory=list)


class ResultItem(BaseModel):
    id: str
    name: str
    headline: str
    target_role: str
    location: str
    years_experience: float
    skills: list[str]
    source: str
    score: float
    text: str
    excerpt: str
    similarity_label: str
    reasons: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    query: str
    filters: dict[str, str]
    results: list[ResultItem]


class AnswerCitation(BaseModel):
    label: str
    title: str
    source: str
    target_role: str
    location: str
    score: float
    excerpt: str
    reasons: list[str] = Field(default_factory=list)


class AnswerResponse(BaseModel):
    question: str
    mode: str
    answer: str
    citations: list[AnswerCitation]
    context: str
    filters: dict[str, str]
    raw: dict[str, Any] = Field(default_factory=dict)


class RankedCandidate(BaseModel):
    id: str
    name: str
    headline: str
    target_role: str
    location: str
    years_experience: float
    skills: list[str]
    source: str
    semantic_score: float
    overall_score: float
    score_breakdown: dict[str, float]
    reasons: list[str] = Field(default_factory=list)
    excerpt: str
    match_label: str


class RankResponse(BaseModel):
    job: JobSnapshot
    query: str
    ranked_candidates: list[RankedCandidate]
    summary: str
    raw: dict[str, Any] = Field(default_factory=dict)


class RankRequest(BaseModel):
    job: JobSnapshot
    query: str = ""
    role: str = "all"
    location: str = "all"
    stage: str = "all"
    top_k: int = Field(default=5, ge=1, le=25)


class InterviewQuestionItem(BaseModel):
    question: str
    focus: str
    expected_signal: str
    difficulty: str


class InterviewPlanResponse(BaseModel):
    candidate: CandidateSnapshot
    job: JobSnapshot
    questions: list[InterviewQuestionItem]
    rubric: dict[str, float]
    summary: str
    raw: dict[str, Any] = Field(default_factory=dict)


class InterviewPlanRequest(BaseModel):
    candidate: CandidateSnapshot
    job: JobSnapshot
    num_questions: int = Field(default=6, ge=1, le=12)


class InterviewAnswerItem(BaseModel):
    prompt: str = Field(min_length=2, max_length=800)
    answer: str = Field(min_length=1, max_length=4000)


class InterviewTelemetry(BaseModel):
    tab_switches: int = Field(default=0, ge=0)
    copy_events: int = Field(default=0, ge=0)
    paste_events: int = Field(default=0, ge=0)
    blur_events: int = Field(default=0, ge=0)
    idle_seconds: float = Field(default=0, ge=0)
    multiple_faces_detected: bool = False


class InterviewEvaluationRequest(BaseModel):
    candidate: CandidateSnapshot
    job: JobSnapshot
    answers: list[InterviewAnswerItem] = Field(default_factory=list)
    telemetry: InterviewTelemetry = Field(default_factory=InterviewTelemetry)


class InterviewEvaluationResponse(BaseModel):
    candidate: CandidateSnapshot
    job: JobSnapshot
    overall_score: float
    technical_score: float
    communication_score: float
    confidence_score: float
    fraud_score: float
    fraud_flags: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class ResumeFeedbackRequest(BaseModel):
    candidate: CandidateSnapshot
    job: JobSnapshot


class ResumeFeedbackResponse(BaseModel):
    candidate: CandidateSnapshot
    job: JobSnapshot
    summary: str
    suggestions: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class FraudScoreRequest(BaseModel):
    telemetry: InterviewTelemetry = Field(default_factory=InterviewTelemetry)


class FraudScoreResponse(BaseModel):
    fraud_score: float
    flags: list[str] = Field(default_factory=list)
    label: str = "low"
