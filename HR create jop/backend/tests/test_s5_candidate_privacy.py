from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Candidate,
    HRDecision,
    Interview,
    Job,
    JobApplication,
    Organization,
    PipelineStageTransition,
    Resume,
    TalentPoolConsent,
    User,
)
from app.services.candidate_privacy_service import CandidatePrivacyService
from app.services.errors import InvalidStateError, NotFoundError


class RecordingStorage:
    def __init__(self):
        self.deleted: list[str] = []

    def delete(self, *, file_uri: str) -> None:
        self.deleted.append(file_uri)


def _candidate_with_records(db: Session):
    org = Organization(name=f"Privacy Org {uuid.uuid4().hex[:8]}")
    db.add(org)
    db.flush()
    user = User(
        organization_id=org.id, email=f"hr-{uuid.uuid4().hex[:8]}@example.com", full_name="HR"
    )
    db.add(user)
    db.flush()
    job = Job(organization_id=org.id, created_by_user_id=user.id, title="Engineer")
    candidate = Candidate(
        organization_id=org.id,
        full_name="Personal Name",
        email="personal@example.com",
        phone="555-0100",
    )
    db.add_all([job, candidate])
    db.flush()
    resume = Resume(
        candidate_id=candidate.id,
        file_uri=f"resumes/{org.id}/{uuid.uuid4()}.pdf",
        original_filename="personal-cv.pdf",
        extracted_text="private CV content",
    )
    db.add(resume)
    db.flush()
    application = JobApplication(
        organization_id=org.id,
        job_id=job.id,
        candidate_id=candidate.id,
        resume_id=resume.id,
        public_contact_email="personal@example.com",
        github_url="https://github.com/personal",
    )
    db.add(application)
    db.flush()
    decision = HRDecision(
        job_application_id=application.id,
        user_id=user.id,
        decision="reject",
        reason="HR rationale retained",
    )
    interview = Interview(
        organization_id=org.id,
        job_application_id=application.id,
        scheduled_date=date.today(),
        scheduled_time="10:00",
        feedback={"summary": "Interview record retained"},
    )
    transition = PipelineStageTransition(
        organization_id=org.id,
        job_application_id=application.id,
        actor_user_id=user.id,
        from_stage="screening",
        to_stage="review",
        reason_code="process_reopened",
        note="Sensitive HR note with candidate context",
        source="hr",
    )
    db.add_all([decision, interview, transition])
    db.flush()
    return org, user, candidate, resume, application, decision, interview


def test_erasure_anonymizes_candidate_and_keeps_hr_and_interview_records(
    db_session: Session,
) -> None:
    org, user, candidate, resume, application, decision, interview = _candidate_with_records(
        db_session
    )
    original_file_uri = resume.file_uri
    storage = RecordingStorage()

    counts = CandidatePrivacyService().erase_candidate(
        db_session,
        candidate_id=candidate.id,
        organization_id=org.id,
        actor_user_id=user.id,
        storage=storage,
    )
    db_session.flush()

    assert counts["files"] == 1
    assert storage.deleted == [original_file_uri]
    assert candidate.full_name == f"Deleted candidate {candidate.id}"
    assert candidate.email is None and candidate.phone is None
    assert candidate.anonymized_at is not None
    assert resume.extracted_text is None and resume.original_filename is None
    assert resume.file_uri == f"deleted://{resume.id}"
    assert db_session.get(JobApplication, application.id).public_contact_email is None
    assert db_session.get(JobApplication, application.id).github_url is None
    assert db_session.get(HRDecision, decision.id).reason == "HR rationale retained"
    assert db_session.get(Interview, interview.id).feedback == {
        "summary": "Interview record retained"
    }
    scrubbed_transition = db_session.scalar(
        select(PipelineStageTransition).where(
            PipelineStageTransition.organization_id == org.id,
            PipelineStageTransition.job_application_id == application.id,
        )
    )
    assert scrubbed_transition.note is None
    assert counts["pipeline_notes_scrubbed"] == 1
    audit = db_session.scalar(select(AuditLog).where(AuditLog.action == "candidate.data_erased"))
    assert audit.entity_id == candidate.id
    assert audit.organization_id == org.id
    assert all(isinstance(value, int) for value in audit.event_metadata["counts"].values())
    assert "Personal Name" not in str(audit.event_metadata)
    assert "personal@example.com" not in str(audit.event_metadata)

    repeated = CandidatePrivacyService().erase_candidate(
        db_session, candidate_id=candidate.id, organization_id=org.id, storage=storage
    )
    assert repeated == {"already_anonymized": True, "candidates": 0}
    assert len(storage.deleted) == 1


def test_erasure_is_org_scoped_and_honors_legal_hold(db_session: Session) -> None:
    org, _, candidate, *_ = _candidate_with_records(db_session)
    other_org = Organization(name="Other privacy org")
    db_session.add(other_org)
    db_session.flush()

    with pytest.raises(NotFoundError):
        CandidatePrivacyService().erase_candidate(
            db_session, candidate_id=candidate.id, organization_id=other_org.id
        )
    candidate.legal_hold = True
    with pytest.raises(InvalidStateError):
        CandidatePrivacyService().erase_candidate(
            db_session, candidate_id=candidate.id, organization_id=org.id
        )
    assert candidate.anonymized_at is None


def test_retention_candidate_requires_all_applications_rejected(db_session: Session) -> None:
    org, user, candidate, resume, application, decision, _ = _candidate_with_records(db_session)
    old = datetime.now(UTC) - timedelta(days=370)
    decision.created_at = old
    org.rejected_retention_months = 12
    db_session.flush()
    eligible = CandidatePrivacyService().eligible_candidates(db_session, now=datetime.now(UTC))
    assert [item.candidate_id for item in eligible] == [candidate.id]

    decision.decision = "hold"
    db_session.flush()
    assert CandidatePrivacyService().eligible_candidates(db_session, now=datetime.now(UTC)) == []


def test_retention_uses_org_defaults_and_consent_renewal(db_session: Session) -> None:
    org, _, candidate, _, _, decision, _ = _candidate_with_records(db_session)
    now = datetime(2026, 11, 22, tzinfo=UTC)
    org.rejected_retention_months = 12
    org.talent_pool_retention_months = 24
    decision.created_at = datetime(2024, 10, 1, tzinfo=UTC)
    consent = TalentPoolConsent(
        organization_id=org.id,
        candidate_id=candidate.id,
        token_hash=uuid.uuid4().hex,
        link_expires_at=now,
        response="accepted",
        granted_at=datetime(2024, 10, 1, tzinfo=UTC),
        consent_expires_at=datetime(2025, 10, 1, tzinfo=UTC),
    )
    db_session.add(consent)
    db_session.flush()
    assert org.rejected_retention_months == 12
    assert org.talent_pool_retention_months == 24
    assert [
        item.candidate_id
        for item in CandidatePrivacyService().eligible_candidates(db_session, now=now)
    ] == [candidate.id]

    renewal = TalentPoolConsent(
        organization_id=org.id,
        candidate_id=candidate.id,
        token_hash=uuid.uuid4().hex,
        link_expires_at=now,
        response="accepted",
        granted_at=datetime(2025, 12, 1, tzinfo=UTC),
        consent_expires_at=datetime(2026, 12, 1, tzinfo=UTC),
    )
    db_session.add(renewal)
    db_session.flush()
    assert CandidatePrivacyService().eligible_candidates(db_session, now=now) == []


def test_retention_dry_run_respects_per_run_cap(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr("app.services.candidate_privacy_service.settings.retention_enabled", False)
    candidates = []
    for _ in range(2):
        org, _, candidate, _, _, decision, _ = _candidate_with_records(db_session)
        decision.created_at = datetime.now(UTC) - timedelta(days=400)
        candidates.append(candidate)
    db_session.flush()

    result = CandidatePrivacyService().run_retention(db_session, dry_run=True, max_deletions=1)
    assert result["enabled"] is False
    assert result["eligible"] == 2
    assert result["selected"] == 1
    assert result["deleted"] == 0
    assert all(candidate.anonymized_at is None for candidate in candidates)
