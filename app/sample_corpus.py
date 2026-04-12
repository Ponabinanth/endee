from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeedDocument:
    id: str
    title: str
    department: str
    doc_type: str
    audience: str
    source: str
    body: str


SAMPLE_DOCUMENTS: list[SeedDocument] = [
    SeedDocument(
        id="engineering-release-process",
        title="Engineering Release Process",
        department="engineering",
        doc_type="runbook",
        audience="internal",
        source="knowledge-base/engineering/release-process.md",
        body="""
Release Readiness

Every production release begins with a short readiness review. The owner verifies unit tests, integration tests, security scans, and migration plans. If the change touches user-facing flows, the team schedules a canary on 10 percent of traffic for at least 30 minutes. The release captain watches error rates, latency, and critical funnel events before approving full rollout.

Rollback is part of the release, not an afterthought. Before the deployment window, the engineer must write the rollback command, confirm that the previous artifact is available, and rehearse the rollback in staging. If a release causes a critical alert, stop the rollout, page the on-call engineer, and post a status update within 15 minutes.

Postmortems are blameless. The follow-up should explain what happened, how customer impact was minimized, which alert should have fired sooner, and which checklist item needs to change. The goal is fewer surprises in the next release, not blame.
""".strip(),
    ),
    SeedDocument(
        id="support-escalation-playbook",
        title="Support Escalation Playbook",
        department="support",
        doc_type="playbook",
        audience="internal",
        source="knowledge-base/support/escalation-playbook.md",
        body="""
Ticket Triage

Support agents triage new tickets in the order they arrive. Sev1 issues get a first response within 10 minutes during business hours, while Sev2 issues receive a response within one hour. Each ticket should include the customer name, product area, severity, and a short summary of the issue.

Escalate to engineering only after the support agent has reproduced the problem, collected logs, and documented the exact user impact. For outages or data loss, page the on-call engineer and update the incident channel immediately. The support lead owns communication with the customer, while engineering owns the technical fix.

Use calm, specific language. If the customer is frustrated, acknowledge the impact first, explain the next step, and give an ETA you can defend. When the incident is resolved, close the loop with a short summary, the root cause, and any workaround that should stay in the knowledge base.
""".strip(),
    ),
    SeedDocument(
        id="product-faq",
        title="Product FAQ",
        department="product",
        doc_type="faq",
        audience="customer",
        source="knowledge-base/product/customer-faq.md",
        body="""
What does the product do?

The platform helps teams search internal knowledge, retrieve relevant passages, and draft grounded answers with citations. It is designed for support centers, operations teams, and product organizations that need accurate answers from their own documents instead of a generic web search result.

How do integrations work?

The fastest path is to connect your existing docs, then ingest markdown, text, or exported help-center content. Teams usually start with a small corpus, validate retrieval quality, and then expand to additional sources such as onboarding guides, policy documents, and runbooks. Authentication and access controls can be layered on top of the retrieval layer.

What about data security?

Customer content is stored in your own Endee instance, which means retrieval stays under your control. The app can be run locally or in Docker, and the retrieval layer supports metadata filters so sensitive content can be separated by department, audience, or document type.
""".strip(),
    ),
    SeedDocument(
        id="sales-objection-handling",
        title="Sales Objection Handling",
        department="sales",
        doc_type="guide",
        audience="internal",
        source="knowledge-base/sales/objection-handling.md",
        body="""
Positioning

When a prospect says the tool is "just another chatbot," respond by shifting the conversation to retrieval quality, citations, and workflow fit. The value is not random text generation. The value is giving people the exact passage they need, ranked by semantic relevance, with filterable metadata and a clean path to a grounded answer.

Price objections are usually implementation objections in disguise. Explain that the first demo can be a small pilot: one department, a handful of documents, and a single measurable success metric such as time saved per ticket or faster onboarding for new hires. Once the pilot shows value, the customer can expand to more content and more workflows.

Security objections should be answered with concrete controls. Talk about private deployment, metadata filtering, and the ability to keep the data in the customer-controlled Endee instance. If procurement wants a technical summary, share the architecture and the exact data flow from ingestion to retrieval to answer synthesis.
""".strip(),
    ),
    SeedDocument(
        id="people-ops-policy",
        title="People Ops Policy",
        department="people",
        doc_type="policy",
        audience="internal",
        source="knowledge-base/people/people-ops-policy.md",
        body="""
Working Model

Employees may work remotely unless their role requires a physical presence for customer events, hardware handling, or security-sensitive operations. Core collaboration hours are 10:00 to 15:00 local time, and teams should document when they will be offline for travel or personal appointments.

Time Off

Vacation requests should be submitted in advance so managers can plan coverage. If a team member is unexpectedly unavailable, the manager should confirm whether deadlines need to move and whether another owner can cover critical work. For leave longer than three days, a short handoff note is required so no one has to guess where the work stands.

Security and Onboarding

New hires receive access in stages. Start with the tools they need for their role, then add sensitive systems after training is complete. Passwords should be managed through the company-approved password manager, and confidential documents should only be shared with the audience they are intended for.
""".strip(),
    ),
]


def filter_catalog() -> dict[str, list[str]]:
    return {
        "departments": sorted({doc.department for doc in SAMPLE_DOCUMENTS}),
        "doc_types": sorted({doc.doc_type for doc in SAMPLE_DOCUMENTS}),
        "audiences": sorted({doc.audience for doc in SAMPLE_DOCUMENTS}),
    }


def example_questions() -> list[str]:
    return [
        "What is the rollback process for a production release?",
        "How should support handle a Sev1 incident?",
        "How do I explain the product's security model to a customer?",
        "What is the remote work policy?",
        "What should I say when a prospect worries about price?",
    ]

