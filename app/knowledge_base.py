from __future__ import annotations

import asyncio
import math
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
    skill_overlap,
    resume_feedback as score_resume_feedback,
    fraud_assessment,
)
from app.vector_store import InMemoryVectorStore, select_vector_store

logger = logging.getLogger(__name__)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    limit = min(len(left), len(right))
    dot = 0.0
    norm_left = 0.0
    norm_right = 0.0
    for index in range(limit):
        lv = float(left[index])
        rv = float(right[index])
        dot += lv * rv
        norm_left += lv * lv
        norm_right += rv * rv
    if norm_left <= 0.0 or norm_right <= 0.0:
        return 0.0
    return dot / math.sqrt(norm_left * norm_right)


class KnowledgeBase:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        from app.embeddings import Embedder

        self.embedder = Embedder(settings.embedding_model, settings.embedding_backend)
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
        self._vector_store_state = "initializing"
        self._vector_store_note = "Preparing vector store connection."
        self._vector_store_attempts = 0
        self._seeded_candidates = 0
        self._seeded_jobs = 0

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
        self._vector_store_state = "fallback"
        self._vector_store_note = f"Endee unavailable; using in-memory vector store. Error: {exc}"

    def _update_vector_store_state(self, state: str, note: str) -> None:
        self._vector_store_state = state
        self._vector_store_note = note

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
            raise

    def _wait_for_endee_index(self) -> None:
        timeout = max(0.0, float(self.settings.endee_bootstrap_timeout_seconds))
        interval = max(0.1, float(self.settings.endee_bootstrap_interval_seconds))
        deadline = time.monotonic() + timeout
        attempts = 0

        while True:
            attempts += 1
            self._vector_store_attempts = attempts
            try:
                self.ensure_index()
                self._update_vector_store_state(
                    "connected",
                    f"Connected to Endee at {self.settings.endee_base_url}.",
                )
                return
            except Exception as exc:
                message = str(exc).lower()
                if "already exists" in message or "exists" in message:
                    self._update_vector_store_state(
                        "connected",
                        f"Endee index '{self.settings.endee_index_name}' is ready.",
                    )
                    return
                if time.monotonic() >= deadline:
                    raise exc
                logger.warning(
                    "Endee not ready yet (attempt %s). Retrying in %ss.",
                    attempts,
                    interval,
                )
                time.sleep(interval)

    def _reindex_materialized_corpus(self) -> tuple[int, int]:
        candidate_count = 0
        job_count = 0
        if not self._candidates and not self._jobs and self.settings.seed_sample_data:
            return self.seed_sample_corpus()

        for candidate in list(self._candidates.values()):
            candidate_count += int(self.upsert_candidate(asdict(candidate)).get("chunks_indexed") or 0)
        for job in list(self._jobs.values()):
            job_count += int(self.upsert_job(asdict(job)).get("chunks_indexed") or 0)
        return candidate_count, job_count

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
            if self.vector_store_backend == "endee":
                try:
                    self._wait_for_endee_index()
                except Exception as exc:
                    self._fallback_to_memory(exc)
                    self.ensure_index()
            else:
                self.ensure_index()
                self._update_vector_store_state("local", "Running on the in-memory vector store.")
            if self.settings.seed_sample_data:
                candidate_count, job_count = self.seed_sample_corpus()
            else:
                candidate_count, job_count = 0, 0
            if self.vector_store_backend == "memory":
                self._update_vector_store_state("local", "Running on the in-memory vector store.")
            self._vector_store_attempts = max(self._vector_store_attempts, 1)
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

    def reconnect_vector_store(self) -> dict[str, Any]:
        self._vector_store = select_vector_store(
            backend=self.settings.vector_store_backend,
            endee_base_url=self.settings.endee_base_url,
            endee_auth_token=self.settings.endee_auth_token,
        )
        self._index = None
        self._bootstrapped = False
        self._bootstrap_error = None
        self._vector_store_attempts = 0
        self._update_vector_store_state("reconnecting", "Reconnecting to the configured vector store.")

        try:
            if self.vector_store_backend == "endee":
                try:
                    self._wait_for_endee_index()
                except Exception as exc:
                    self._fallback_to_memory(exc)
                    self.ensure_index()
            else:
                self.ensure_index()
                self._update_vector_store_state("local", "Running on the in-memory vector store.")

            if self._candidates or self._jobs:
                self._reindex_materialized_corpus()
            elif self.settings.seed_sample_data:
                self.seed_sample_corpus()

            self._vector_store_attempts = max(self._vector_store_attempts, 1)
            self._bootstrapped = True
            self._bootstrap_error = None
            self._last_bootstrap_at = time.time()
            self._seeded_candidates = len(self._candidates)
            self._seeded_jobs = len(self._jobs)
        except Exception as exc:
            self._bootstrap_error = str(exc)
            self._update_vector_store_state("fallback", f"Reconnect failed: {exc}")

        return self.status()

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
            "vector_store_state": self._vector_store_state,
            "vector_store_note": self._vector_store_note,
            "vector_store_attempts": self._vector_store_attempts,
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

    def document_summary(self, *, candidate: dict[str, Any]) -> dict[str, Any]:
        candidate_model = self._candidate_to_profile(candidate)
        skills = dedupe_preserve_order(candidate_model.skills)
        highlights = dedupe_preserve_order(
            [
                candidate_model.headline,
                candidate_model.location,
                *skills[:4],
                *candidate_model.projects[:2],
                candidate_model.summary,
                candidate_model.source,
            ]
        )

        focus = candidate_model.target_role or candidate_model.headline or "the available document"
        summary_parts = [
            f"{candidate_model.name} is a {candidate_model.years_experience:g}-year profile based in {candidate_model.location}.",
            f"It is most aligned with {focus}.",
        ]

        if skills:
            summary_parts.append(f"Core skills include {', '.join(skills[:5])}.")
        if candidate_model.summary:
            summary_parts.append(candidate_model.summary)
        if candidate_model.projects:
            summary_parts.append(f"Highlighted projects: {', '.join(candidate_model.projects[:3])}.")
        if candidate_model.resume_text:
            summary_parts.append(f"Excerpt: {truncate(candidate_model.resume_text, 220)}")

        return {
            "candidate": asdict(candidate_model),
            "summary": " ".join(summary_parts),
            "highlights": highlights,
            "raw": {
                "skill_count": len(skills),
                "project_count": len(candidate_model.projects),
                "resume_length": len(candidate_model.resume_text),
            },
        }

    def compare_candidates(self, *, candidate_a: dict[str, Any], candidate_b: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
        candidate_model_a = self._candidate_to_profile(candidate_a)
        candidate_model_b = self._candidate_to_profile(candidate_b)
        job_model = self._job_to_role(job)

        job_text = " ".join(
            [
                job_model.title,
                job_model.department,
                job_model.description,
                " ".join(job_model.must_have_skills),
                " ".join(job_model.nice_to_have_skills),
                " ".join(job_model.interview_focus),
            ]
        ).strip()
        candidate_text_a = " ".join(
            [
                candidate_model_a.name,
                candidate_model_a.headline,
                candidate_model_a.target_role,
                " ".join(candidate_model_a.skills),
                candidate_model_a.summary,
                " ".join(candidate_model_a.projects),
                candidate_model_a.resume_text,
            ]
        ).strip()
        candidate_text_b = " ".join(
            [
                candidate_model_b.name,
                candidate_model_b.headline,
                candidate_model_b.target_role,
                " ".join(candidate_model_b.skills),
                candidate_model_b.summary,
                " ".join(candidate_model_b.projects),
                candidate_model_b.resume_text,
            ]
        ).strip()

        semantic_a = _cosine_similarity(self.embedder.embed(candidate_text_a), self.embedder.embed(job_text))
        semantic_b = _cosine_similarity(self.embedder.embed(candidate_text_b), self.embedder.embed(job_text))

        breakdown_a = build_rank_breakdown(candidate_model_a, job_model, semantic_score=semantic_a)
        breakdown_b = build_rank_breakdown(candidate_model_b, job_model, semantic_score=semantic_b)

        shared_skills = dedupe_preserve_order(skill_overlap(candidate_model_a.skills, candidate_model_b.skills))
        unique_skills_a = dedupe_preserve_order(missing_skills(candidate_model_b.skills, candidate_model_a.skills))
        unique_skills_b = dedupe_preserve_order(missing_skills(candidate_model_a.skills, candidate_model_b.skills))

        score_a = breakdown_a["overall_score"]
        score_b = breakdown_b["overall_score"]
        score_delta = round(score_a - score_b, 2)
        abs_delta = abs(score_delta)

        if abs_delta < 5:
            winner = "tie"
            recommendation = (
                f"Both candidates are close for {job_model.title}. "
                f"Use the final interview to separate them on {job_model.interview_focus[0] if job_model.interview_focus else 'role-specific execution'}."
            )
            summary = (
                f"{candidate_model_a.name} and {candidate_model_b.name} are effectively tied for {job_model.title}. "
                f"The decision comes down to the quality of their interview signals and how strongly they address the job's top gaps."
            )
        else:
            if score_a > score_b:
                winner = candidate_model_a.id
                recommendation = (
                    f"Shortlist {candidate_model_a.name} for {job_model.title}; the overall fit is stronger by {abs_delta:.1f} points."
                )
                summary = (
                    f"{candidate_model_a.name} is the stronger match for {job_model.title}. "
                    f"They lead on semantic fit, skills coverage, or experience relative to the role."
                )
            else:
                winner = candidate_model_b.id
                recommendation = (
                    f"Shortlist {candidate_model_b.name} for {job_model.title}; the overall fit is stronger by {abs_delta:.1f} points."
                )
                summary = (
                    f"{candidate_model_b.name} is the stronger match for {job_model.title}. "
                    f"They lead on semantic fit, skills coverage, or experience relative to the role."
                )

        strengths_a = dedupe_preserve_order(
            [
                f"Overall score of {score_a:.1f}/100.",
                f"Semantic alignment score of {breakdown_a['semantic_score']:.1f}/100.",
                f"Matches: {', '.join(skill_overlap(candidate_model_a.skills, job_model.must_have_skills)[:4])}"
                if skill_overlap(candidate_model_a.skills, job_model.must_have_skills)
                else "",
            ]
        )
        strengths_b = dedupe_preserve_order(
            [
                f"Overall score of {score_b:.1f}/100.",
                f"Semantic alignment score of {breakdown_b['semantic_score']:.1f}/100.",
                f"Matches: {', '.join(skill_overlap(candidate_model_b.skills, job_model.must_have_skills)[:4])}"
                if skill_overlap(candidate_model_b.skills, job_model.must_have_skills)
                else "",
            ]
        )

        concerns_a = dedupe_preserve_order(
            [
                f"Missing skills: {', '.join(breakdown_a['gaps'][:4])}" if breakdown_a["gaps"] else "",
                f"Experience is below the target of {job_model.min_years_experience:g} years."
                if breakdown_a["experience_score"] < 88
                else "",
                "Semantic fit is only moderate." if breakdown_a["semantic_score"] < 65 else "",
            ]
        )
        concerns_b = dedupe_preserve_order(
            [
                f"Missing skills: {', '.join(breakdown_b['gaps'][:4])}" if breakdown_b["gaps"] else "",
                f"Experience is below the target of {job_model.min_years_experience:g} years."
                if breakdown_b["experience_score"] < 88
                else "",
                "Semantic fit is only moderate." if breakdown_b["semantic_score"] < 65 else "",
            ]
        )

        candidate_snapshot_a = {
            "candidate_id": candidate_model_a.id,
            "name": candidate_model_a.name,
            "headline": candidate_model_a.headline,
            "target_role": candidate_model_a.target_role,
            "years_experience": candidate_model_a.years_experience,
            "location": candidate_model_a.location,
            "skills": list(candidate_model_a.skills),
            "resume_text": candidate_model_a.resume_text,
            "source": candidate_model_a.source,
            "stage": candidate_model_a.stage,
        }
        candidate_snapshot_b = {
            "candidate_id": candidate_model_b.id,
            "name": candidate_model_b.name,
            "headline": candidate_model_b.headline,
            "target_role": candidate_model_b.target_role,
            "years_experience": candidate_model_b.years_experience,
            "location": candidate_model_b.location,
            "skills": list(candidate_model_b.skills),
            "resume_text": candidate_model_b.resume_text,
            "source": candidate_model_b.source,
            "stage": candidate_model_b.stage,
        }
        job_snapshot = {
            "job_id": job_model.id,
            "title": job_model.title,
            "description": job_model.description,
            "department": job_model.department,
            "location": job_model.location,
            "min_years_experience": job_model.min_years_experience,
            "must_have_skills": list(job_model.must_have_skills),
            "nice_to_have_skills": list(job_model.nice_to_have_skills),
            "interview_focus": list(job_model.interview_focus),
        }

        return {
            "candidate_a": candidate_snapshot_a,
            "candidate_b": candidate_snapshot_b,
            "job": job_snapshot,
            "summary": summary,
            "recommendation": recommendation,
            "winner": winner,
            "score_a": score_a,
            "score_b": score_b,
            "score_delta": score_delta,
            "semantic_a": breakdown_a["semantic_score"],
            "semantic_b": breakdown_b["semantic_score"],
            "shared_skills": shared_skills,
            "unique_skills_a": unique_skills_a,
            "unique_skills_b": unique_skills_b,
            "strengths_a": strengths_a,
            "strengths_b": strengths_b,
            "concerns_a": concerns_a,
            "concerns_b": concerns_b,
            "score_breakdown_a": breakdown_a,
            "score_breakdown_b": breakdown_b,
            "raw": {
                "job_text_length": len(job_text),
                "candidate_a_text_length": len(candidate_text_a),
                "candidate_b_text_length": len(candidate_text_b),
            },
        }
