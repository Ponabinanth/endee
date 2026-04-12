from __future__ import annotations

from app.filters import dedupe_sorted
from app.scoring import CandidateProfile, JobRole


SAMPLE_CANDIDATES: list[CandidateProfile] = [
    CandidateProfile(
        id="doc-cloud-sec-2024",
        name="Enterprise Cloud Security Whitepaper 2024",
        headline="Comprehensive guide on Zero Trust Architecture and IAM best practices",
        years_experience=2.0,
        location="Global/Remote",
        target_role="Security Policy",
        skills=("Zero Trust", "IAM", "Encryption", "SOC2", "OAuth2", "Cloud Governance", "Firewalls"),
        resume_text="""
This document outlines the migration path for legacy enterprises into Zero Trust environments. 
It covers identity-driven security models, granular IAM permissions, and the importance of hardware-based MFA.
Key sections include data encryption at rest using AES-256 and transit-layer security via TLS 1.3.
Compliance mapping includes SOC2 Type II and GDPR data sovereignty requirements for multi-region cloud deployments.
""".strip(),
        source="internal/whitepapers/cloud-security-2024.md",
        summary="Foundational security document for infrastructure teams.",
        projects=("Zero Trust Roadmap", "IAM Audit Log Specification"),
    ),
    CandidateProfile(
        id="doc-api-design-standard",
        name="Global API Design & Consistency Standard",
        headline="Internal engineering specification for REST and GraphQL interfaces",
        years_experience=1.1,
        location="Internal Knowledge Base",
        target_role="API Standards",
        skills=("REST", "GraphQL", "Versioning", "Rate Limiting", "Swagger", "Protobuf", "Caching"),
        resume_text="""
Specifications for all internal and external facing services. 
Standardized response codes (RFC 7231), header requirements, and semantic versioning (SemVer) are mandatory.
Pagination must be implemented via cursor-based methods for large datasets to optimize database performance.
Rate limiting policies are defined per tier: Bronze, Silver, and Gold, enforced via Redis-backed middleware.
""".strip(),
        source="engineering/standards/api-design.md",
        summary="Mandatory reading for all backend engineers and technical product managers.",
        projects=("RESTful Core Library", "GraphQL Federation Gateway"),
    ),
    CandidateProfile(
        id="doc-data-privacy-gdpr",
        name="GDPR Compliance & Data Residency Protocol",
        headline="Operational manual for PII handling and data subject access requests",
        years_experience=6.0,
        location="Legal/Compliance",
        target_role="Legal Compliance",
        skills=("GDPR", "PII", "Data Anonymization", "DSAR", "Privacy Shield", "Legal", "Compliance"),
        resume_text="""
Detailed procedures for handling Personal Identifiable Information (PII) within the platform.
Data must be anonymized or pseudonymized before entering the analytics pipeline. 
Data Subject Access Requests (DSAR) must be fulfilled within 30 days.
Includes protocols for data residency in the EU (Ireland/Frankfurt) to comply with Schrems II rulings.
""".strip(),
        source="legal/compliance/gdpr-protocol.md",
        summary="Critical legal reference for data engineering and customer support.",
        projects=("PII Detection Service", "Automated DSAR Workflow"),
    ),
    CandidateProfile(
        id="doc-distributed-sys-patterns",
        name="Distributed Systems: Resilience & Scaling Patterns",
        headline="Architecture guide for microservices, circuit breakers, and event sourcing",
        years_experience=5.5,
        location="Architecture Group",
        target_role="System Architecture",
        skills=("Microservices", "Circuit Breakers", "Kafka", "Event Sourcing", "Scalability", "Kubernetes"),
        resume_text="""
Guidelines for building resilient distributed systems. 
Implementation of the Circuit Breaker pattern is required to prevent cascading failures in the service mesh.
Event sourcing via Apache Kafka is recommended for high-throughput transactional consistency.
Services must be stateless and deployable as OCI-compliant containers on Kubernetes.
""".strip(),
        source="engineering/architecture/distributed-patterns.md",
        summary="Best practices for platform scalability and reliability.",
        projects=("Resilience Mesh", "Transactional Event Bus"),
    ),
]


SAMPLE_JOBS: list[JobRole] = [
    JobRole(
        id="query-security-audit",
        title="Compliance & Security Auditor",
        department="engineering",
        location="Remote",
        min_years_experience=4,
        must_have_skills=("Zero Trust", "IAM", "GDPR", "SOC2"),
        nice_to_have_skills=("Encryption", "PII", "Audit Logs"),
        description="""
Searching for documents related to infrastructure security, cloud compliance, and privacy regulations.
The ideal documents should provide actionable steps for SOC2 auditing and PII protection within multi-cloud environments.
""".strip(),
        interview_focus=("audit readiness", "policy enforcement", "data sovereignty"),
        source="queries/security-audit-brief.md",
    ),
    JobRole(
        id="query-platform-arch",
        title="Lead Platform Architect",
        department="engineering",
        location="Remote",
        min_years_experience=5,
        must_have_skills=("Microservices", "API Design", "Kubernetes", "Scalability"),
        nice_to_have_skills=("Kafka", "Event Sourcing", "GraphQL", "Caching"),
        description="""
Retrieving technical specifications for distributed systems design, API consistency, and infrastructure scaling.
Need documentation on circuit breakers, service mesh implementation, and REST/GraphQL interface standards.
""".strip(),
        interview_focus=("system resilience", "interface contracts", "scaling bottlenecks"),
        source="queries/platform-architecture-brief.md",
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
        "How should we handle PII and GDPR compliance in our database?",
        "What are the mandatory API design standards for REST services?",
        "Summarize the best practices for Zero Trust cloud security.",
        "Find documents related to microservices scalability and Kafka.",
        "Which compliance documents discuss SOC2 and data sovereignty?",
    ]
