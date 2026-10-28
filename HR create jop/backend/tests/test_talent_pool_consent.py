from __future__ import annotations

import hashlib
import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import app
from app.models import (
    Candidate,
    HRDecision,
    Job,
    JobApplication,
    Organization,
    Resume,
    TalentPoolConsent,
    User,
)
from app.services.errors import NotFoundError
from app.services.talent_pool_consent_service import TalentPoolConsentService
from app.ai.tools.pipeline_tools import _get_talent_pool


@pytest.fixture()
def client(db_session: Session) -> Generator[httpx.Client, None, None]:
    connection = db_session.connection()
    db_session.bind = connection

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def _org_user_candidate(db: Session, suffix: str) -> tuple[Organization, User, Candidate]:
    organization = Organization(name=f"Consent Org {suffix}")
    db.add(organization)
    db.flush()
    user = User(
        organization_id=organization.id,
        email=f"consent-{suffix}@example.com",
        full_name="Consent HR",
        role="recruiter",
    )
    candidate = Candidate(
        organization_id=organization.id,
        full_name="Synthetic Candidate",
        email=f"candidate-{suffix}@example.test",
    )
    db.add_all([user, candidate])
    db.flush()
    return organization, user, candidate


def _headers(org: Organization, user: User) -> dict[str, str]:
    return {"X-User-Id": str(user.id), "X-Organization-Id": str(org.id)}


def test_link_is_hashed_one_use_and_acceptance_expires_after_twelve_calendar_months(
    db_session: Session,
) -> None:
    organization, user, candidate = _org_user_candidate(db_session, "accept")
    service = TalentPoolConsentService()
    before = datetime.now(UTC)
    token, link_expires_at = service.create_link(
        db_session,
        candidate_id=candidate.id,
        organization_id=organization.id,
        actor_user_id=user.id,
    )
    record = db_session.query(TalentPoolConsent).one()

    assert record.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert record.token_hash != token
    assert timedelta(days=6, hours=23) < link_expires_at - before < timedelta(days=7, minutes=1)
    preview = service.preview(db_session, token=token)
    assert "12 months" in preview["consent_text"]
    assert candidate.full_name not in str(preview)

    granted_at = datetime.now(UTC)
    expires_at = service.respond(db_session, token=token, decision="accepted")
    assert record.response == "accepted"
    assert record.granted_at is not None
    assert record.consent_text == preview["consent_text"]
    assert record.consent_version == preview["consent_version"]
    assert expires_at.year == granted_at.year + 1
    assert (expires_at.month, expires_at.day) == (granted_at.month, granted_at.day)
    with pytest.raises(NotFoundError):
        service.preview(db_session, token=token)


def test_declined_and_expired_links_cannot_be_reused(db_session: Session) -> None:
    organization, user, candidate = _org_user_candidate(db_session, "decline")
    service = TalentPoolConsentService()
    declined_token, _ = service.create_link(
        db_session,
        candidate_id=candidate.id,
        organization_id=organization.id,
        actor_user_id=user.id,
    )
    assert service.respond(db_session, token=declined_token, decision="declined") is None
    declined = db_session.query(TalentPoolConsent).filter_by(response="declined").one()
    assert declined.granted_at is None
    assert declined.consent_expires_at is None
    with pytest.raises(NotFoundError):
        service.respond(db_session, token=declined_token, decision="accepted")

    expired_token, _ = service.create_link(
        db_session,
        candidate_id=candidate.id,
        organization_id=organization.id,
        actor_user_id=user.id,
    )
    expired = (
        db_session.query(TalentPoolConsent)
        .filter(TalentPoolConsent.token_hash == hashlib.sha256(expired_token.encode()).hexdigest())
        .one()
    )
    expired.link_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.flush()
    with pytest.raises(NotFoundError):
        service.preview(db_session, token=expired_token)


def test_talent_pool_requires_explicit_consent_and_withdrawal_keeps_original_decision(
    client: httpx.Client, db_session: Session
) -> None:
    organization, user, candidate = _org_user_candidate(db_session, "api")
    job = Job(organization_id=organization.id, created_by_user_id=user.id, title="Backend")
    resume = Resume(candidate_id=candidate.id, file_uri=f"local://{uuid.uuid4()}.pdf")
    db_session.add_all([job, resume])
    db_session.flush()
    application = JobApplication(
        organization_id=organization.id,
        job_id=job.id,
        candidate_id=candidate.id,
        resume_id=resume.id,
        status="hold",
    )
    db_session.add(application)
    db_session.flush()
    decision = HRDecision(
        job_application_id=application.id,
        user_id=user.id,
        decision="hold",
        reason="Synthetic test decision",
    )
    db_session.add(decision)
    db_session.flush()

    headers = _headers(organization, user)
    assert client.get("/api/v1/talent-pool", headers=headers).json() == []
    assert _get_talent_pool(
        db_session,
        organization_id=organization.id,
        user_id=user.id,
    )["total"] == 0
    link_response = client.post(
        f"/api/v1/candidates/{candidate.id}/talent-pool-consent-link", headers=headers
    )
    assert link_response.status_code == 201
    token = link_response.json()["token"]
    preview = client.post(
        "/api/v1/candidate-portal/talent-pool-consent/preview", json={"token": token}
    )
    assert preview.status_code == 200
    assert candidate.full_name not in preview.text
    accepted = client.post(
        "/api/v1/candidate-portal/talent-pool-consent/respond",
        json={"token": token, "decision": "accepted", "self_attested": True},
    )
    assert accepted.status_code == 200
    assert client.get("/api/v1/talent-pool", headers=headers).json()[0]["application_id"] == str(
        application.id
    )
    assert _get_talent_pool(
        db_session,
        organization_id=organization.id,
        user_id=user.id,
    )["total"] == 1

    reused = client.post(
        "/api/v1/candidate-portal/talent-pool-consent/respond",
        json={"token": token, "decision": "declined", "self_attested": True},
    )
    assert reused.status_code == 404

    consent_record = db_session.query(TalentPoolConsent).filter_by(response="accepted").one()
    consent_record.consent_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.flush()
    assert client.get("/api/v1/talent-pool", headers=headers).json() == []
    assert _get_talent_pool(
        db_session,
        organization_id=organization.id,
        user_id=user.id,
    )["total"] == 0

    renewal_link = client.post(
        f"/api/v1/candidates/{candidate.id}/talent-pool-consent-link", headers=headers
    ).json()
    renewed = client.post(
        "/api/v1/candidate-portal/talent-pool-consent/respond",
        json={"token": renewal_link["token"], "decision": "accepted", "self_attested": True},
    )
    assert renewed.status_code == 200
    withdrawn = client.post(
        f"/api/v1/candidates/{candidate.id}/talent-pool-consent/withdraw",
        headers=headers,
        json={"candidate_requested": True},
    )
    assert withdrawn.status_code == 200
    assert withdrawn.json()["withdrawn"] is True
    assert client.get("/api/v1/talent-pool", headers=headers).json() == []
    assert _get_talent_pool(
        db_session,
        organization_id=organization.id,
        user_id=user.id,
    )["total"] == 0
    assert db_session.get(JobApplication, application.id).status == "hold"
    assert db_session.get(HRDecision, decision.id).decision == "hold"


def test_consent_link_and_talent_pool_are_organization_scoped(
    client: httpx.Client, db_session: Session
) -> None:
    organization, user, candidate = _org_user_candidate(db_session, "owner")
    other_organization, other_user, _other_candidate = _org_user_candidate(db_session, "other")
    response = client.post(
        f"/api/v1/candidates/{candidate.id}/talent-pool-consent-link",
        headers=_headers(other_organization, other_user),
    )
    assert response.status_code == 404

    token, _ = TalentPoolConsentService().create_link(
        db_session,
        candidate_id=candidate.id,
        organization_id=organization.id,
        actor_user_id=user.id,
    )
    assert client.post(
        "/api/v1/candidate-portal/talent-pool-consent/preview", json={"token": token}
    ).status_code == 200
    assert client.get("/api/v1/talent-pool", headers=_headers(other_organization, other_user)).json() == []
