from __future__ import annotations

import uuid

from app.models import Job, Organization, SourcingCandidate, SourcingSearch, User
from app.services.sourcing_outreach_service import (
    _parse_ai_output,
    build_ai_personalized_draft,
    build_template_draft,
)


def _candidate(db_session):
    organization = Organization(name="Acme Egypt")
    user = User(
        organization=organization, email=f"{uuid.uuid4()}@example.test", full_name="HR Lead"
    )
    db_session.add_all([organization, user])
    db_session.flush()
    job = Job(
        organization_id=organization.id,
        title="Senior Backend Engineer",
        description_text="Build reliable Python services for fintech.",
        created_by_user_id=user.id,
    )
    db_session.add(job)
    db_session.flush()
    search = SourcingSearch(
        organization_id=organization.id,
        requested_by_user_id=user.id,
        job_id=job.id,
        query_text="backend engineer",
        provider="apify",
        actor_id="a/b",
        status="succeeded",
    )
    db_session.add(search)
    db_session.flush()
    candidate = SourcingCandidate(
        search_id=search.id,
        full_name="Ahmed Taha",
        headline="Backend Engineer @ Bosta",
        current_title="Backend Engineer",
        current_company="Bosta",
        email="ahmed@example.com",
        status="suggested",
    )
    db_session.add(candidate)
    db_session.flush()
    return candidate, job, organization, user


def test_template_draft_uses_candidate_and_job_context(db_session):
    candidate, job, organization, user = _candidate(db_session)
    draft = build_template_draft(
        candidate=candidate,
        job=job,
        organization_name=organization.name,
        sender_name=user.full_name,
    )
    assert draft["personalized"] is False
    assert "Senior Backend Engineer" in draft["subject"]
    assert "Acme Egypt" in draft["subject"]
    assert draft["body"].startswith("Hi Ahmed,")
    assert "Backend Engineer at Bosta" in draft["body"]
    assert "Build reliable Python services" in draft["body"]
    assert draft["body"].rstrip().endswith("Acme Egypt")


def test_ai_personalize_falls_back_to_template_on_provider_failure(db_session, monkeypatch):
    candidate, job, organization, user = _candidate(db_session)

    class BrokenProvider:
        def generate_text(self, request):
            raise RuntimeError("provider down")

    monkeypatch.setattr(
        "app.services.sourcing_outreach_service.get_provider", lambda settings: BrokenProvider()
    )
    draft = build_ai_personalized_draft(
        candidate=candidate,
        job=job,
        organization_name=organization.name,
        sender_name=user.full_name,
    )
    assert draft["personalized"] is False
    assert "Senior Backend Engineer" in draft["subject"]


def test_ai_personalize_uses_provider_output(db_session, monkeypatch):
    candidate, job, organization, user = _candidate(db_session)

    class Result:
        text = "Subject: Your Bosta work caught my eye\n\nHi Ahmed, loved your backend work."

    class GoodProvider:
        def generate_text(self, request):
            assert "Ahmed Taha" in request.input
            assert "Senior Backend Engineer" in request.input
            return Result()

    monkeypatch.setattr(
        "app.services.sourcing_outreach_service.get_provider", lambda settings: GoodProvider()
    )
    draft = build_ai_personalized_draft(
        candidate=candidate,
        job=job,
        organization_name=organization.name,
        sender_name=user.full_name,
    )
    assert draft["personalized"] is True
    assert draft["subject"] == "Your Bosta work caught my eye"
    assert draft["body"].startswith("Hi Ahmed")


def test_parse_ai_output_without_subject_line_keeps_fallback():
    parsed = _parse_ai_output("Just a body.", "Fallback subject")
    assert parsed == {"subject": "Fallback subject", "body": "Just a body."}
