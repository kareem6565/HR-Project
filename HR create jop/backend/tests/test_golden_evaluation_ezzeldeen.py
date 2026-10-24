# ruff: noqa: E501 (CV_TEXT is verbatim resume content with unavoidable long lines)
"""Golden end-to-end evaluation test for Ezzeldeen Saleh's CV.

Runs the REAL HERA pipeline against the exact Ezzeldeen Saleh resume text and a
locked golden Job Profile: (1) candidate profile extraction with the real AI
provider on the CV text, then (2) candidate evaluation with the real AI provider
twice so the evidence semantics genuinely reflect the CV. Every assertion below
the workflow boundary is deterministic - it only depends on persisted rows and
the locked ScoringService rules.

This is intentionally a live-provider test (``soal`` marker): it requires a
real LLM so semantic facts are validated against the actual CV. Run it through
``tools\\run_gemini_tests.ps1`` or ``pytest -m soal`` with SOAL_API_KEY set.

Scoring expectations (weights must_have=3/important=2/nice_to_have=1,
denominator 31):
- 5 matched must_have (Java, Spring Boot, REST APIs, Microservices, PostgreSQL)
- the 2+ years must_have is NOT matched without explicit evidence (missing, or
  partial at most; matched is a grounding defect)
- 5 matched important (Docker, Kafka, Spring Security, SQL, Testing)
- AWS and Kubernetes are missing (they are absent from the CV; anything else
  means the AI invented experience)
- CI/CD may be missing/partial/matched (GitHub Actions is present in the CV)
That evidence can only land the deterministic score on one of six values
(80.645 / 82.258 / 83.871 / 85.484 / 87.097 / 88.710); the primary expected band
is 80.0-82.3 (reference 82.258 with CI/CD partial, 80.645 with CI/CD missing).
"""

import os
import re
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.contracts import (
    normalize_job_profile_requirements,
    requirement_key,
)
from app.ai.providers.factory import get_provider
from app.ai.workflows import (
    CandidateEvaluationWorkflow,
    CandidateProfileExtractionWorkflow,
)
from app.core.config import Settings
from app.models import (
    Candidate,
    CandidateEvaluation,
    CandidateProfile,
    HRDecision,
    Job,
    JobApplication,
    JobProfile,
    MatchEvidence,
    Organization,
    Resume,
    User,
)
from app.services.candidate_pool_service import assign_group
from app.services.scoring_service import ScoringService, build_evidence_by_key

CV_TEXT = """EZZELDEEN SALEH
Backend Engineer  ·  Distributed Systems  ·  Java / Spring Boot / Kafka
Cairo, Egypt  |  01140258638  |  ezzeldeensaat234@gmail.com  |  github.com/Zezoxsaleh  |  linkedin.com/in/ezzeldeensaleh

PROFESSIONAL SUMMARY

Information Systems student at Helwan University with hands-on experience building distributed backend systems.
Delivered a 5-service microservices platform with Kafka event-driven workflows, Stripe payment integration, and JWT-secured APIs — fully containerized via Docker Compose. Built a real-time clickstream pipeline processing thousands of events using Kafka, NiFi, and Spark. Focused on clean architecture, scalable API design, and production-ready deployment.

TECHNICAL SKILLS

Backend: Java · Spring Boot · Spring Security · REST APIs ·
Microservices · JWT · JPA/Hibernate
Data & Streaming: Apache Kafka · Apache Spark · Apache
NiFi · ETL Pipelines · Stream Processing
DevOps: Docker · Docker Compose · Git & GitHub · Linux ·
GitHub Actions
Databases: PostgreSQL · MySQL · SQL Server
Testing: JUnit · Unit & Integration Testing · Postman · Clean
Architecture · SOLID · Agile
Frontend: React · Vite · JavaScript · HTML5/CSS3 · API
Integration

PROJECTS

Food Ordering System — Full-Stack Microservices Platform
Stack: Java · Spring Boot · Apache Kafka · Docker · React · MySQL · Stripe · JWT
Repo: github.com/Zezoxsaleh/food-ordering-system
• 5+ microservices independently deployable, each owning a distinct business domain (orders, payments, users, notifications, restaurant).
• Kafka event bus decoupling order lifecycle events — placed → confirmed → dispatched — enabling async, fault-tolerant communication.
• Secured all APIs with Spring Security + JWT, supporting role-based access (customer, restaurant admin, driver).
• Integrated Stripe payment gateway covering full checkout lifecycle — charge, confirm, and refund.
• Containerized all services with Docker Compose; single command spins up the entire stack locally.
• REST APIs consumed by a React/Vite frontend with real-time order status updates.

BookCircle — Community Book-Sharing Platform
Stack: ASP.NET Core · Entity Framework Core · SQL Server · SignalR · JWT · React
Repo: github.com/Zezoxsaleh/BookCircle
• 15+ REST API endpoints across auth, book management, and borrowing — built with layered Controller → Service → Repository architecture.
• Role-based authorization for 3 roles (Admin, BookOwner, Reader) using JWT with refresh token support.
• Real-time notifications via SignalR, improving borrowing-request responsiveness.
• Optimized frontend data fetching with React Query caching, reducing redundant API calls.
• Managed full borrow lifecycle: request → approval → return, with admin moderation layer.

Clickstream Data Pipeline — Real-Time Data Engineering
Stack: Apache Kafka · Apache NiFi · Apache Spark · MySQL
Repo: github.com/Zezoxsaleh/clickstream-pipeline
• End-to-end pipeline ingesting thousands of simulated click events per run with sub-second Kafka ingestion latency.
• Kafka topics used for high-throughput stream ingestion and decoupled event delivery between pipeline stages.
• ETL workflows in Apache NiFi — field normalization, filtering, and routing to downstream processors.
• Spark jobs for distributed batch and micro-batch stream processing with aggregation and sessionization.
• Processed results stored in MySQL, queryable for click-funnel and drop-off analysis.

Train Tracking System — Backend Developer
Stack: PHP · JavaScript · REST APIs · MySQL
Repo: github.com/Zezoxsaleh/train-tracking
• Built RESTful backend APIs for real-time train tracking and schedule management.
• Designed relational MySQL schema and implemented dynamic routing logic for timetable management.
• Exposed clean API contracts consumed by a JavaScript frontend for live status display.

EDUCATION

B.Sc. Information Systems — Helwan University 2023 – 2027/28
Faculty of Computer Science & Artificial Intelligence
Coursework: Data Structures & Algorithms · Operating Systems · Database Systems · Software Engineering · Computer Networks · System Analysis & Design

CORE STRENGTHS

• Distributed Systems & Microservices Architecture • Event-Driven Design with Apache Kafka
• REST API Design & Security (JWT / Spring Security) • Docker & Containerized Deployments
• Real-Time Data Pipelines (Kafka · NiFi · Spark) • Clean Architecture & SOLID Principles
• Database Design & Query Optimization
"""

GOLDEN_JOB_TITLE = "Backend Engineer (Java / Spring Boot)"

GOLDEN_REQUIREMENTS: list[dict[str, str]] = [
    # must_have (weight 3)
    {"text": "Java", "category": "must_have", "dimension": "skill"},
    {"text": "Spring Boot", "category": "must_have", "dimension": "skill"},
    {"text": "REST APIs", "category": "must_have", "dimension": "skill"},
    {"text": "Microservices", "category": "must_have", "dimension": "skill"},
    {"text": "PostgreSQL", "category": "must_have", "dimension": "skill"},
    {
        "text": "2+ years professional backend experience",
        "category": "must_have",
        "dimension": "experience",
    },
    # important (weight 2)
    {"text": "Docker", "category": "important", "dimension": "skill"},
    {"text": "Kafka", "category": "important", "dimension": "skill"},
    {"text": "Spring Security", "category": "important", "dimension": "skill"},
    {"text": "SQL", "category": "important", "dimension": "skill"},
    {"text": "Testing", "category": "important", "dimension": "skill"},
    # nice_to_have (weight 1)
    {"text": "AWS", "category": "nice_to_have", "dimension": "skill"},
    {"text": "Kubernetes", "category": "nice_to_have", "dimension": "skill"},
    {"text": "CI/CD", "category": "nice_to_have", "dimension": "skill"},
]

# Allowed evidence_type per golden requirement. These are the semantic facts the
# LLM is permitted to report; anything else is a golden-test defect.
EXPECTED_EVIDENCE_TYPES: dict[str, set[str]] = {
    requirement_key("Java", "must_have"): {"matched"},
    requirement_key("Spring Boot", "must_have"): {"matched"},
    requirement_key("REST APIs", "must_have"): {"matched"},
    requirement_key("Microservices", "must_have"): {"matched"},
    requirement_key("PostgreSQL", "must_have"): {"matched"},
    requirement_key("2+ years professional backend experience", "must_have"): {
        "missing",
        "partial",
    },
    requirement_key("Docker", "important"): {"matched"},
    requirement_key("Kafka", "important"): {"matched"},
    requirement_key("Spring Security", "important"): {"matched"},
    requirement_key("SQL", "important"): {"matched"},
    requirement_key("Testing", "important"): {"matched"},
    requirement_key("AWS", "nice_to_have"): {"missing"},
    requirement_key("Kubernetes", "nice_to_have"): {"missing"},
    requirement_key("CI/CD", "nice_to_have"): {"missing", "partial", "matched"},
}

# Ground-truth skills that must surface in the extracted CandidateProfile, and
# skills that must NOT be invented. Each entry is a set of accepted phrasings
# (case-insensitive, matched on word boundaries).
EXPECTED_GROUNDED_SKILLS: dict[str, tuple[str, ...]] = {
    "java": ("java",),
    "spring boot": ("spring boot",),
    "kafka": ("kafka",),
    "postgresql": ("postgresql",),
    "docker": ("docker",),
    "spring security": ("spring security",),
    "testing": ("testing", "junit"),
    "sql": ("sql",),
    "github actions": ("github actions",),
}
BANNED_SKILLS: tuple[str, ...] = ("aws", "kubernetes")


def _has_token(haystack: str, *tokens: str) -> bool:
    for token in tokens:
        if re.search(rf"\b{re.escape(token)}\b", haystack):
            return True
    return False


def create_golden_parent_records(
    db_session: Session,
) -> tuple[Organization, JobApplication, JobProfile]:
    organization = Organization(name="Golden Saleh Evaluation Org")
    db_session.add(organization)
    db_session.flush()

    user = User(
        organization_id=organization.id,
        email="golden-saleh-evaluation@example.com",
        full_name="Golden Evaluation User",
    )
    candidate = Candidate(
        organization_id=organization.id,
        full_name="Ezzeldeen Saleh",
        email="ezzeldeensa234@gmail.com",
    )
    db_session.add_all([user, candidate])
    db_session.flush()

    job = Job(
        organization_id=organization.id,
        created_by_user_id=user.id,
        title=GOLDEN_JOB_TITLE,
    )
    resume = Resume(
        candidate_id=candidate.id,
        file_uri="local://resumes/golden-ezzeldeen-saleh.pdf",
    )
    db_session.add_all([job, resume])
    db_session.flush()

    application = JobApplication(
        organization_id=organization.id,
        job_id=job.id,
        candidate_id=candidate.id,
        resume_id=resume.id,
    )
    job_profile = JobProfile(
        job_id=job.id,
        version_number=1,
        status="approved",
        source="hr_created",
        profile_data={
            "title": GOLDEN_JOB_TITLE,
            "summary": "Golden backend engineer role used to validate the HERA evaluation workflow.",
            "requirements": GOLDEN_REQUIREMENTS,
            "skills": [
                "Java",
                "Spring Boot",
                "REST APIs",
                "Microservices",
                "PostgreSQL",
                "Docker",
                "Kafka",
                "Spring Security",
                "SQL",
                "Testing",
                "AWS",
                "Kubernetes",
                "CI/CD",
            ],
        },
        approved_by_user_id=user.id,
        approved_at=datetime.now(UTC),
        is_current=True,
    )
    db_session.add_all([application, job_profile])
    db_session.commit()

    return organization, application, job_profile


def _make_soal_providers() -> tuple[
    CandidateProfileExtractionWorkflow, CandidateEvaluationWorkflow, str
]:
    api_key = os.environ.get("SOAL_API_KEY")
    if not api_key:
        pytest.skip("SOAL_API_KEY is not set; skipping real Soal provider tests.")
    settings = Settings(
        ai_provider="soal",
        soal_api_key=api_key,
        soal_model="gemini-3.5-flash",
    )
    extraction = CandidateProfileExtractionWorkflow(provider=get_provider(settings))
    evaluation = CandidateEvaluationWorkflow(
        evidence_provider=get_provider(settings),
        explanation_provider=get_provider(settings),
    )
    return extraction, evaluation, api_key


@pytest.mark.soal
class TestGoldenSalehEvaluation:
    def test_golden_evaluation_against_saleh_cv(self, db_session: Session) -> None:
        organization, application, job_profile = create_golden_parent_records(db_session)
        original_application_status = application.status
        requirements = normalize_job_profile_requirements(job_profile.profile_data["requirements"])
        expected_keys = set(EXPECTED_EVIDENCE_TYPES)
        assert len(requirements) == 14
        assert {requirement.key for requirement in requirements} == expected_keys

        extraction_workflow, evaluation_workflow, _api_key = _make_soal_providers()

        # --- 1. Candidate profile extraction from the exact CV text ---
        extracted = extraction_workflow.run(
            db_session,
            resume_id=application.resume_id,
            organization_id=organization.id,
            resume_text=CV_TEXT,
        )
        db_session.commit()

        profile = db_session.get(CandidateProfile, extracted.profile_id)
        assert profile.status == "extracted"
        assert profile.is_current is True
        assert profile.source == "ai_extracted"
        assert profile.profile_data.get("full_name", "").strip()

        grounded_skills = " | ".join(
            f" {skill.strip().lower()} " for skill in profile.profile_data.get("skills", [])
        )
        for label, phrasings in EXPECTED_GROUNDED_SKILLS.items():
            assert _has_token(grounded_skills, *phrasings), (
                f"extracted skills must ground {label!r} from the CV, got {grounded_skills!r}"
            )
        for banned in BANNED_SKILLS:
            assert not _has_token(grounded_skills, banned), (
                f"extracted skills must not invent {banned!r}, got {grounded_skills!r}"
            )

        # --- 2. Evaluation round 1 (real provider) ---
        first = evaluation_workflow.run(
            db_session,
            job_application_id=application.id,
            organization_id=organization.id,
        )
        db_session.commit()

        evaluation = db_session.get(CandidateEvaluation, first.evaluation_id)
        assert evaluation.status == "completed"
        assert evaluation.version_number == 1
        assert evaluation.is_current is True
        assert evaluation.recommendation is None
        assert evaluation.provenance["workflow"] == "candidate_evaluation"
        assert evaluation.provenance["provider"] == "soal"
        assert "score" not in evaluation.provenance
        assert evaluation.job_profile_id == job_profile.id
        assert evaluation.candidate_profile_id == profile.id

        evidence = list(
            db_session.scalars(
                select(MatchEvidence).where(MatchEvidence.candidate_evaluation_id == evaluation.id)
            )
        )
        assert len(evidence) == 14
        evidence_by_key = {row.requirement_ref["requirement_key"]: row for row in evidence}
        assert set(evidence_by_key) == expected_keys

        for key, allowed in EXPECTED_EVIDENCE_TYPES.items():
            actual = evidence_by_key[key].evidence_type
            assert actual in allowed, (
                f"requirement {key} reported {actual!r}, expected one of {sorted(allowed)!r}"
            )

        score_result = ScoringService().compute(
            requirements,
            build_evidence_by_key(evidence),
        )
        assert Decimal(evaluation.score) == score_result["score"]
        assert evaluation.score_breakdown == score_result["breakdown"]
        assert evaluation.scoring_version == "1.0"

        derived_scores = {
            Decimal("80.645"),
            Decimal("82.258"),
            Decimal("83.871"),
            Decimal("85.484"),
            Decimal("87.097"),
            Decimal("88.710"),
        }
        assert evaluation.score in derived_scores, f"score {evaluation.score} outside derived band"

        assert assign_group(evaluation.score) == "must_review"

        missing_must_have = any(
            (evidence_by_key[requirement.key].evidence_type == "missing")
            for requirement in requirements
            if requirement.category == "must_have"
        )
        assert score_result["review_signals"] == (
            ["missing_must_have"] if missing_must_have else []
        )

        # --- Safety: evaluation never creates HR decisions or mutates the pool ---
        assert (
            db_session.scalar(
                select(func.count())
                .select_from(HRDecision)
                .where(HRDecision.candidate_evaluation_id == evaluation.id)
            )
            == 0
        )
        db_session.refresh(application)
        assert application.status == original_application_status

        # --- 3. Re-run: new version, no evidence accumulation, profiles preserved ---
        second = evaluation_workflow.run(
            db_session,
            job_application_id=application.id,
            organization_id=organization.id,
        )
        db_session.commit()

        first_eval = db_session.get(CandidateEvaluation, first.evaluation_id)
        second_eval = db_session.get(CandidateEvaluation, second.evaluation_id)
        db_session.refresh(first_eval)
        db_session.refresh(second_eval)

        assert second_eval.version_number == 2
        assert first_eval.is_current is False
        assert second_eval.is_current is True
        assert first_eval.score == evaluation.score
        assert second_eval.job_profile_id == job_profile.id
        assert second_eval.candidate_profile_id == profile.id

        first_evidence = list(
            db_session.scalars(
                select(MatchEvidence).where(MatchEvidence.candidate_evaluation_id == first_eval.id)
            )
        )
        second_evidence = list(
            db_session.scalars(
                select(MatchEvidence).where(MatchEvidence.candidate_evaluation_id == second_eval.id)
            )
        )
        assert len(first_evidence) == 14
        assert len(second_evidence) == 14
        assert {row.requirement_ref["requirement_key"] for row in first_evidence} == expected_keys

        total_evidence = db_session.scalar(
            select(func.count())
            .select_from(MatchEvidence)
            .join(
                CandidateEvaluation,
                MatchEvidence.candidate_evaluation_id == CandidateEvaluation.id,
            )
            .where(CandidateEvaluation.job_application_id == application.id)
        )
        assert total_evidence == 28

        # Evaluation must not create new JobProfile / CandidateProfile versions.
        assert (
            db_session.scalar(
                select(func.count())
                .select_from(JobProfile)
                .where(JobProfile.job_id == application.job_id)
            )
            == 1
        )
        assert (
            db_session.scalar(
                select(func.count())
                .select_from(CandidateProfile)
                .where(CandidateProfile.resume_id == application.resume_id)
            )
            == 1
        )
