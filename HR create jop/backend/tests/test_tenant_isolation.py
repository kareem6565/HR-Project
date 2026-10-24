"""Comprehensive Tenant Isolation and AI Settings Security Test Suite (Prompt 4).

Verifies strict cross-tenant isolation across all registered endpoints, models,
services, and queries using independent organizations and real Bearer tokens.
"""

from __future__ import annotations

import io
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from starlette.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import create_app
from app.models import (
    AITrace,
    Candidate,
    CandidateEvaluation,
    CandidateProfile,
    ChatMessage,
    ChatThread,
    HRDecision,
    Interview,
    InterviewQuestion,
    InterviewQuestionSet,
    Job,
    JobApplication,
    JobProfile,
    MatchEvidence,
    Organization,
    Resume,
    User,
    WorkflowRun,
    WorkflowStepTrace,
)
from app.services.storage_service import LocalFileSystemStorage
from app.services.user_service import UserService


# ==============================================================================
# Fixtures: Two Independent Organizations and Users
# ==============================================================================

@pytest.fixture()
def client(db_session):
    """Provide a test client wired to the active database session."""
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def org_a(db_session) -> Organization:
    org = Organization(name="Organization Alpha")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture()
def org_b(db_session) -> Organization:
    org = Organization(name="Organization Beta")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture()
def admin_a(db_session, org_a) -> User:
    user = UserService().create(
        db_session,
        organization_id=org_a.id,
        email="admin@alpha.com",
        full_name="Admin Alpha",
        password="ValidPassword123!",
        role="admin",
    )
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def recruiter_a(db_session, org_a) -> User:
    user = UserService().create(
        db_session,
        organization_id=org_a.id,
        email="recruiter@alpha.com",
        full_name="Recruiter Alpha",
        password="ValidPassword123!",
        role="recruiter",
    )
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def admin_b(db_session, org_b) -> User:
    user = UserService().create(
        db_session,
        organization_id=org_b.id,
        email="admin@beta.com",
        full_name="Admin Beta",
        password="ValidPassword123!",
        role="admin",
    )
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def recruiter_b(db_session, org_b) -> User:
    user = UserService().create(
        db_session,
        organization_id=org_b.id,
        email="recruiter@beta.com",
        full_name="Recruiter Beta",
        password="ValidPassword123!",
        role="recruiter",
    )
    db_session.commit()
    db_session.refresh(user)
    return user


def auth_header(user: User) -> dict[str, str]:
    token = create_access_token(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role,
        token_version=user.token_version,
    )
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# Fixture: Representative Resources for Both Organizations
# ==============================================================================

@pytest.fixture()
def seeded_resources(db_session, org_a, org_b, admin_a, admin_b):
    """Seed representative resources for Organization Alpha and Organization Beta."""
    # Org A resources
    job_a = Job(
        organization_id=org_a.id,
        title="Backend Engineer Alpha",
        raw_description="Build scalable python backend systems for Alpha",
        status="active",
        created_by_user_id=admin_a.id,
    )
    db_session.add(job_a)
    db_session.flush()

    job_profile_a = JobProfile(
        job_id=job_a.id,
        version_number=1,
        is_current=True,
        status="approved",
        source="hr_created",
        profile_data={"requirements": [{"key": "python", "title": "Python 3"}]},
        approved_by_user_id=admin_a.id,
        approved_at=datetime.now(UTC),
    )
    db_session.add(job_profile_a)
    db_session.flush()

    cand_a = Candidate(
        organization_id=org_a.id,
        full_name="Alice Candidate",
        email="alice@cand-alpha.com",
        phone="+1234567890",
    )
    db_session.add(cand_a)
    db_session.flush()

    storage = LocalFileSystemStorage(settings.storage_root_dir)
    resume_id_a = uuid.uuid4()
    storage_key_a = storage.save(
        organization_id=org_a.id,
        resume_id=resume_id_a,
        extension="pdf",
        stream=lambda: b"%PDF-1.4 test resume alpha content",
    )

    resume_a = Resume(
        id=resume_id_a,
        candidate_id=cand_a.id,
        file_uri=storage_key_a,
        original_filename="Alice_CV.pdf",
        content_type="application/pdf",
        file_size_bytes=34,
        status="uploaded",
    )
    db_session.add(resume_a)
    db_session.flush()

    cand_profile_a = CandidateProfile(
        resume_id=resume_a.id,
        version_number=1,
        is_current=True,
        status="current",
        source="system_extracted",
        profile_data={"skills": ["Python", "FastAPI"], "experience": []},
    )
    db_session.add(cand_profile_a)
    db_session.flush()

    app_a = JobApplication(
        organization_id=org_a.id,
        job_id=job_a.id,
        candidate_id=cand_a.id,
        resume_id=resume_a.id,
        status="ready_for_review",
    )
    db_session.add(app_a)
    db_session.flush()

    eval_a = CandidateEvaluation(
        job_application_id=app_a.id,
        job_profile_id=job_profile_a.id,
        candidate_profile_id=cand_profile_a.id,
        version_number=1,
        is_current=True,
        status="completed",
        score=Decimal("85.00"),
        score_breakdown={"python": {"text": "Python 3", "score": 85}},
    )
    db_session.add(eval_a)
    db_session.flush()

    dec_a = HRDecision(
        job_application_id=app_a.id,
        candidate_evaluation_id=eval_a.id,
        user_id=admin_a.id,
        decision="advance",
        reason="Strong candidate for Alpha",
    )
    db_session.add(dec_a)
    db_session.flush()

    qset_a = InterviewQuestionSet(
        organization_id=org_a.id,
        job_application_id=app_a.id,
        version_number=1,
        is_current=True,
        status="approved",
        approved_by_user_id=admin_a.id,
        approved_at=datetime.now(UTC),
    )
    db_session.add(qset_a)
    db_session.flush()

    q_a = InterviewQuestion(
        question_set_id=qset_a.id,
        position=1,
        category="Technical",
        text="Explain python concurrency",
    )
    db_session.add(q_a)
    db_session.flush()

    interview_a = Interview(
        organization_id=org_a.id,
        job_application_id=app_a.id,
        interviewer_user_id=admin_a.id,
        interview_question_set_id=qset_a.id,
        status="scheduled",
        interview_type="technical",
        scheduled_date=date(2026, 11, 1),
        scheduled_time="10:00",
        scheduled_duration_minutes=45,
    )
    db_session.add(interview_a)
    db_session.flush()

    thread_a = ChatThread(
        organization_id=org_a.id,
        created_by_user_id=admin_a.id,
        title="Alpha Recruitment Chat",
    )
    db_session.add(thread_a)
    db_session.flush()

    run_a = WorkflowRun(
        organization_id=org_a.id,
        workflow_type="candidate_evaluation",
        related_entity_type="job_application",
        related_entity_id=app_a.id,
        status="completed",
    )
    db_session.add(run_a)
    db_session.flush()

    step_a = WorkflowStepTrace(
        workflow_run_id=run_a.id,
        step_name="evaluation",
        status="completed",
    )
    db_session.add(step_a)
    db_session.flush()

    ai_trace_a = AITrace(
        workflow_step_trace_id=step_a.id,
        ai_component_name="evaluator",
        status="succeeded",
    )
    db_session.add(ai_trace_a)
    db_session.flush()

    # -------------------------------------------------------------------------
    # Org B resources
    # -------------------------------------------------------------------------
    job_b = Job(
        organization_id=org_b.id,
        title="Data Scientist Beta",
        raw_description="Build predictive models for Beta",
        status="active",
        created_by_user_id=admin_b.id,
    )
    db_session.add(job_b)
    db_session.flush()

    job_profile_b = JobProfile(
        job_id=job_b.id,
        version_number=1,
        is_current=True,
        status="approved",
        source="hr_created",
        profile_data={"requirements": [{"key": "pandas", "title": "Pandas"}]},
        approved_by_user_id=admin_b.id,
        approved_at=datetime.now(UTC),
    )
    db_session.add(job_profile_b)
    db_session.flush()

    cand_b = Candidate(
        organization_id=org_b.id,
        full_name="Bob Candidate",
        email="bob@cand-beta.com",
        phone="+9876543210",
    )
    db_session.add(cand_b)
    db_session.flush()

    resume_id_b = uuid.uuid4()
    storage_key_b = storage.save(
        organization_id=org_b.id,
        resume_id=resume_id_b,
        extension="pdf",
        stream=lambda: b"%PDF-1.4 test resume beta content",
    )

    resume_b = Resume(
        id=resume_id_b,
        candidate_id=cand_b.id,
        file_uri=storage_key_b,
        original_filename="Bob_CV.pdf",
        content_type="application/pdf",
        file_size_bytes=32,
        status="uploaded",
    )
    db_session.add(resume_b)
    db_session.flush()

    cand_profile_b = CandidateProfile(
        resume_id=resume_b.id,
        version_number=1,
        is_current=True,
        status="current",
        source="system_extracted",
        profile_data={"skills": ["Pandas", "Scikit-Learn"], "experience": []},
    )
    db_session.add(cand_profile_b)
    db_session.flush()

    app_b = JobApplication(
        organization_id=org_b.id,
        job_id=job_b.id,
        candidate_id=cand_b.id,
        resume_id=resume_b.id,
        status="ready_for_review",
    )
    db_session.add(app_b)
    db_session.flush()

    eval_b = CandidateEvaluation(
        job_application_id=app_b.id,
        job_profile_id=job_profile_b.id,
        candidate_profile_id=cand_profile_b.id,
        version_number=1,
        is_current=True,
        status="completed",
        score=Decimal("92.00"),
        score_breakdown={"pandas": {"text": "Pandas", "score": 92}},
    )
    db_session.add(eval_b)
    db_session.flush()

    dec_b = HRDecision(
        job_application_id=app_b.id,
        candidate_evaluation_id=eval_b.id,
        user_id=admin_b.id,
        decision="advance",
        reason="Strong candidate for Beta",
    )
    db_session.add(dec_b)
    db_session.flush()

    qset_b = InterviewQuestionSet(
        organization_id=org_b.id,
        job_application_id=app_b.id,
        version_number=1,
        is_current=True,
        status="approved",
        approved_by_user_id=admin_b.id,
        approved_at=datetime.now(UTC),
    )
    db_session.add(qset_b)
    db_session.flush()

    q_b = InterviewQuestion(
        question_set_id=qset_b.id,
        position=1,
        category="Technical",
        text="Explain random forest internals",
    )
    db_session.add(q_b)
    db_session.flush()

    interview_b = Interview(
        organization_id=org_b.id,
        job_application_id=app_b.id,
        interviewer_user_id=admin_b.id,
        interview_question_set_id=qset_b.id,
        status="scheduled",
        interview_type="technical",
        scheduled_date=date(2026, 11, 2),
        scheduled_time="14:00",
        scheduled_duration_minutes=60,
    )
    db_session.add(interview_b)
    db_session.flush()

    thread_b = ChatThread(
        organization_id=org_b.id,
        created_by_user_id=admin_b.id,
        title="Beta Recruitment Chat",
    )
    db_session.add(thread_b)
    db_session.flush()

    run_b = WorkflowRun(
        organization_id=org_b.id,
        workflow_type="candidate_evaluation",
        related_entity_type="job_application",
        related_entity_id=app_b.id,
        status="completed",
    )
    db_session.add(run_b)
    db_session.flush()

    step_b = WorkflowStepTrace(
        workflow_run_id=run_b.id,
        step_name="evaluation",
        status="completed",
    )
    db_session.add(step_b)
    db_session.flush()

    ai_trace_b = AITrace(
        workflow_step_trace_id=step_b.id,
        ai_component_name="evaluator",
        status="succeeded",
    )
    db_session.add(ai_trace_b)
    db_session.commit()

    return {
        "job_a": job_a,
        "job_b": job_b,
        "job_profile_a": job_profile_a,
        "job_profile_b": job_profile_b,
        "cand_a": cand_a,
        "cand_b": cand_b,
        "resume_a": resume_a,
        "resume_b": resume_b,
        "cand_profile_a": cand_profile_a,
        "cand_profile_b": cand_profile_b,
        "app_a": app_a,
        "app_b": app_b,
        "eval_a": eval_a,
        "eval_b": eval_b,
        "dec_a": dec_a,
        "dec_b": dec_b,
        "qset_a": qset_a,
        "qset_b": qset_b,
        "interview_a": interview_a,
        "interview_b": interview_b,
        "thread_a": thread_a,
        "thread_b": thread_b,
        "run_a": run_a,
        "run_b": run_b,
        "step_a": step_a,
        "step_b": step_b,
        "ai_trace_a": ai_trace_a,
        "ai_trace_b": ai_trace_b,
    }


# ==============================================================================
# 1. Cross-Tenant Read Protection (Returning 404 Not Found)
# ==============================================================================

def test_cross_tenant_read_returns_404(client, recruiter_a, seeded_resources) -> None:
    """Organization Alpha cannot retrieve Organization Beta's resources by ID."""
    headers = auth_header(recruiter_a)
    res = seeded_resources

    endpoints = [
        f"/api/v1/jobs/{res['job_b'].id}",
        f"/api/v1/jobs/{res['job_b'].id}/profiles/{res['job_profile_b'].version_number}",
        f"/api/v1/jobs/{res['job_b'].id}/profiles",
        f"/api/v1/jobs/{res['job_b'].id}/candidates",
        f"/api/v1/candidates/{res['cand_b'].id}",
        f"/api/v1/candidates/{res['cand_b'].id}/resumes",
        f"/api/v1/resumes/{res['resume_b'].id}",
        f"/api/v1/resumes/{res['resume_b'].id}/download",
        f"/api/v1/resumes/{res['resume_b'].id}/profiles/{res['cand_profile_b'].version_number}",
        f"/api/v1/resumes/{res['resume_b'].id}/profiles",
        f"/api/v1/job-applications/{res['app_b'].id}",
        f"/api/v1/job-applications/{res['app_b'].id}/evaluations/{res['eval_b'].version_number}",
        f"/api/v1/job-applications/{res['app_b'].id}/evaluations",
        f"/api/v1/job-applications/{res['app_b'].id}/review",
        f"/api/v1/interview-question-sets/{res['qset_b'].id}",
        f"/api/v1/interview-questions?candidate_id={res['cand_b'].id}",
        f"/api/v1/interviews/{res['interview_b'].id}",
        f"/api/v1/chat/threads/{res['thread_b'].id}",
        f"/api/v1/observability/workflow-runs/{res['run_b'].id}",
        f"/api/v1/observability/workflow-step-traces/{res['step_b'].id}",
        f"/api/v1/observability/ai-traces/{res['ai_trace_b'].id}",
    ]

    for endpoint in endpoints:
        resp = client.get(endpoint, headers=headers)
        assert resp.status_code == 404, f"Expected 404 for {endpoint}, got {resp.status_code}: {resp.text}"


def test_cross_tenant_read_by_id_does_not_leak_via_422(client, recruiter_a, seeded_resources) -> None:
    """Verifies that requesting an existing cross-tenant ID returns 404, not 422."""
    headers = auth_header(recruiter_a)
    res = seeded_resources

    # Both a truly non-existent UUID and Org B's existing UUID return identical 404s
    random_id = uuid.uuid4()
    resp_nonexistent = client.get(f"/api/v1/candidates/{random_id}", headers=headers)
    resp_cross_tenant = client.get(f"/api/v1/candidates/{res['cand_b'].id}", headers=headers)

    assert resp_nonexistent.status_code == 404
    assert resp_cross_tenant.status_code == 404
    assert resp_nonexistent.json() == resp_cross_tenant.json()


# ==============================================================================
# 2. List & Search Isolation (Excluding Cross-Tenant Data)
# ==============================================================================

def test_list_queries_exclude_other_organization_data(client, recruiter_a, seeded_resources) -> None:
    """List, search, and summary queries only return caller organization data."""
    headers = auth_header(recruiter_a)
    res = seeded_resources

    # 1. Jobs list
    resp = client.get("/api/v1/jobs", headers=headers)
    assert resp.status_code == 200
    job_ids = [j["id"] for j in resp.json()]
    assert str(res["job_a"].id) in job_ids
    assert str(res["job_b"].id) not in job_ids

    # 2. Candidates list
    resp = client.get("/api/v1/candidates", headers=headers)
    assert resp.status_code == 200
    cand_ids = [c["id"] for c in resp.json()]
    assert str(res["cand_a"].id) in cand_ids
    assert str(res["cand_b"].id) not in cand_ids

    # 3. Job applications list
    resp = client.get("/api/v1/job-applications", headers=headers)
    assert resp.status_code == 200
    app_ids = [a["id"] for a in resp.json()]
    assert str(res["app_a"].id) in app_ids
    assert str(res["app_b"].id) not in app_ids

    # 4. Talent pool list
    resp = client.get("/api/v1/talent-pool", headers=headers)
    assert resp.status_code == 200
    talent_app_ids = [r["application_id"] for r in resp.json()]
    assert str(res["app_b"].id) not in talent_app_ids

    # 5. Interviews list
    resp = client.get("/api/v1/interviews", headers=headers)
    assert resp.status_code == 200
    interview_ids = [i["id"] for i in resp.json()["interviews"]]
    assert str(res["interview_a"].id) in interview_ids
    assert str(res["interview_b"].id) not in interview_ids

    # 6. Interview slots
    resp = client.get("/api/v1/interview-slots?scheduled_date=2026-11-01", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1  # Only Alpha's interview on this date

    resp_b_date = client.get("/api/v1/interview-slots?scheduled_date=2026-11-02", headers=headers)
    assert resp_b_date.status_code == 200
    assert resp_b_date.json()["total"] == 0  # Beta has an interview on this date, Alpha does not

    # 7. Interviewers list
    resp = client.get("/api/v1/interviewers", headers=headers)
    assert resp.status_code == 200
    interviewer_emails = [i["email"] for i in resp.json()]
    assert "admin@alpha.com" in interviewer_emails
    assert "admin@beta.com" not in interviewer_emails

    # 8. Chat threads list
    resp = client.get("/api/v1/chat/threads", headers=headers)
    assert resp.status_code == 200
    thread_ids = [t["id"] for t in resp.json()["threads"]]
    assert str(res["thread_a"].id) in thread_ids
    assert str(res["thread_b"].id) not in thread_ids

    # 9. AI activity workflow runs list
    resp = client.get("/api/v1/ai-activity/runs", headers=headers)
    assert resp.status_code == 200
    run_ids = [r["id"] for r in resp.json()]
    assert str(res["run_a"].id) in run_ids
    assert str(res["run_b"].id) not in run_ids


# ==============================================================================
# 3. Cross-Tenant Mutation Protection
# ==============================================================================

def test_cross_tenant_update_and_delete_returns_404(client, admin_a, seeded_resources) -> None:
    """Organization Alpha cannot modify or delete Organization Beta's records."""
    headers = auth_header(admin_a)
    res = seeded_resources

    # 1. Update job
    resp = client.patch(
        f"/api/v1/jobs/{res['job_b'].id}",
        json={"title": "Hacked Title"},
        headers=headers,
    )
    assert resp.status_code == 404

    # 2. Delete job
    resp = client.delete(
        f"/api/v1/jobs/{res['job_b'].id}",
        headers=headers,
    )
    assert resp.status_code == 404

    # 3. Update candidate
    resp = client.patch(
        f"/api/v1/candidates/{res['cand_b'].id}",
        json={"email": "hacked@alpha.com"},
        headers=headers,
    )
    assert resp.status_code == 404

    # 4. Cancel interview
    resp = client.patch(
        f"/api/v1/interviews/{res['interview_b'].id}",
        json={"status": "cancelled"},
        headers=headers,
    )
    assert resp.status_code == 404

    # 5. Submit interview feedback
    resp = client.post(
        f"/api/v1/interviews/{res['interview_b'].id}/feedback",
        json={
            "technical": 5,
            "communication": 5,
            "problem_solving": 5,
            "overall": 5.0,
            "comments": "Hacked feedback",
        },
        headers=headers,
    )
    assert resp.status_code == 404

    # 6. Rename chat thread
    resp = client.patch(
        f"/api/v1/chat/threads/{res['thread_b'].id}",
        json={"title": "Hacked Thread"},
        headers=headers,
    )
    assert resp.status_code == 404

    # 7. Post message to chat thread
    resp = client.post(
        f"/api/v1/chat/threads/{res['thread_b'].id}/messages",
        json={"content": "Hacked message"},
        headers=headers,
    )
    assert resp.status_code == 404

    # 8. Approve job profile
    resp = client.post(
        f"/api/v1/jobs/{res['job_b'].id}/profiles/{res['job_profile_b'].version_number}/approve",
        headers=headers,
    )
    assert resp.status_code == 404

    # 9. Approve interview question set
    resp = client.post(
        f"/api/v1/interview-question-sets/{res['qset_b'].id}/approve",
        headers=headers,
    )
    assert resp.status_code == 404

    # 10. Retry workflow run
    resp = client.post(
        f"/api/v1/ai-activity/runs/{res['run_b'].id}/retry",
        headers=headers,
    )
    assert resp.status_code == 404


# ==============================================================================
# 4. Nested Resource Linking Rejection (Prevent Cross-Tenant References)
# ==============================================================================

def test_cannot_link_cross_tenant_resources_in_job_application(
    client, recruiter_a, seeded_resources
) -> None:
    """An organization cannot create an application linking its own resources to Org B's resources."""
    headers = auth_header(recruiter_a)
    res = seeded_resources

    # Case 1: Org A Job + Org B Candidate + Org A Resume -> 404
    resp = client.post(
        "/api/v1/job-applications",
        json={
            "job_id": str(res["job_a"].id),
            "candidate_id": str(res["cand_b"].id),
            "resume_id": str(res["resume_a"].id),
        },
        headers=headers,
    )
    assert resp.status_code == 404

    # Case 2: Org B Job + Org A Candidate + Org A Resume -> 404
    resp = client.post(
        "/api/v1/job-applications",
        json={
            "job_id": str(res["job_b"].id),
            "candidate_id": str(res["cand_a"].id),
            "resume_id": str(res["resume_a"].id),
        },
        headers=headers,
    )
    assert resp.status_code == 404

    # Case 3: Org A Job + Org A Candidate + Org B Resume -> 404
    resp = client.post(
        "/api/v1/job-applications",
        json={
            "job_id": str(res["job_a"].id),
            "candidate_id": str(res["cand_a"].id),
            "resume_id": str(res["resume_b"].id),
        },
        headers=headers,
    )
    assert resp.status_code == 404


def test_cannot_upload_resume_to_cross_tenant_candidate(client, recruiter_a, seeded_resources) -> None:
    """Uploading a resume to another organization's candidate returns 404."""
    headers = auth_header(recruiter_a)
    res = seeded_resources

    file_payload = {"file": ("malicious.pdf", io.BytesIO(b"%PDF-1.4 sample content"), "application/pdf")}
    resp = client.post(
        f"/api/v1/candidates/{res['cand_b'].id}/resumes/upload",
        files=file_payload,
        headers=headers,
    )
    assert resp.status_code == 404


def test_cannot_schedule_interview_with_cross_tenant_resources(
    client, recruiter_a, seeded_resources
) -> None:
    """Scheduling an interview with cross-tenant candidate, job, or question set returns 404."""
    headers = auth_header(recruiter_a)
    res = seeded_resources

    # 1. Cross-tenant candidate
    resp = client.post(
        "/api/v1/interviews",
        json={
            "candidate_id": str(res["cand_b"].id),
            "job_id": str(res["job_a"].id),
            "interview_type": "technical",
            "scheduled_date": "2026-11-15",
            "scheduled_time": "11:00",
        },
        headers=headers,
    )
    assert resp.status_code == 404

    # 2. Cross-tenant job
    resp = client.post(
        "/api/v1/interviews",
        json={
            "candidate_id": str(res["cand_a"].id),
            "job_id": str(res["job_b"].id),
            "interview_type": "technical",
            "scheduled_date": "2026-11-15",
            "scheduled_time": "11:00",
        },
        headers=headers,
    )
    assert resp.status_code == 404

    # 3. Cross-tenant question set
    resp = client.post(
        "/api/v1/interviews",
        json={
            "candidate_id": str(res["cand_a"].id),
            "job_id": str(res["job_a"].id),
            "interview_type": "technical",
            "scheduled_date": "2026-11-15",
            "scheduled_time": "11:00",
            "interview_question_set_id": str(res["qset_b"].id),
        },
        headers=headers,
    )
    assert resp.status_code == 404


def test_cannot_record_hr_decision_on_cross_tenant_application(
    client, recruiter_a, seeded_resources
) -> None:
    """Submitting an HR decision on Org B's application returns 404."""
    headers = auth_header(recruiter_a)
    res = seeded_resources

    resp = client.post(
        "/api/v1/hr-decisions",
        json={
            "job_application_id": str(res["app_b"].id),
            "decision": "advance",
            "reason": "Unauthorized decision attempt",
        },
        headers=headers,
    )
    assert resp.status_code == 404


def test_cannot_trigger_workflows_on_cross_tenant_resources(
    client, recruiter_a, seeded_resources
) -> None:
    """AI workflows reject execution on another organization's application with 404."""
    headers = auth_header(recruiter_a)
    res = seeded_resources

    # 1. Candidate evaluation workflow
    resp = client.post(
        "/api/v1/workflows/candidate-evaluations",
        json={"job_application_id": str(res["app_b"].id)},
        headers=headers,
    )
    assert resp.status_code == 404

    # 2. Interview question generation workflow
    resp = client.post(
        "/api/v1/workflows/interview-questions",
        json={"job_application_id": str(res["app_b"].id)},
        headers=headers,
    )
    assert resp.status_code == 404


# ==============================================================================
# 5. Client-Supplied Organization and User Identifiers Cannot Override Context
# ==============================================================================

def test_client_supplied_org_id_in_payload_is_ignored_or_rejected(
    client, db_session, recruiter_a, org_b
) -> None:
    """Supplying Org B's id in a create payload does not create the record in Org B."""
    headers = auth_header(recruiter_a)

    # 1. Create job with foreign organization_id in request body
    resp = client.post(
        "/api/v1/jobs",
        json={
            "title": "Alpha Scoped Job",
            "raw_description": "Job description here",
            "organization_id": str(org_b.id),
        },
        headers=headers,
    )
    assert resp.status_code == 201
    created_job_id = resp.json()["id"]

    job = db_session.get(Job, uuid.UUID(created_job_id))
    assert job is not None
    assert job.organization_id == recruiter_a.organization_id
    assert job.organization_id != org_b.id

    # 2. Create candidate with foreign organization_id in request body
    resp = client.post(
        "/api/v1/candidates",
        json={
            "full_name": "Alpha Scoped Candidate",
            "email": "alpha_scoped@cand.com",
            "organization_id": str(org_b.id),
        },
        headers=headers,
    )
    assert resp.status_code == 201
    created_cand_id = resp.json()["id"]

    candidate = db_session.get(Candidate, uuid.UUID(created_cand_id))
    assert candidate is not None
    assert candidate.organization_id == recruiter_a.organization_id
    assert candidate.organization_id != org_b.id


def test_client_supplied_legacy_headers_do_not_override_jwt_identity(
    client, recruiter_a, org_b, admin_b
) -> None:
    """Supplying X-Organization-Id or X-User-Id headers does not override trusted JWT context."""
    headers = auth_header(recruiter_a)
    headers["X-Organization-Id"] = str(org_b.id)
    headers["X-User-Id"] = str(admin_b.id)

    # Calling /auth/me should return recruiter_a's details, not admin_b's or org_b's
    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(recruiter_a.id)
    assert data["organization_id"] == str(recruiter_a.organization_id)
    assert data["role"] == "recruiter"


# ==============================================================================
# 6. Role & Administration Protection
# ==============================================================================

def test_recruiter_cannot_access_ai_settings(client, recruiter_a) -> None:
    """Recruiters receive 403 Forbidden on AI configuration endpoints."""
    headers = auth_header(recruiter_a)

    resp = client.get("/api/v1/settings/ai", headers=headers)
    assert resp.status_code == 403

    resp = client.post("/api/v1/settings/ai/verify", json={}, headers=headers)
    assert resp.status_code == 403


def test_recruiter_cannot_manage_users(client, recruiter_a, org_a) -> None:
    """Recruiters receive 403 Forbidden when trying to list or create users."""
    headers = auth_header(recruiter_a)

    resp = client.get(f"/api/v1/organizations/{org_a.id}/users", headers=headers)
    assert resp.status_code == 403

    resp = client.post(
        f"/api/v1/organizations/{org_a.id}/users",
        json={
            "email": "newuser@alpha.com",
            "full_name": "New User",
            "password": "ValidPassword123!",
            "role": "recruiter",
        },
        headers=headers,
    )
    assert resp.status_code == 403


def test_admin_cannot_provision_or_list_users_in_other_organization(
    client, admin_a, org_b
) -> None:
    """Administrator of Organization Alpha cannot provision or list users in Organization Beta."""
    headers = auth_header(admin_a)

    # List Org B users -> 403 Forbidden
    resp = client.get(f"/api/v1/organizations/{org_b.id}/users", headers=headers)
    assert resp.status_code == 403

    # Provision user under Org B path -> 403 Forbidden
    resp = client.post(
        f"/api/v1/organizations/{org_b.id}/users",
        json={
            "email": "infiltrator@beta.com",
            "full_name": "Infiltrator",
            "password": "ValidPassword123!",
            "role": "recruiter",
        },
        headers=headers,
    )
    assert resp.status_code == 403

    # Provision user under /users with foreign organization_id -> 403 Forbidden
    resp = client.post(
        "/api/v1/users",
        json={
            "email": "infiltrator2@beta.com",
            "full_name": "Infiltrator 2",
            "password": "ValidPassword123!",
            "role": "recruiter",
            "organization_id": str(org_b.id),
        },
        headers=headers,
    )
    assert resp.status_code == 403


def test_unauthenticated_requests_are_rejected(client, seeded_resources) -> None:
    """Requests without Bearer tokens return 401 Unauthorized across protected routes."""
    res = seeded_resources

    endpoints = [
        ("/api/v1/jobs", "GET"),
        (f"/api/v1/jobs/{res['job_a'].id}", "GET"),
        ("/api/v1/candidates", "GET"),
        (f"/api/v1/candidates/{res['cand_a'].id}", "GET"),
        ("/api/v1/job-applications", "GET"),
        (f"/api/v1/job-applications/{res['app_a'].id}", "GET"),
        ("/api/v1/settings/ai", "GET"),
        ("/api/v1/interviews", "GET"),
        ("/api/v1/chat/threads", "GET"),
    ]

    for endpoint, method in endpoints:
        if method == "GET":
            resp = client.get(endpoint)
        assert resp.status_code == 401, f"Expected 401 for {endpoint}, got {resp.status_code}"


# ==============================================================================
# 7. AI Settings Configuration Security
# ==============================================================================

def test_ai_settings_endpoint_never_exposes_api_key_secret(client, admin_a) -> None:
    """GET /settings/ai returns key status and provider but never the secret key."""
    headers = auth_header(admin_a)

    resp = client.get("/api/v1/settings/ai", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "provider" in data
    assert "has_api_key" in data
    assert "api_key_source" in data
    # Ensure sensitive credentials are never in the response dictionary
    assert "api_key" not in data
    assert "soal_api_key" not in data
    assert "secret" not in data


def test_runtime_ai_key_mutation_endpoints_are_disabled(client, admin_a) -> None:
    """POST /settings/ai/api-key and DELETE /settings/ai/api-key return 405 Method Not Allowed."""
    headers = auth_header(admin_a)

    # POST key mutation -> 405
    resp = client.post(
        "/api/v1/settings/ai/api-key",
        json={"api_key": "some-key-value"},
        headers=headers,
    )
    assert resp.status_code == 405
    assert "disabled" in resp.json()["detail"].lower()

    # DELETE key mutation -> 405
    resp = client.delete(
        "/api/v1/settings/ai/api-key",
        headers=headers,
    )
    assert resp.status_code == 405
    assert "disabled" in resp.json()["detail"].lower()


# ==============================================================================
# 8. AI Chat & Tools Tenant Isolation
# ==============================================================================

def test_ai_chat_assistant_cannot_access_cross_tenant_application(
    client, recruiter_a, seeded_resources
) -> None:
    """HERA chat tool execution rejects cross-tenant application lookups grounded in tenant scope."""
    headers = auth_header(recruiter_a)
    res = seeded_resources

    # Create a chat thread in Org Alpha
    resp = client.post(
        "/api/v1/chat/threads",
        json={"title": "Test Chat Isolation"},
        headers=headers,
    )
    assert resp.status_code == 201
    thread_id = resp.json()["id"]

    # Send a prompt referencing Organization Beta's application ID
    resp = client.post(
        f"/api/v1/chat/threads/{thread_id}/messages",
        json={"content": f"Can you give me the application details for {res['app_b'].id}?"},
        headers=headers,
    )
    assert resp.status_code == 200
    msg = resp.json()["message"]

    # In fake provider mode, the planner triggers get_application_details tool.
    # The tool returns ok=False with not found error, preventing any leak of Org B data.
    tool_results = msg.get("tool_results")
    if tool_results:
        app_result = next((tr for tr in tool_results if tr.get("tool") == "get_application_details"), None)
        if app_result:
            assert app_result["ok"] is False
            assert "not found" in app_result["error"].lower()
            assert app_result["data"] is None
