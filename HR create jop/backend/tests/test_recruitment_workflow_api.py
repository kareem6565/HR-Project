from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import app
from app.models import Candidate, Job, JobApplication, Organization, Resume, User
from app.services.decision_service import DecisionService
from app.services.scheduling_workflow_service import SchedulingWorkflowService


@pytest.fixture()
def client(db_session: Session) -> Generator[httpx.Client, None, None]:
    connection = db_session.connection()
    db_session.bind = connection

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def auth_headers(org_id: str, user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id, "X-Organization-Id": org_id}


def seed_entities(db: Session):
    org = Organization(name="API Test Org")
    db.add(org)
    db.flush()

    user = User(
        organization_id=org.id,
        email="recruiter-api@example.com",
        full_name="Recruiter One",
        role="recruiter",
    )
    interviewer = User(
        organization_id=org.id,
        email="interviewer-api@example.com",
        full_name="Interviewer One",
        role="recruiter",
    )
    candidate = Candidate(
        organization_id=org.id,
        full_name="Salma Test",
        email="salma.test@example.com",
    )
    db.add_all([user, interviewer, candidate])
    db.flush()

    job = Job(
        organization_id=org.id,
        created_by_user_id=user.id,
        title="Frontend Specialist",
        department="Product",
        status="active",
    )
    resume = Resume(
        candidate_id=candidate.id,
        file_uri="local://res/salma.pdf",
    )
    db.add_all([job, resume])
    db.flush()

    application = JobApplication(
        organization_id=org.id,
        job_id=job.id,
        candidate_id=candidate.id,
        resume_id=resume.id,
        status="created",
    )
    db.add(application)
    db.commit()

    return org, user, interviewer, job, candidate, application


def test_api_advance_gate_denies_interview_scheduling_before_decision(client: httpx.Client, db_session: Session) -> None:
    org, user, interviewer, job, candidate, application = seed_entities(db_session)
    headers = auth_headers(str(org.id), str(user.id))

    # Direct API POST /interviews before advance decision returns 422
    resp = client.post(
        "/api/v1/interviews",
        headers=headers,
        json={
            "candidate_id": str(candidate.id),
            "job_id": str(job.id),
            "interview_type": "technical",
            "scheduled_date": "2026-11-20",
            "scheduled_time": "10:00 AM",
            "interviewer_user_id": str(interviewer.id),
        },
    )
    assert resp.status_code == 422
    assert "Interview scheduling denied" in resp.json()["detail"]


def test_api_hr_decision_is_consistent_in_application_list_and_review_bundle(
    client: httpx.Client, db_session: Session
) -> None:
    org, user, _interviewer, _job, _candidate, application = seed_entities(db_session)
    headers = auth_headers(str(org.id), str(user.id))

    decision_response = client.post(
        f"/api/v1/job-applications/{application.id}/decisions",
        headers=headers,
        json={"decision": "advance"},
    )
    assert decision_response.status_code == 201
    assert decision_response.json()["decision"] == "advance"

    applications_response = client.get("/api/v1/job-applications", headers=headers)
    assert applications_response.status_code == 200
    application_row = next(
        row for row in applications_response.json() if row["id"] == str(application.id)
    )
    assert application_row["status"] == "advanced"
    assert application_row["group"] == "lower_priority"

    review_response = client.get(
        f"/api/v1/job-applications/{application.id}/review-bundle",
        headers=headers,
    )
    assert review_response.status_code == 200
    review = review_response.json()
    assert review["application"]["status"] == "advanced"
    assert review["pool_row"]["status"] == "advanced"
    assert review["pool_row"]["decision"] == "advance"
    assert review["pool_row"]["group"] == "lower_priority"


def test_api_invitation_creation_and_candidate_portal_booking(client: httpx.Client, db_session: Session) -> None:
    org, user, interviewer, job, candidate, application = seed_entities(db_session)
    headers = auth_headers(str(org.id), str(user.id))

    # 1. Advance candidate via DecisionService
    DecisionService().create(
        db_session,
        job_application_id=application.id,
        user_id=user.id,
        decision="advance",
        organization_id=org.id,
    )
    db_session.commit()

    # 2. Publish interviewer availability via API
    avail_resp = client.post(
        "/api/v1/availability",
        headers=headers,
        json={
            "interviewer_user_id": str(interviewer.id),
            "scheduled_date": "2026-11-25",
            "start_time": "10:00",
            "end_time": "12:00",
            "duration_minutes": 60,
        },
    )
    assert avail_resp.status_code == 201
    next_day_avail = client.post(
        "/api/v1/availability",
        headers=headers,
        json={
            "interviewer_user_id": str(interviewer.id),
            "scheduled_date": "2026-11-27",
            "start_time": "13:00",
            "end_time": "14:00",
            "duration_minutes": 60,
        },
    )
    assert next_day_avail.status_code == 201

    # 3. Create candidate invitation via API
    inv_resp = client.post(
        f"/api/v1/job-applications/{application.id}/invitations",
        headers=headers,
        json={"expires_in_days": 7, "notes": "Welcome to HERA scheduling"},
    )
    assert inv_resp.status_code == 201
    token = inv_resp.json()["token"]

    # 4. Candidate accesses public portal view (NO auth headers required!)
    portal_resp = client.post(
        "/api/v1/candidate-portal/interview/preview", json={"token": token}
    )
    assert portal_resp.status_code == 200
    portal_data = portal_resp.json()
    assert portal_data["candidate_name"] == "Salma Test"
    assert portal_data["job_title"] == "Frontend Specialist"
    assert "score" not in portal_data

    # 5. Candidate queries open slots
    slots_resp = client.post(
        "/api/v1/candidate-portal/interview/slots",
        json={"token": token, "month": "2026-11-01"},
    )
    assert slots_resp.status_code == 200
    slots = slots_resp.json()
    assert len(slots) == 3
    assert slots[0]["start_time"] == "10:00"
    assert any(slot["date"] == "2026-11-27" for slot in slots)

    # 6. Candidate books 10:00 slot
    book_resp = client.post(
        "/api/v1/candidate-portal/interview/book",
        json={
            "token": token,
            "availability_id": slots[0]["availability_id"],
            "scheduled_time": "10:00",
        },
    )
    assert book_resp.status_code == 201
    assert book_resp.json()["status"] == "scheduled"
    assert book_resp.json()["scheduled_time"] == "10:00"
    assert book_resp.json()["timezone"] == "UTC"

    # 7. A used invitation no longer exposes slots or permits rescheduling.
    remaining_resp = client.post(
        "/api/v1/candidate-portal/interview/slots",
        json={"token": token, "month": "2026-11-01"},
    )
    assert remaining_resp.json() == []
    assert "candidate_id" not in book_resp.json()
    assert "organization_id" not in book_resp.json()


def test_api_feedback_learning_loop(client: httpx.Client, db_session: Session) -> None:
    org, user, _interviewer, job, _candidate, _application = seed_entities(db_session)
    headers = auth_headers(str(org.id), str(user.id))

    # 1. Post a correction
    corr_resp = client.post(
        "/api/v1/feedback/corrections",
        headers=headers,
        json={
            "correction_type": "skill_alias_correction",
            "job_id": str(job.id),
            "original_ai_output": {"term": "vue.js"},
            "hr_corrected_result": {"term": "vue"},
            "reason": "Map Vue.js to canonical vue skill",
        },
    )
    assert corr_resp.status_code == 201

    # 2. Get analytics
    analytics_resp = client.get("/api/v1/feedback/analytics", headers=headers)
    assert analytics_resp.status_code == 200
    analytics = analytics_resp.json()
    assert analytics["total_corrections"] >= 1

    # 3. Propose alias
    alias_resp = client.post(
        "/api/v1/feedback/aliases/propose",
        headers=headers,
        json={"alias": "golang", "canonical_skill": "go"},
    )
    assert alias_resp.status_code == 200
    assert alias_resp.json()["status"] == "activated"

    # 4. Benchmark evaluation
    bench_resp = client.post(
        "/api/v1/feedback/evaluation-run",
        headers=headers,
        json={
            "test_cases": [
                {"text": "Built backend microservices in golang", "term": "go", "expected": True},
                {"text": "Python data pipeline developer", "term": "go", "expected": False},
            ]
        },
    )
    assert bench_resp.status_code == 200
    bench = bench_resp.json()
    assert bench["total_evaluated"] == 2
    assert bench["accuracy_pct"] == 100.0
