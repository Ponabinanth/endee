from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict
from typing import Any

from app.config import Settings
from app.filters import build_endee_filter
from app.models import CandidateSnapshot, JobSnapshot
from app.rag import extractive_answer, openai_answer, truncate
from app.sample_corpus import SAMPLE_CANDIDATES, SAMPLE_JOBS, example_questions, filter_catalog
from app.scoring import (
    CandidateProfile,
    JobRole,
    build_rank_breakdown,
    dedupe_preserve_order,
    evaluate_interview_answers,
    generate_interview_questions,
    missing_skills,
    resume_feedback as score_resume_feedback,
    fraud_assessment,
)
from app.vector_store import InMemoryVectorStore, select_vector_store

logger = logging.getLogger(__name__)


class KnowledgeBase:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        from app.embeddings import Embedder

        self.embedder = Embedder(settings.embedding_model)
        self._vector_store = select_vector_store(
            backend=settings.vector_store_backend,
            endee_base_url=settings.endee_base_url,
            endee_auth_token=settings.endee_auth_token,
        )
        self._index = None
        self._bootstrapped = False
        self._bootstrap_error: str | None = None
        self._last_bootstrap_at: float | None = None
        self._candidates: dict[str, CandidateProfile] = {}
        self._jobs: dict[str, JobRole] = {}
        self._interviews: dict[tuple[str, str], dict[str, Any]] = {}
        self._telemetry: dict[tuple[str, str], dict[str, Any]] = {}

    @property
    def vector_store_backend(self) -> str:
        return getattr(self._vector_store, "backend", "unknown")

    @property
    def index(self):
        if self._index is None:
            self._index = self._vector_store.get_index(name=self.settings.endee_index_name)
        return self._index

    def _fallback_to_memory(self, exc: Exception) -> None:
        logger.warning("Falling back to in-memory vector store: %s", exc)
        self._bootstrap_error = f"Endee unavailable; using in-memory vector store. Error: {exc}"
        self._vector_store = InMemoryVectorStore()
        self._index = None

    def ensure_index(self) -> None:
        try:
            if self.vector_store_backend == "endee":
                from endee import Precision

                self._vector_store.create_index(
                    name=self.settings.endee_index_name,
                    dimension=384,
                    space_type="cosine",
                    precision=Precision.INT8,
                )
            else:
                self._vector_store.create_index(name=self.settings.endee_index_name, dimension=384, space_type="cosine")
        except Exception as exc:
            message = str(exc).lower()
            if "already exists" in message or "exists" in message:
                return
            if self.vector_store_backend == "endee":
                self._fallback_to_memory(exc)
                self._vector_store.create_index(name=self.settings.endee_index_name, dimension=384, space_type="cosine")
                return
            raise

    def _next_id(self, prefix: str) -> str:
        return f"{prefix}-{len(self._candidates) + len(self._jobs) + 1:04d}"

    def _upsert_record(self, record_id: str, text: str, meta: dict[str, Any], filt: dict[str, Any]) -> None:
        vector = self.embedder.embed(text)
        record = {
            "id": record_id,
            "vector": vector,
            "meta": {**meta, "text": text, "excerpt": truncate(text, 220)},
            "filter": filt,
        }
        self.index.upsert([record])

    def _candidate_to_profile(self, data: dict[str, Any]) -> CandidateProfile:
        return CandidateProfile(
            id=str(data.get("candidate_id") or data.get("id") or ""),
            name=str(data.get("name") or "Anonymous Candidate"),
            headline=str(data.get("headline") or ""),
            years_experience=float(data.get("years_experience") or 0.0),
            location=str(data.get("location") or "Remote"),
            target_role=str(data.get("target_role") or ""),
            skills=tuple(data.get("skills") or ()),
            resume_text=str(data.get("resume_text") or ""),
            source=str(data.get("source") or ""),
            stage=str(data.get("stage") or "screening"),
            summary=str(data.get("summary") or ""),
            projects=tuple(data.get("projects") or ()),
        )

    def _job_to_role(self, data: dict[str, Any]) -> JobRole:
        return JobRole(
            id=str(data.get("job_id") or data.get("id") or ""),
            title=str(data.get("title") or "Job Role"),
            department=str(data.get("department") or "engineering"),
            location=str(data.get("location") or "Remote"),
            min_years_experience=float(data.get("min_years_experience") or 0.0),
            must_have_skills=tuple(data.get("must_have_skills") or ()),
            nice_to_have_skills=tuple(data.get("nice_to_have_skills") or ()),
            description=str(data.get("description") or ""),
            interview_focus=tuple(data.get("interview_focus") or ()),
            source=str(data.get("source") or ""),
        )

    def upsert_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        profile = self._candidate_to_profile(candidate)
        if not profile.id:
            profile = CandidateProfile(
                id=self._next_id("cand"),
                name=profile.name,
                headline=profile.headline,
                years_experience=profile.years_experience,
                location=profile.location,
                target_role=profile.target_role,
                skills=profile.skills,
                resume_text=profile.resume_text,
                source=profile.source,
                stage=profile.stage,
                summary=profile.summary,
                projects=profile.projects,
            )
        self._candidates[profile.id] = profile

        if profile.resume_text:
            self._upsert_record(
                record_id=f"candidate-{profile.id}",
                text=" ".join([profile.resume_text, profile.summary, " ".join(profile.skills)]).strip(),
                meta={
                    "entity_type": "candidate",
                    "candidate_id": profile.id,
                    "name": profile.name,
                    "headline": profile.headline,
                    "target_role": profile.target_role,
                    "years_experience": profile.years_experience,
                    "location": profile.location,
                    "skills": list(profile.skills),
                    "source": profile.source,
                    "stage": profile.stage,
                    "summary": profile.summary,
                    "projects": list(profile.projects),
                },
                filt={
                    "entity_type": "candidate",
                    "target_role": profile.target_role or "all",
                    "location": profile.location or "all",
                    "stage": profile.stage or "screening",
                },
            )
            return {"candidate_id": profile.id, "chunks_indexed": 1}

        return {"candidate_id": profile.id, "chunks_indexed": 0}

    def upsert_job(self, job: dict[str, Any]) -> dict[str, Any]:
        role = self._job_to_role(job)
        if not role.id:
            role = JobRole(
                id=self._next_id("job"),
                title=role.title,
                department=role.department,
                location=role.location,
                min_years_experience=role.min_years_experience,
                must_have_skills=role.must_have_skills,
                nice_to_have_skills=role.nice_to_have_skills,
                description=role.description,
                interview_focus=role.interview_focus,
                source=role.source,
            )
        self._jobs[role.id] = role

        if role.description:
            self._upsert_record(
                record_id=f"job-{role.id}",
                text=" ".join([role.title, role.description, " ".join(role.must_have_skills), " ".join(role.nice_to_have_skills)]).strip(),
                meta={
                    "entity_type": "job",
                    "job_id": role.id,
                    "title": role.title,
                    "department": role.department,
                    "location": role.location,
                    "min_years_experience": role.min_years_experience,
                    "must_have_skills": list(role.must_have_skills),
                    "nice_to_have_skills": list(role.nice_to_have_skills),
                    "description": role.description,
                    "interview_focus": list(role.interview_focus),
                    "source": role.source,
                },
                filt={
                    "entity_type": "job",
                    "target_role": role.title,
                    "location": role.location or "all",
                    "stage": "job",
                },
            )
            return {"job_id": role.id, "chunks_indexed": 1}

        return {"job_id": role.id, "chunks_indexed": 0}

    def candidate_snapshots(self) -> list[CandidateSnapshot]:
        return [
            CandidateSnapshot(
                candidate_id=candidate.id,
                name=candidate.name,
                headline=candidate.headline,
                target_role=candidate.target_role,
                years_experience=candidate.years_experience,
                location=candidate.location,
                skills=list(candidate.skills),
                resume_text=candidate.resume_text,
                source=candidate.source,
                stage=candidate.stage,
            )
            for candidate in self._candidates.values()
        ]

    def job_snapshots(self) -> list[JobSnapshot]:
        return [
            JobSnapshot(
                job_id=job.id,
                title=job.title,
                description=job.description,
                department=job.department,
                location=job.location,
                min_years_experience=job.min_years_experience,
                must_have_skills=list(job.must_have_skills),
                nice_to_have_skills=list(job.nice_to_have_skills),
                interview_focus=list(job.interview_focus),
            )
            for job in self._jobs.values()
        ]

    def seed_sample_corpus(self) -> tuple[int, int]:
        candidate_count = 0
        job_count = 0
        for candidate in SAMPLE_CANDIDATES:
            candidate_count += self.upsert_candidate(asdict(candidate))["chunks_indexed"]
        for job in SAMPLE_JOBS:
            job_count += self.upsert_job(asdict(job))["chunks_indexed"]
        return candidate_count, job_count

    def bootstrap(self) -> None:
        try:
            self.ensure_index()
            if self.settings.seed_sample_data:
                candidate_count, job_count = self.seed_sample_corpus()
            else:
                candidate_count, job_count = 0, 0
            self._bootstrapped = True
            self._bootstrap_error = None
            self._last_bootstrap_at = time.time()
            self._seeded_candidates = candidate_count
            self._seeded_jobs = job_count
        except Exception as exc:  # pragma: no cover - runtime dependent
            self._bootstrap_error = str(exc)
            raise

    async def bootstrap_async(self) -> None:
        try:
            await asyncio.to_thread(self.bootstrap)
        except Exception as exc:  # pragma: no cover
            logger.exception("Bootstrap failed")
            self._bootstrap_error = str(exc)
            if self.settings.vector_store_backend == "auto" and self.vector_store_backend != "memory":
                self._fallback_to_memory(exc)
                self.bootstrap()

    def status(self) -> dict[str, Any]:
        catalog = filter_catalog()
        candidate_roles = [candidate.target_role for candidate in self._candidates.values() if candidate.target_role]
        job_roles = [job.title for job in self._jobs.values() if job.title]
        candidate_locations = [candidate.location for candidate in self._candidates.values() if candidate.location]
        job_locations = [job.location for job in self._jobs.values() if job.location]
        candidate_skills = [skill for candidate in self._candidates.values() for skill in candidate.skills]
        job_skills = [skill for job in self._jobs.values() for skill in (*job.must_have_skills, *job.nice_to_have_skills)]
        return {
            "ready": self._bootstrapped,
            "app_name": self.settings.app_name,
            "index_name": self.settings.endee_index_name,
            "endee_base_url": self.settings.endee_base_url,
            "vector_store_backend": self.vector_store_backend,
            "embedding_model": self.settings.embedding_model,
            "embedding_backend": self.embedder.backend,
            "sample_candidates": len(self._candidates),
            "sample_jobs": len(self._jobs),
            "openai_enabled": bool(self.settings.openai_api_key),
            "error": self._bootstrap_error,
            "filters": {
                "roles": dedupe_preserve_order([*candidate_roles, *job_roles, *catalog["roles"]]),
                "locations": dedupe_preserve_order([*candidate_locations, *job_locations, *catalog["locations"]]),
                "stages": dedupe_preserve_order([*(candidate.stage for candidate in self._candidates.values()), "screening", "interview", "assessment", "final"]),
                "skills": dedupe_preserve_order([*candidate_skills, *job_skills, *catalog["skills"]]),
            },
            "examples": example_questions(),
        }

    def _search_hits(self, *, query: str, role: str, location: str, stage: str, top_k: int) -> list[dict[str, Any]]:
        vector = self.embedder.embed(query)
        clauses = build_endee_filter(entity_type="candidate", role=role, location=location, stage=stage)
        kwargs: dict[str, Any] = {"vector": vector, "top_k": max(1, int(top_k) * 6), "ef": 128, "include_vectors": False}
        if clauses:
            kwargs["filter"] = clauses
        raw = self.index.query(**kwargs)

        best: dict[str, dict[str, Any]] = {}
        for item in raw:
            meta = item.get("meta") or item.get("metadata") or {}
            candidate_id = str(meta.get("candidate_id") or item.get("id") or "")
            score = float(item.get("similarity") or item.get("score") or 0.0)
            if not candidate_id:
                continue
            if candidate_id not in best or score > best[candidate_id]["score"]:
                profile = self._candidates.get(candidate_id) or self._candidate_to_profile({"candidate_id": candidate_id, **meta})
                best[candidate_id] = {
                    "id": candidate_id,
                    "name": profile.name,
                    "headline": profile.headline,
                    "target_role": profile.target_role,
                    "location": profile.location,
                    "years_experience": profile.years_experience,
                    "skills": list(profile.skills),
                    "source": profile.source,
                    "score": score,
                    "text": profile.resume_text,
                    "excerpt": truncate(profile.resume_text or meta.get("excerpt") or "", 220),
                    "similarity_label": f"{score:.3f}",
                    "reasons": dedupe_preserve_order(
                        [
                            f"Semantic overlap with '{query}'.",
                            f"Skills snapshot: {', '.join(list(profile.skills)[:4]) or 'n/a'}.",
                        ]
                    ),
                }

        return sorted(best.values(), key=lambda item: item["score"], reverse=True)[: max(1, int(top_k))]

    def search(self, *, query: str, role: str = "all", location: str = "all", stage: str = "all", top_k: int = 5) -> list[dict[str, Any]]:
        return self._search_hits(query=query, role=role, location=location, stage=stage, top_k=top_k)

    def related(self, *, text: str, role: str = "all", location: str = "all", stage: str = "all", top_k: int = 5) -> list[dict[str, Any]]:
        return self._search_hits(query=text, role=role, location=location, stage=stage, top_k=top_k)

    def answer(self, *, question: str, role: str = "all", location: str = "all", stage: str = "all", top_k: int = 4) -> dict[str, Any]:
        hits = self._search_hits(query=question, role=role, location=location, stage=stage, top_k=top_k)
        rag_hits = [
            {
                "title": hit["name"],
                "source": hit["source"],
                "department": hit["target_role"],
                "doc_type": "candidate_resume",
                "audience": hit["location"],
                "score": hit["score"],
                "text": hit["text"],
            }
            for hit in hits
        ]
        if self.settings.openai_api_key:
            result = openai_answer(question, rag_hits, api_key=self.settings.openai_api_key, model=self.settings.openai_model)
        else:
            result = extractive_answer(question, rag_hits)
        return {
            "mode": result["mode"],
            "answer": result["answer"],
            "citations": result["citations"],
            "context": result["context"],
            "filters": {"role": role, "location": location, "stage": stage},
            "raw": result.get("raw", {}),
        }

    def rank_candidates(
        self,
        *,
        job: dict[str, Any],
        query: str = "",
        role: str = "all",
        location: str = "all",
        stage: str = "all",
        top_k: int = 5,
    ) -> dict[str, Any]:
        role_model = self._job_to_role(job)
        query_text = query.strip() or f"{role_model.title} {role_model.description}"
        hits = self._search_hits(query=query_text, role=role, location=location, stage=stage, top_k=max(1, int(top_k) * 8))

        ranked: list[dict[str, Any]] = []
        for hit in hits:
            candidate = self._candidates.get(hit["id"]) or self._candidate_to_profile({"candidate_id": hit["id"], **hit})
            breakdown = build_rank_breakdown(candidate, role_model, semantic_score=hit["score"])
            ranked.append(
                {
                    "id": candidate.id,
                    "name": candidate.name,
                    "headline": candidate.headline,
                    "target_role": candidate.target_role,
                    "location": candidate.location,
                    "years_experience": candidate.years_experience,
                    "skills": list(candidate.skills),
                    "source": candidate.source,
                    "semantic_score": breakdown["semantic_score"],
                    "overall_score": breakdown["overall_score"],
                    "score_breakdown": {
                        "semantic": breakdown["semantic_score"],
                        "skills": breakdown["skill_score"],
                        "experience": breakdown["experience_score"],
                        "location": breakdown["location_score"],
                    },
                    "reasons": breakdown["reasons"],
                    "excerpt": hit["excerpt"],
                    "match_label": f"Match {breakdown['overall_score']:.1f}/100",
                }
            )

        ranked.sort(key=lambda item: item["overall_score"], reverse=True)
        ranked = ranked[: max(1, int(top_k))]
        summary = "Ranked candidates with explainable semantic, skills, experience, and location scoring."
        return {"job": job, "query": query_text, "ranked_candidates": ranked, "summary": summary, "raw": {"vector_store_backend": self.vector_store_backend}}

    def plan_interview(self, *, candidate: dict[str, Any], job: dict[str, Any], num_questions: int = 6) -> dict[str, Any]:
        candidate_model = self._candidate_to_profile(candidate)
        job_model = self._job_to_role(job)
        questions = generate_interview_questions(candidate_model, job_model, count=max(1, int(num_questions)))
        return {
            "candidate": asdict(candidate_model),
            "job": asdict(job_model),
            "questions": questions,
            "rubric": {"technical": 0.4, "communication": 0.25, "confidence": 0.15, "fraud_integrity": 0.2},
            "summary": f"Generated {len(questions)} interview questions tailored to {candidate_model.name}.",
            "raw": {
                "matched_skills": dedupe_preserve_order(skill for skill in candidate_model.skills if skill in job_model.must_have_skills),
                "missing_skills": missing_skills(candidate_model.skills, job_model.must_have_skills),
            },
        }

    def score_fraud(self, telemetry: dict[str, Any]) -> dict[str, Any]:
        result = fraud_assessment(telemetry)
        label = "high" if result["fraud_score"] >= 60 else "medium" if result["fraud_score"] >= 30 else "low"
        return {"fraud_score": result["fraud_score"], "flags": result["flags"], "label": label}

    def evaluate_interview(self, *, candidate: dict[str, Any], job: dict[str, Any], answers: list[dict[str, str]], telemetry: dict[str, Any]) -> dict[str, Any]:
        candidate_model = self._candidate_to_profile(candidate)
        job_model = self._job_to_role(job)
        evaluation = evaluate_interview_answers(candidate_model, job_model, answers, telemetry)
        fraud = self.score_fraud(telemetry)
        return {
            "candidate": candidate,
            "job": job,
            "overall_score": evaluation["overall_score"],
            "technical_score": evaluation["technical_score"],
            "communication_score": evaluation["communication_score"],
            "confidence_score": evaluation["confidence_score"],
            "fraud_score": fraud["fraud_score"],
            "fraud_flags": fraud["flags"],
            "reasons": evaluation["reasons"],
            "suggestions": evaluation["suggestions"],
            "raw": evaluation["raw"],
        }

    def resume_feedback(self, *, candidate: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
        candidate_model = self._candidate_to_profile(candidate)
        job_model = self._job_to_role(job)
        feedback = score_resume_feedback(candidate_model, job_model)
        return {
            "candidate": candidate,
            "job": job,
            "summary": feedback["summary"],
            "suggestions": feedback["suggestions"],
            "missing_skills": feedback["missing_skills"],
            "raw": feedback["raw"],
        }
