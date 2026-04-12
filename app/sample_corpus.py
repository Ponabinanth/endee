from __future__ import annotations

from app.filters import dedupe_sorted
from app.scoring import CandidateProfile, JobRole


SAMPLE_CANDIDATES: list[CandidateProfile] = [
    CandidateProfile(
        id="candidate-priya-shah",
        name="Priya Shah",
        headline="Senior AI Engineer focused on semantic search and LLM systems",
        years_experience=6.5,
        location="Bengaluru, India",
        target_role="AI Engineer",
        skills=("Python", "FastAPI", "embeddings", "vector databases", "PyTorch", "Docker", "AWS", "LLMs"),
        resume_text="""
Senior AI engineer who built a semantic search stack for an internal support knowledge base.
Delivered resume matching experiments using embeddings, vector similarity, and evaluation loops.
Shipped production services in Python and FastAPI, containerized workloads with Docker, and deployed on AWS.
Led retrieval experiments, prompt tuning, and search quality reviews with product and recruiting teams.
""".strip(),
        source="sample-resumes/priya-shah.txt",
        summary="Strong at semantic search, retrieval workflows, and production API delivery.",
        projects=("Semantic Search Engine", "Resume Matcher", "LLM Evaluation Dashboard"),
    ),
    CandidateProfile(
        id="candidate-daniel-kim",
        name="Daniel Kim",
        headline="Backend engineer with strong API, database, and platform skills",
        years_experience=4.2,
        location="Singapore",
        target_role="Backend Engineer",
        skills=("Python", "PostgreSQL", "Redis", "FastAPI", "Docker", "System design", "Testing"),
        resume_text="""
Backend engineer who owns REST APIs, data models, and observability for product teams.
Built performant services in Python, tuned PostgreSQL queries, and implemented caching with Redis.
Comfortable with test-driven development, service contracts, and deployment pipelines.
""".strip(),
        source="sample-resumes/daniel-kim.txt",
        summary="Great fit for backend-heavy roles that need reliability and clean APIs.",
        projects=("Internal API Platform", "Caching Layer", "Release Automation"),
    ),
    CandidateProfile(
        id="candidate-aisha-rahman",
        name="Aisha Rahman",
        headline="Data scientist focused on experimentation and decision support",
        years_experience=5.1,
        location="Remote",
        target_role="Data Scientist",
        skills=("Python", "SQL", "machine learning", "A/B testing", "XGBoost", "statistics", "dashboards"),
        resume_text="""
Data scientist who works closely with product and recruiting teams to translate messy data into decisions.
Built candidate funnel dashboards, model scoring experiments, and feature engineering pipelines.
Strong in SQL, experimentation, and communicating findings clearly to non-technical stakeholders.
""".strip(),
        source="sample-resumes/aisha-rahman.txt",
        summary="Balances analytics depth with clear communication and experiment design.",
        projects=("Candidate Funnel Dashboard", "Experimentation Toolkit", "Predictive Scoring Model"),
    ),
    CandidateProfile(
        id="candidate-miguel-torres",
        name="Miguel Torres",
        headline="Full-stack engineer bridging frontends, APIs, and product design",
        years_experience=3.4,
        location="Mexico City",
        target_role="Full Stack Engineer",
        skills=("React", "Next.js", "Node.js", "Python", "REST APIs", "Testing", "UX"),
        resume_text="""
Full-stack engineer who builds product experiences end to end.
Delivered dashboards, form flows, and API integrations with React, Next.js, Node.js, and Python services.
Comfortable collaborating with designers, writing tests, and shipping fast iterations.
""".strip(),
        source="sample-resumes/miguel-torres.txt",
        summary="Flexible builder for product-facing software teams.",
        projects=("Candidate Dashboard", "Interview UI", "Workflow Builder"),
    ),
    CandidateProfile(
        id="candidate-lena-novak",
        name="Lena Novak",
        headline="Applied NLP engineer with strong evaluation and retrieval experience",
        years_experience=7.0,
        location="Berlin, Germany",
        target_role="ML Engineer",
        skills=("Python", "HuggingFace", "transformers", "semantic search", "LLMs", "evaluation", "MLOps"),
        resume_text="""
Applied NLP engineer who built retrieval-augmented assistants, semantic ranking pipelines, and model evaluation loops.
Deep experience with Hugging Face transformers, prompt design, and search relevance analysis.
Partnered with recruiters to explain ranking decisions and improve candidate matching quality.
""".strip(),
        source="sample-resumes/lena-novak.txt",
        summary="Ideal for retrieval-heavy ML roles and explainable AI systems.",
        projects=("RAG Interview Copilot", "Semantic Ranker", "Evaluation Harness"),
    ),
    CandidateProfile(
        id="candidate-jordan-lee",
        name="Jordan Lee",
        headline="Quality and fraud analytics engineer with anomaly detection experience",
        years_experience=4.8,
        location="Austin, USA",
        target_role="QA / Fraud Analytics",
        skills=("Python", "Playwright", "Selenium", "anomaly detection", "monitoring", "dashboards", "fraud analytics"),
        resume_text="""
Quality engineer and fraud analytics specialist who builds safe assessment flows.
Implemented browser behavior tracking, anomaly detection dashboards, and test automation.
Useful for teams that need strong integrity signals in online assessments and interviews.
""".strip(),
        source="sample-resumes/jordan-lee.txt",
        summary="Strong match for fraud detection, QA automation, and assessment integrity.",
        projects=("Assessment Integrity Engine", "Browser Telemetry Monitor", "Automation Suite"),
    ),
]


SAMPLE_JOBS: list[JobRole] = [
    JobRole(
        id="job-senior-ai-engineer",
        title="Senior AI Engineer",
        department="engineering",
        location="Remote",
        min_years_experience=5,
        must_have_skills=("Python", "embeddings", "vector databases", "FastAPI", "LLMs"),
        nice_to_have_skills=("PyTorch", "AWS", "Docker", "evaluation"),
        description="""
Build the ranking and interview intelligence layer for an autonomous hiring platform.
The role needs someone who can design semantic matching systems, create explainable scoring, and ship fast APIs.
Production Python experience, retrieval workflows, and a strong sense for evaluation quality are essential.
""".strip(),
        interview_focus=("retrieval quality", "system design", "evaluation", "explainability"),
        source="jobs/senior-ai-engineer.md",
    ),
    JobRole(
        id="job-backend-platform-engineer",
        title="Backend Platform Engineer",
        department="engineering",
        location="Remote",
        min_years_experience=4,
        must_have_skills=("Python", "FastAPI", "PostgreSQL", "Docker"),
        nice_to_have_skills=("Redis", "testing", "observability", "system design"),
        description="""
Own APIs, data contracts, and deployment quality for the hiring platform.
Candidates should be able to build reliable services, model workflows, and support product teams with low-latency APIs.
""".strip(),
        interview_focus=("API design", "database modeling", "observability", "testing"),
        source="jobs/backend-platform-engineer.md",
    ),
    JobRole(
        id="job-ml-ranking-scientist",
        title="ML Ranking Scientist",
        department="data",
        location="Remote",
        min_years_experience=4,
        must_have_skills=("Python", "machine learning", "statistics", "evaluation"),
        nice_to_have_skills=("A/B testing", "SQL", "experiment design", "dashboards"),
        description="""
Tune the ranking model, explain scores to recruiters, and improve matching quality.
This role blends product analytics, ranking evaluation, and practical ML system thinking.
""".strip(),
        interview_focus=("ranking evaluation", "experiment design", "metrics", "communication"),
        source="jobs/ml-ranking-scientist.md",
    ),
    JobRole(
        id="job-fraud-detection-analyst",
        title="Fraud Detection Analyst",
        department="security",
        location="Hybrid",
        min_years_experience=3,
        must_have_skills=("Python", "monitoring", "anomaly detection", "dashboards"),
        nice_to_have_skills=("Playwright", "Selenium", "fraud analytics", "behavioral analysis"),
        description="""
Monitor interview integrity and surface suspicious assessment patterns.
You will review browser telemetry, copy-paste signals, and camera review flags so the hiring process stays trustworthy.
""".strip(),
        interview_focus=("behavioral signals", "telemetry", "investigation", "reporting"),
        source="jobs/fraud-detection-analyst.md",
    ),
]


def filter_catalog() -> dict[str, list[str]]:
    return {
        "roles": dedupe_sorted(job.title for job in SAMPLE_JOBS),
        "locations": dedupe_sorted(candidate.location for candidate in SAMPLE_CANDIDATES),
        "stages": dedupe_sorted(candidate.stage for candidate in SAMPLE_CANDIDATES),
        "skills": dedupe_sorted(skill for candidate in SAMPLE_CANDIDATES for skill in candidate.skills),
    }


def example_questions() -> list[str]:
    return [
        "Rank these resumes for a senior AI engineer role.",
        "Which candidates have Python, ML, and 2+ years of experience?",
        "Generate interview questions for the best NLP candidate.",
        "Show fraud signals for the current interview session.",
        "What resume improvements would help a backend engineer get shortlisted?",
    ]
