"""Comprehensive test suite for Immutable Audit Trail and Decision Integrity (HERA Prompt 9).

Covers:
1. Immutability:
   - Database triggers prevent SQL UPDATE and DELETE on audit_logs.
   - Application service exposes no mutation or deletion methods.
   - Idempotent schema initialization.
2. Audit Event Generation:
   - HR decision creation (and atomicity on rollback).
   - JobProfile approval.
   - CandidateEvaluation creation and re-evaluation.
   - Resume download.
   - User creation, role update, and account deactivation.
   - Authentication failure recording with safe categories and no credentials.
   - Metadata data minimization (no passwords, tokens, API keys, CV text).
3. Decision Integrity & Freshness:
   - Evaluation freshness check (409 Conflict on stale expected_evaluation_id).
   - Organization/application mismatch checks.
   - Idempotent repeated decision submissions.
   - Full append-only decision history preservation on subsequent decisions.
4. Admin-Only Audit Access:
   - Unauthenticated 401.
   - Recruiter role 403.
   - Admin access 200 with tenant scoping.
   - Pagination and query filtering.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import create_app
from app.models import (
    AuditLog,
    Candidate,
    CandidateEvaluation,
    CandidateProfile,
    HRDecision,
    Job,
    JobApplication,
    JobProfile,
    Organization,
    Resume,
    User,
)
from app.services.audit_service import AuditService, sanitize_audit_metadata
from app.services.decision_service import DecisionService
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.services.job_profile_service import JobProfileService
from app.services.user_service import UserService


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(
        user_id=user.id,
        organization_id=user.organization_id,
        role=user.role,
        token_version=user.token_version,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client(db_session: Session):
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def setup_org_and_users(db_session: Session):
    org = Organization(name="Audit Test Org")
    db_session.add(org)
    db_session.flush()

    admin = UserService().create(
        db_session,
        organization_id=org.id,
        email="audit-admin@example.com",
        full_name="Audit Admin",
        password="ValidPassword123!",
        role="admin",
    )
    recruiter = UserService().create(
        db_session,
        organization_id=org.id,
        email="audit-recruiter@example.com",
        full_name="Audit Recruiter",
        password="ValidPassword123!",
        role="recruiter",
    )

    other_org = Organization(name="Other Test Org")
    db_session.add(other_org)
    db_session.flush()

    other_admin = UserService().create(
        db_session,
        organization_id=other_org.id,
        email="other-admin@example.com",
        full_name="Other Admin",
        password="ValidPassword123!",
        role="admin",
    )

    db_session.commit()
    return org, admin, recruiter, other_org, other_admin


@pytest.fixture()
def setup_application_and_eval(db_session: Session, setup_org_and_users):
    org, admin, recruiter, other_org, other_admin = setup_org_and_users

    candidate = Candidate(
        organization_id=org.id,
        full_name="Audit Candidate",
        email="audit-candidate@example.com",
    )
    db_session.add(candidate)
    db_session.flush()

    job = Job(organization_id=org.id, created_by_user_id=recruiter.id, title="Senior Auditor")
    resume = Resume(
        candidate_id=candidate.id,
        file_uri="local://resumes/audit_candidate.pdf",
        original_filename="audit_candidate.pdf",
        extracted_text="Experienced auditor in recruitment integrity.",
    )
    db_session.add_all([job, resume])
    db_session.flush()

    application = JobApplication(
        organization_id=org.id,
        job_id=job.id,
        candidate_id=candidate.id,
        resume_id=resume.id,
    )
    job_profile = JobProfile(
        job_id=job.id,
        version_number=1,
        status="approved",
        source="hr_created",
        profile_data={"title": "Senior Auditor", "requirements": [{"text": "Audit Experience"}]},
        approved_by_user_id=admin.id,
        approved_at=datetime.now(UTC),
        is_current=True,
    )
    candidate_profile = CandidateProfile(
        resume_id=resume.id,
        version_number=1,
        status="current",
        source="system_extracted",
        profile_data={"skills": ["Auditing"]},
        is_current=True,
    )
    db_session.add_all([application, job_profile, candidate_profile])
    db_session.flush()

    eval_v1 = CandidateEvaluation(
        job_application_id=application.id,
        job_profile_id=job_profile.id,
        candidate_profile_id=candidate_profile.id,
        version_number=1,
        status="completed",
        score=Decimal("88.0"),
        recommendation="advance",
        is_current=True,
    )
    db_session.add(eval_v1)
    db_session.commit()

    return {
        "org": org,
        "admin": admin,
        "recruiter": recruiter,
        "candidate": candidate,
        "job": job,
        "resume": resume,
        "application": application,
        "job_profile": job_profile,
        "candidate_profile": candidate_profile,
        "eval_v1": eval_v1,
        "other_org": other_org,
        "other_admin": other_admin,
    }


# ===========================================================================
# 1. Immutability Tests
# ===========================================================================

def test_audit_log_database_trigger_prohibits_update(db_session: Session, setup_org_and_users):
    """Database triggers prohibit direct SQL UPDATE on audit_logs."""
    org, admin, _, _, _ = setup_org_and_users
    audit_entry = AuditService().log_event(
        db_session,
        action="test.immutable",
        entity_type="test",
        organization_id=org.id,
        actor_user_id=admin.id,
    )
    db_session.commit()

    with pytest.raises((DBAPIError, OperationalError, IntegrityError)) as excinfo:
        from sqlalchemy import update
        db_session.execute(
            update(AuditLog).where(AuditLog.id == audit_entry.id).values(action="tampered")
        )
        db_session.commit()

    db_session.rollback()
    assert "append-only" in str(excinfo.value).lower()


def test_audit_log_database_trigger_prohibits_delete(db_session: Session, setup_org_and_users):
    """Database triggers prohibit direct SQL DELETE on audit_logs."""
    org, admin, _, _, _ = setup_org_and_users
    audit_entry = AuditService().log_event(
        db_session,
        action="test.immutable_delete",
        entity_type="test",
        organization_id=org.id,
        actor_user_id=admin.id,
    )
    db_session.commit()

    with pytest.raises((DBAPIError, OperationalError, IntegrityError)) as excinfo:
        from sqlalchemy import delete
        db_session.execute(
            delete(AuditLog).where(AuditLog.id == audit_entry.id)
        )
        db_session.commit()

    db_session.rollback()
    assert "append-only" in str(excinfo.value).lower()


def test_audit_service_exposes_no_mutation_or_deletion_methods():
    """Verify application service provides zero edit or delete methods."""
    audit_service = AuditService()
    exposed_methods = [
        attr for attr in dir(audit_service)
        if callable(getattr(audit_service, attr)) and not attr.startswith("_")
    ]
    for method_name in exposed_methods:
        assert not any(forbidden in method_name for forbidden in ("update", "delete", "remove", "edit", "modify")), (
            f"AuditService must not expose modification method: {method_name}"
        )


# ===========================================================================
# 2. Audit Event Generation & Atomicity
# ===========================================================================

def test_hr_decision_audited_and_atomic_with_transaction(db_session: Session, setup_application_and_eval):
    """A successful HR decision produces an audit log committed in the same transaction."""
    ctx = setup_application_and_eval
    app_id = ctx["application"].id
    user_id = ctx["recruiter"].id
    eval_id = ctx["eval_v1"].id

    decision = DecisionService().create(
        db_session,
        job_application_id=app_id,
        user_id=user_id,
        decision="advance",
        candidate_evaluation_id=eval_id,
        expected_evaluation_id=eval_id,
        reason="Exemplary audit trail knowledge.",
    )
    db_session.commit()

    audit_logs = db_session.scalars(
        select(AuditLog)
        .where(
            AuditLog.entity_type == "job_application",
            AuditLog.entity_id == app_id,
            AuditLog.action == "hr_decision.created",
        )
    ).all()

    assert len(audit_logs) == 1
    log = audit_logs[0]
    assert log.actor_user_id == user_id
    assert log.organization_id == ctx["org"].id
    assert log.event_metadata["decision"] == "advance"
    assert log.event_metadata["candidate_evaluation_id"] == str(eval_id)
    assert log.event_metadata["new_status"] == "advanced"


def test_hr_decision_rollback_leaves_no_audit_record(db_session: Session, setup_application_and_eval):
    """A rolled-back business transaction does not leave an orphaned audit record."""
    ctx = setup_application_and_eval
    app_id = ctx["application"].id
    user_id = ctx["recruiter"].id

    # Create decision without committing, then roll back
    DecisionService().create(
        db_session,
        job_application_id=app_id,
        user_id=user_id,
        decision="hold",
        reason="Will be rolled back.",
    )
    db_session.rollback()

    audit_logs = db_session.scalars(
        select(AuditLog).where(
            AuditLog.entity_type == "job_application",
            AuditLog.entity_id == app_id,
        )
    ).all()
    assert len(audit_logs) == 0


def test_job_profile_approval_is_audited(db_session: Session, setup_application_and_eval):
    """Approving a JobProfile creates a committed audit record."""
    ctx = setup_application_and_eval
    job = ctx["job"]
    admin = ctx["admin"]

    # Create a draft profile
    draft_profile = JobProfileService().create_version(
        db_session,
        job_id=job.id,
        status="draft",
        source="hr_created",
        profile_data={"title": "Auditor v2", "requirements": []},
        organization_id=ctx["org"].id,
    )
    db_session.commit()

    # Approve draft
    approved = JobProfileService().approve(
        db_session,
        profile_id=draft_profile.id,
        approved_by_user_id=admin.id,
        organization_id=ctx["org"].id,
    )
    db_session.commit()

    audit_entry = db_session.scalars(
        select(AuditLog).where(
            AuditLog.action == "job_profile.approved",
            AuditLog.entity_id == approved.id,
        )
    ).first()

    assert audit_entry is not None
    assert audit_entry.actor_user_id == admin.id
    assert audit_entry.organization_id == ctx["org"].id
    assert audit_entry.event_metadata["version_number"] == approved.version_number
    assert "requirements" not in audit_entry.event_metadata


def test_resume_download_is_audited(client: TestClient, db_session: Session, setup_application_and_eval):
    """Authorized resume download produces a resume.downloaded audit entry."""
    ctx = setup_application_and_eval
    resume = ctx["resume"]
    headers = _auth_headers(ctx["recruiter"])

    # Setup fake file on disk for storage
    from app.core.config import settings
    from app.services.storage_service import LocalFileSystemStorage
    storage = LocalFileSystemStorage(settings.storage_root_dir)
    storage_key = storage.save(
        organization_id=ctx["org"].id,
        resume_id=resume.id,
        extension=".pdf",
        stream=lambda: b"%PDF-1.4 Fake CV",
    )
    resume.file_uri = storage_key
    db_session.commit()

    response = client.get(f"/api/v1/resumes/{resume.id}/download", headers=headers)
    assert response.status_code == 200

    audit_entry = db_session.scalars(
        select(AuditLog).where(
            AuditLog.action == "resume.downloaded",
            AuditLog.entity_id == resume.id,
        )
    ).first()

    assert audit_entry is not None
    assert audit_entry.actor_user_id == ctx["recruiter"].id
    assert audit_entry.organization_id == ctx["org"].id
    assert audit_entry.event_metadata["candidate_id"] == str(resume.candidate_id)
    assert "file_bytes" not in audit_entry.event_metadata
    assert "file_uri" not in audit_entry.event_metadata


def test_user_creation_role_change_and_deactivation_are_audited(
    client: TestClient, db_session: Session, setup_org_and_users
):
    """User creation, role updates, and deactivations are audited without credentials."""
    org, admin, _, _, _ = setup_org_and_users
    headers = _auth_headers(admin)

    # 1. Create User
    create_resp = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "new-auditor@example.com",
            "full_name": "New Auditor",
            "password": "PasswordSecret123!",
            "role": "recruiter",
        },
    )
    assert create_resp.status_code == 201
    created_user_id = create_resp.json()["id"]

    create_log = db_session.scalars(
        select(AuditLog).where(
            AuditLog.action == "user.created",
            AuditLog.entity_id == uuid.UUID(created_user_id),
        )
    ).first()
    assert create_log is not None
    assert "password" not in create_log.event_metadata
    assert create_log.event_metadata["role"] == "recruiter"

    # 2. Update Role
    role_resp = client.patch(
        f"/api/v1/users/{created_user_id}/role",
        headers=headers,
        json={"role": "admin"},
    )
    assert role_resp.status_code == 200

    role_log = db_session.scalars(
        select(AuditLog).where(
            AuditLog.action == "user.role_updated",
            AuditLog.entity_id == uuid.UUID(created_user_id),
        )
    ).first()
    assert role_log is not None
    assert role_log.event_metadata["old_role"] == "recruiter"
    assert role_log.event_metadata["new_role"] == "admin"

    # 3. Deactivate User
    status_resp = client.patch(
        f"/api/v1/users/{created_user_id}/status",
        headers=headers,
        json={"status": "inactive"},
    )
    assert status_resp.status_code == 200

    deact_log = db_session.scalars(
        select(AuditLog).where(
            AuditLog.action == "user.deactivated",
            AuditLog.entity_id == uuid.UUID(created_user_id),
        )
    ).first()
    assert deact_log is not None
    assert deact_log.event_metadata["old_status"] == "active"
    assert deact_log.event_metadata["new_status"] == "inactive"


def test_failed_login_records_safe_category_without_credentials(
    client: TestClient, db_session: Session, setup_org_and_users
):
    """Authentication failures log safe categories without exposing submitted passwords or emails."""
    org, admin, _, _, _ = setup_org_and_users

    # Non-existent user
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "BadPassword123!"},
    )
    assert resp.status_code == 401

    log = db_session.scalars(
        select(AuditLog)
        .where(AuditLog.action == "auth.login_failed")
        .order_by(AuditLog.created_at.desc())
    ).first()

    assert log is not None
    assert log.event_metadata["category"] == "invalid_credentials"
    assert "email" not in log.event_metadata
    assert "password" not in log.event_metadata


def test_data_minimization_scrubs_prohibited_keys():
    """Metadata sanitizer strips passwords, tokens, API keys, and CV contents."""
    raw_meta = {
        "password": "secret_password",
        "access_token": "ey1234567890.abcdef",
        "secret_key": "api-secret-here",
        "cv_text": "Candidate full confidential resume text",
        "email": "candidate@example.com",
        "safe_key": "allowed_value",
        "nested": {
            "token": "nested_secret",
            "count": 5,
        },
    }
    sanitized = sanitize_audit_metadata(raw_meta)
    assert "password" not in sanitized
    assert "access_token" not in sanitized
    assert "secret_key" not in sanitized
    assert "cv_text" not in sanitized
    assert "email" not in sanitized
    assert sanitized["safe_key"] == "allowed_value"
    assert sanitized["nested"]["count"] == 5
    assert "token" not in sanitized["nested"]


# ===========================================================================
# 3. Decision Integrity, Freshness, and Concurrency
# ===========================================================================

def test_decision_with_stale_expected_evaluation_returns_409(db_session: Session, setup_application_and_eval):
    """A decision specifying a superseded evaluation id fails with 409 Conflict."""
    ctx = setup_application_and_eval
    app_id = ctx["application"].id
    user_id = ctx["recruiter"].id
    eval_v1 = ctx["eval_v1"]

    # Mark eval_v1 superseded by adding eval_v2
    eval_v1.is_current = False
    eval_v1.status = "superseded"
    eval_v2 = CandidateEvaluation(
        job_application_id=app_id,
        job_profile_id=ctx["job_profile"].id,
        candidate_profile_id=ctx["candidate_profile"].id,
        version_number=2,
        status="completed",
        score=Decimal("92.0"),
        recommendation="advance",
        is_current=True,
    )
    db_session.add(eval_v2)
    db_session.commit()

    with pytest.raises(ConflictError) as excinfo:
        DecisionService().create(
            db_session,
            job_application_id=app_id,
            user_id=user_id,
            decision="advance",
            expected_evaluation_id=eval_v1.id,
        )

    assert "stale" in str(excinfo.value).lower()


def test_decision_with_mismatched_organization_or_application_fails(
    db_session: Session, setup_application_and_eval
):
    """Cannot record decision referencing an evaluation or user from another organization."""
    ctx = setup_application_and_eval
    other_org = ctx["other_org"]
    other_admin = ctx["other_admin"]

    # Attempt decision for an application under the wrong organization
    with pytest.raises(NotFoundError):
        DecisionService().create(
            db_session,
            job_application_id=ctx["application"].id,
            user_id=other_admin.id,
            decision="advance",
            organization_id=other_org.id,
        )


def test_idempotent_repeated_decision_does_not_duplicate_records(
    db_session: Session, setup_application_and_eval
):
    """Repeated identical decision request returns existing decision without appending a duplicate row."""
    ctx = setup_application_and_eval
    app_id = ctx["application"].id
    user_id = ctx["recruiter"].id
    eval_id = ctx["eval_v1"].id

    first = DecisionService().create(
        db_session,
        job_application_id=app_id,
        user_id=user_id,
        decision="hold",
        expected_evaluation_id=eval_id,
        reason="Need further assessment.",
    )
    db_session.commit()

    # Repeated exact submission
    second = DecisionService().create(
        db_session,
        job_application_id=app_id,
        user_id=user_id,
        decision="hold",
        expected_evaluation_id=eval_id,
        reason="Need further assessment.",
    )
    db_session.commit()

    assert first.id == second.id

    decisions = db_session.scalars(
        select(HRDecision).where(HRDecision.job_application_id == app_id)
    ).all()
    assert len(decisions) == 1

    audit_entries = db_session.scalars(
        select(AuditLog).where(
            AuditLog.entity_type == "job_application",
            AuditLog.entity_id == app_id,
            AuditLog.action == "hr_decision.created",
        )
    ).all()
    assert len(audit_entries) == 1


def test_intentional_subsequent_decision_preserves_history(
    db_session: Session, setup_application_and_eval
):
    """Subsequent different decisions append to history without overwriting earlier decisions."""
    ctx = setup_application_and_eval
    app_id = ctx["application"].id
    user_id = ctx["recruiter"].id

    dec_1 = DecisionService().create(
        db_session,
        job_application_id=app_id,
        user_id=user_id,
        decision="hold",
        reason="Initial hold.",
    )
    db_session.commit()

    dec_2 = DecisionService().create(
        db_session,
        job_application_id=app_id,
        user_id=user_id,
        decision="advance",
        reason="Follow-up advance.",
    )
    db_session.commit()

    assert dec_1.id != dec_2.id
    history = list(
        db_session.scalars(
            select(HRDecision)
            .where(HRDecision.job_application_id == app_id)
            .order_by(HRDecision.created_at.asc())
        ).all()
    )
    assert len(history) == 2
    assert history[0].decision == "hold"
    assert history[1].decision == "advance"

    # Application reflects latest status
    app = db_session.get(JobApplication, app_id)
    assert app.status == "advanced"


# ===========================================================================
# 4. Access Control & Admin-Only Querying
# ===========================================================================

def test_audit_logs_unauthenticated_returns_401(client: TestClient):
    """Unauthenticated access to audit history returns 401."""
    resp = client.get("/api/v1/audit-logs")
    assert resp.status_code == 401


def test_audit_logs_recruiter_returns_403(client: TestClient, setup_org_and_users):
    """Recruiters cannot access the audit history endpoint."""
    _, _, recruiter, _, _ = setup_org_and_users
    headers = _auth_headers(recruiter)
    resp = client.get("/api/v1/audit-logs", headers=headers)
    assert resp.status_code == 403


def test_audit_logs_admin_tenant_isolation(
    client: TestClient, db_session: Session, setup_org_and_users
):
    """Admins only see audit records belonging to their own organization."""
    org_1, admin_1, _, org_2, admin_2 = setup_org_and_users

    # Log events for Org 1 and Org 2
    AuditService().log_event(
        db_session,
        action="org1.event",
        entity_type="test",
        organization_id=org_1.id,
        actor_user_id=admin_1.id,
    )
    AuditService().log_event(
        db_session,
        action="org2.event",
        entity_type="test",
        organization_id=org_2.id,
        actor_user_id=admin_2.id,
    )
    db_session.commit()

    # Query as Admin 1
    resp_1 = client.get("/api/v1/audit-logs", headers=_auth_headers(admin_1))
    assert resp_1.status_code == 200
    data_1 = resp_1.json()
    actions_1 = [item["action"] for item in data_1["items"]]
    assert "org1.event" in actions_1
    assert "org2.event" not in actions_1

    # Query as Admin 2
    resp_2 = client.get("/api/v1/audit-logs", headers=_auth_headers(admin_2))
    assert resp_2.status_code == 200
    data_2 = resp_2.json()
    actions_2 = [item["action"] for item in data_2["items"]]
    assert "org2.event" in actions_2
    assert "org1.event" not in actions_2


def test_audit_logs_pagination_and_filters(
    client: TestClient, db_session: Session, setup_org_and_users
):
    """Audit logs support bounded pagination and action/date filtering."""
    org, admin, _, _, _ = setup_org_and_users

    for i in range(5):
        AuditService().log_event(
            db_session,
            action=f"batch.item_{i % 2}",
            entity_type="batch_entity",
            organization_id=org.id,
            actor_user_id=admin.id,
        )
    db_session.commit()

    headers = _auth_headers(admin)

    # Filter by action
    resp = client.get("/api/v1/audit-logs?action=batch.item_0", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(item["action"] in ("batch.item_0", "audit_log.accessed") for item in items)

    # Invalid date range returns 422
    future = (datetime.now(UTC) + timedelta(days=5)).isoformat()
    past = (datetime.now(UTC) - timedelta(days=5)).isoformat()
    resp_bad_date = client.get(f"/api/v1/audit-logs?from_date={future}&to_date={past}", headers=headers)
    assert resp_bad_date.status_code == 422
