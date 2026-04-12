from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.rag import tokenize, truncate


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
    return ordered


def _normalize_skill(skill: str) -> str:
    alias_map = {
        "js": "javascript",
        "ts": "typescript",
        "ml": "machine learning",
        "ai": "artificial intelligence",
        "llm": "large language models",
        "nlp": "natural language processing",
        "cv": "computer vision",
        "ci/cd": "ci cd",
    }
    cleaned = " ".join(tokenize(skill))
    if not cleaned:
        return skill.strip().lower()
    return alias_map.get(cleaned, cleaned)


def normalize_skills(skills: Iterable[str]) -> list[str]:
    return dedupe_preserve_order(_normalize_skill(skill) for skill in skills)


def _contains_skill(text: str, skill: str) -> bool:
    normalized = _normalize_skill(skill)
    if not normalized:
        return False
    text_tokens = set(tokenize(text))
    skill_tokens = set(tokenize(normalized))
    return bool(skill_tokens and skill_tokens.issubset(text_tokens))


@dataclass(frozen=True)
class CandidateProfile:
    id: str
    name: str
    headline: str
    years_experience: float
    location: str
    target_role: str
    skills: tuple[str, ...]
    resume_text: str
    source: str
    stage: str = "screening"
    summary: str = ""
    projects: tuple[str, ...] = ()


@dataclass(frozen=True)
class JobRole:
    id: str
    title: str
    department: str
    location: str
    min_years_experience: float
    must_have_skills: tuple[str, ...]
    nice_to_have_skills: tuple[str, ...]
    description: str
    interview_focus: tuple[str, ...] = ()
    source: str = ""


def skill_overlap(candidate_skills: Iterable[str], job_skills: Iterable[str]) -> list[str]:
    candidate = {skill.lower() for skill in normalize_skills(candidate_skills)}
    return [skill for skill in normalize_skills(job_skills) if skill.lower() in candidate]


def missing_skills(candidate_skills: Iterable[str], job_skills: Iterable[str]) -> list[str]:
    candidate = {skill.lower() for skill in normalize_skills(candidate_skills)}
    return [skill for skill in normalize_skills(job_skills) if skill.lower() not in candidate]


def score_experience(candidate_years: float, min_years: float) -> float:
    if min_years <= 0:
        return 75.0 if candidate_years > 0 else 45.0
    if candidate_years >= min_years:
        extra_years = candidate_years - min_years
        return clamp(88.0 + min(extra_years * 2.5, 12.0))
    ratio = candidate_years / min_years
    return clamp(ratio * 100.0)


def score_location(candidate_location: str, job_location: str) -> float:
    candidate = candidate_location.strip().lower()
    job = job_location.strip().lower()
    if not job or job == "all":
        return 85.0
    if "remote" in candidate or "remote" in job:
        return 100.0
    if candidate == job:
        return 100.0
    if candidate in job or job in candidate:
        return 82.0
    return 60.0


def score_semantics(semantic_score: float) -> float:
    if semantic_score <= 1.0:
        return clamp(semantic_score * 100.0)
    return clamp(semantic_score)


def score_skill_match(candidate: CandidateProfile, job: JobRole) -> tuple[float, list[str], list[str]]:
    must_have = normalize_skills(job.must_have_skills)
    nice_to_have = normalize_skills(job.nice_to_have_skills)
    candidate_skills = normalize_skills(candidate.skills)

    must_overlap = skill_overlap(candidate_skills, must_have)
    nice_overlap = skill_overlap(candidate_skills, nice_to_have)
    text_hits = [skill for skill in must_have if _contains_skill(candidate.resume_text, skill)]

    must_ratio = len(set(must_overlap) | set(text_hits)) / len(must_have) if must_have else 0.5
    nice_ratio = len(nice_overlap) / len(nice_to_have) if nice_to_have else 0.5
    score = 100.0 * clamp(0.72 * must_ratio + 0.18 * nice_ratio + 0.10 * min(len(candidate_skills) / 10.0, 1.0))

    reasons: list[str] = []
    if must_overlap:
        reasons.append(f"Must-have skills matched: {', '.join(must_overlap[:4])}.")
    if nice_overlap:
        reasons.append(f"Nice-to-have skills matched: {', '.join(nice_overlap[:4])}.")
    if text_hits and set(text_hits) - set(must_overlap):
        reasons.append(f"Resume text also mentions: {', '.join(sorted(set(text_hits) - set(must_overlap))[:3])}.")

    gaps = missing_skills(candidate_skills, must_have)
    if gaps:
        reasons.append(f"Missing skills to probe: {', '.join(gaps[:4])}.")

    return clamp(score), reasons, gaps


def build_rank_breakdown(
    candidate: CandidateProfile,
    job: JobRole,
    *,
    semantic_score: float,
) -> dict[str, Any]:
    skill_score, skill_reasons, gaps = score_skill_match(candidate, job)
    experience_score = score_experience(candidate.years_experience, job.min_years_experience)
    location_score = score_location(candidate.location, job.location)
    semantic_percent = score_semantics(semantic_score)

    overall = clamp(
        0.42 * semantic_percent
        + 0.30 * skill_score
        + 0.18 * experience_score
        + 0.10 * location_score
    )

    reasons: list[str] = []
    if semantic_percent >= 85:
        reasons.append("Semantic match is very strong against the job description.")
    elif semantic_percent >= 65:
        reasons.append("Semantic match is strong and relevant to the role.")
    else:
        reasons.append("Semantic similarity is moderate, so the role fit depends on structured skills.")

    if experience_score >= 88:
        reasons.append(f"Meets or exceeds the minimum experience of {job.min_years_experience:g} years.")
    else:
        reasons.append(f"Candidate is below the minimum experience target of {job.min_years_experience:g} years.")

    if location_score >= 95:
        reasons.append(f"Location fit is favorable for {job.location}.")

    reasons.extend(skill_reasons[:3])

    return {
        "semantic_score": round(semantic_percent, 2),
        "skill_score": round(skill_score, 2),
        "experience_score": round(experience_score, 2),
        "location_score": round(location_score, 2),
        "overall_score": round(overall, 2),
        "reasons": dedupe_preserve_order(reasons),
        "gaps": gaps,
    }


def communication_score(answer_text: str) -> float:
    words = tokenize(answer_text)
    if not words:
        return 0.0

    length_bonus = min(len(words) / 35.0, 1.0) * 40.0
    structure_bonus = 0.0
    lower = answer_text.lower()
    if any(marker in lower for marker in ("first", "second", "third", "for example", "example", "because")):
        structure_bonus += 20.0
    if answer_text.strip().endswith((".", "!", "?")):
        structure_bonus += 10.0
    if len(words) >= 18:
        structure_bonus += 15.0
    if len(words) >= 45:
        structure_bonus += 15.0
    return clamp(length_bonus + structure_bonus)


def confidence_score(answer_text: str) -> float:
    words = tokenize(answer_text)
    if not words:
        return 0.0

    hedges = ["maybe", "perhaps", "probably", "guess", "sorta", "kind", "think"]
    hedge_hits = sum(answer_text.lower().count(word) for word in hedges)
    directness = 70.0 + min(len(words), 60) * 0.5
    return clamp(directness - hedge_hits * 6.0)


def fraud_assessment(telemetry: Any) -> dict[str, Any]:
    if isinstance(telemetry, dict):
        def read(key: str, default: Any = 0) -> Any:
            return telemetry.get(key, default)
    else:
        def read(key: str, default: Any = 0) -> Any:
            return getattr(telemetry, key, default)

    tab_switches = int(read("tab_switches", 0) or 0)
    copy_events = int(read("copy_events", 0) or 0)
    paste_events = int(read("paste_events", 0) or 0)
    blur_events = int(read("blur_events", 0) or 0)
    idle_seconds = float(read("idle_seconds", 0.0) or 0.0)
    multiple_faces = bool(read("multiple_faces_detected", False))

    risk = 0.0
    flags: list[str] = []

    if tab_switches:
        risk += min(tab_switches * 12.0, 36.0)
        flags.append(f"{tab_switches} tab switch{'' if tab_switches == 1 else 'es'} during the interview.")
    if copy_events:
        risk += min(copy_events * 8.0, 24.0)
        flags.append(f"{copy_events} copy event{'' if copy_events == 1 else 's'} detected.")
    if paste_events:
        risk += min(paste_events * 10.0, 30.0)
        flags.append(f"{paste_events} paste event{'' if paste_events == 1 else 's'} detected.")
    if blur_events:
        risk += min(blur_events * 7.0, 21.0)
        flags.append(f"{blur_events} focus loss event{'' if blur_events == 1 else 's'} detected.")
    if idle_seconds > 90:
        risk += min((idle_seconds - 90) * 0.15, 20.0)
        flags.append("Long idle periods may indicate task sharing or outside assistance.")
    if multiple_faces:
        risk += 30.0
        flags.append("Multiple faces detected by camera review.")

    return {
        "fraud_score": round(clamp(risk), 2),
        "trust_score": round(clamp(100.0 - risk), 2),
        "flags": dedupe_preserve_order(flags),
    }


def generate_interview_questions(candidate: CandidateProfile, job: JobRole, count: int = 5) -> list[dict[str, str]]:
    must_have = normalize_skills(job.must_have_skills)
    candidate_skills = normalize_skills(candidate.skills)
    gaps = missing_skills(candidate_skills, must_have)
    interview_focus = [focus for focus in job.interview_focus if focus.strip()]

    questions: list[dict[str, str]] = []
    if gaps:
        gap = gaps[0]
        questions.append(
            {
                "question": f"Walk me through how you'd get productive with {gap} in your first two weeks.",
                "focus": f"Ramp-up on {gap}",
                "expected_signal": f"A concrete learning plan for {gap} and the related workflow.",
                "difficulty": "warm-up",
            }
        )

    if must_have:
        primary = must_have[0]
        questions.append(
            {
                "question": f"Describe a production project where you used {primary}. What trade-offs did you make?",
                "focus": primary,
                "expected_signal": f"Real production experience with {primary} and measurable outcomes.",
                "difficulty": "core",
            }
        )

    if interview_focus:
        focus = interview_focus[0]
        questions.append(
            {
                "question": f"This role emphasizes {focus}. How do you balance speed, reliability, and maintainability there?",
                "focus": focus,
                "expected_signal": f"Structured reasoning around {focus} with practical trade-offs.",
                "difficulty": "core",
            }
        )
    else:
        questions.append(
            {
                "question": f"What metrics would you use to prove success in a {job.title} role?",
                "focus": job.title,
                "expected_signal": "Evidence of product thinking and outcome-focused measurement.",
                "difficulty": "core",
            }
        )

    project_hint = candidate.projects[0] if candidate.projects else candidate.headline
    questions.append(
        {
            "question": f"Tell me about a project like '{truncate(project_hint, 42)}' and the result you shipped.",
            "focus": "impact",
            "expected_signal": "A crisp example with ownership, metrics, and scope.",
            "difficulty": "behavioral",
        }
    )

    questions.append(
        {
            "question": f"If quality dropped after a launch, how would you investigate before escalating?",
            "focus": "debugging",
            "expected_signal": "Structured debugging and communication under pressure.",
            "difficulty": "advanced",
        }
    )

    return questions[:count]


def evaluate_interview_answers(
    candidate: CandidateProfile,
    job: JobRole,
    answers: Iterable[dict[str, str]],
    telemetry: Any,
) -> dict[str, Any]:
    answer_items = list(answers)
    if not answer_items:
        answer_items = [{"prompt": "", "answer": ""}]

    all_answer_text = " ".join(item.get("answer", "") for item in answer_items)
    technical = 0.0
    communication_values: list[float] = []
    confidence_values: list[float] = []

    for item in answer_items:
        text = item.get("answer", "")
        technical += min(100.0, len(set(tokenize(text)) & set(tokenize(job.description))) * 12.0)
        technical += min(25.0, len(set(tokenize(text)) & set(tokenize(candidate.resume_text))) * 2.0)
        communication_values.append(communication_score(text))
        confidence_values.append(confidence_score(text))

    technical = clamp(technical / max(len(answer_items), 1) + 35.0)
    communication = clamp(sum(communication_values) / max(len(communication_values), 1))
    confidence = clamp(sum(confidence_values) / max(len(confidence_values), 1))
    fraud = fraud_assessment(telemetry)

    overall = clamp(
        0.40 * technical
        + 0.25 * communication
        + 0.15 * confidence
        + 0.20 * fraud["trust_score"]
    )

    reasons = [
        f"Technical answers align with {job.title} expectations." if technical >= 70 else "Technical depth looks partial and could be stronger.",
        "Communication is clear and structured." if communication >= 70 else "Communication could be more concise and concrete.",
        "Confidence reads well." if confidence >= 70 else "Responses include a few hedges or evasive phrases.",
    ]
    if fraud["flags"]:
        reasons.append("Interview telemetry contains suspicious signals.")
    else:
        reasons.append("No major fraud signals were detected.")

    suggestions = [
        "Add a crisp example with a metric, scope, and result.",
        "Name the trade-off you made and why it was the right call.",
    ]
    if fraud["flags"]:
        suggestions.append("Review interview integrity signals before proceeding to the next stage.")

    return {
        "overall_score": round(overall, 2),
        "technical_score": round(technical, 2),
        "communication_score": round(communication, 2),
        "confidence_score": round(confidence, 2),
        "fraud_score": fraud["fraud_score"],
        "fraud_flags": fraud["flags"],
        "reasons": dedupe_preserve_order(reasons),
        "suggestions": dedupe_preserve_order(suggestions),
        "raw": {
            "answer_count": len(answer_items),
            "answer_text_length": len(all_answer_text),
            "trust_score": fraud["trust_score"],
        },
    }


def resume_feedback(candidate: CandidateProfile, job: JobRole) -> dict[str, Any]:
    missing = missing_skills(candidate.skills, job.must_have_skills)
    overlaps = skill_overlap(candidate.skills, job.must_have_skills)
    suggestions = [
        f"Lead with the skills that matter most for this role: {', '.join(overlaps[:4])}." if overlaps else "Bring your most relevant role-specific skills to the top of the resume.",
        "Use metrics to prove impact instead of only listing responsibilities.",
        "Tailor the summary to the job title and mention the production systems you shipped.",
    ]
    if missing:
        suggestions.append(f"Add evidence of {', '.join(missing[:4])} through projects, certifications, or portfolio work.")

    summary = (
        f"{candidate.name} is a {candidate.years_experience:g}-year profile for {job.title}. "
        f"The strongest overlap is {', '.join(overlaps[:3]) if overlaps else 'semantic alignment rather than direct skill overlap'}."
    )

    return {
        "summary": summary,
        "suggestions": dedupe_preserve_order(suggestions),
        "missing_skills": missing,
        "raw": {
            "matched_skills": overlaps,
            "candidate_length": len(candidate.resume_text),
            "job_length": len(job.description),
        },
    }
