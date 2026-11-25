from __future__ import annotations

import asyncio
import uuid

from app.core.config import settings
from app.models import Organization, SourcingCandidate, SourcingSearch, User
from app.services.sourcing_service import (
    MAX_RESULTS_PER_SEARCH,
    ApifySourcingProvider,
    candidate_from_provider_item,
)


def _record(db_session, *, query_text="backend engineer in cairo"):
    organization = Organization(name=f"Org {uuid.uuid4()}")
    user = User(organization=organization, email=f"{uuid.uuid4()}@example.test", full_name="HR")
    db_session.add_all([organization, user])
    db_session.flush()
    record = SourcingSearch(
        organization_id=organization.id,
        requested_by_user_id=user.id,
        query_text=query_text,
        provider="apify",
        actor_id="harvestapi/linkedin-profile-search",
        status="queued",
    )
    db_session.add(record)
    db_session.flush()
    return record, organization, user


class _Response:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def _mock_client(calls):
    class MockClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, *, headers, json):
            calls.append(("post", url, headers, json))
            return _Response({"data": {"id": "run-1", "defaultDatasetId": "returned-dataset"}})

        async def get(self, url, *, headers, params=None):
            calls.append(("get", url, headers, params))
            if "/actor-runs/" in url:
                return _Response(
                    {"data": {"status": "SUCCEEDED", "defaultDatasetId": "returned-dataset"}}
                )
            return _Response(
                [
                    {
                        "fullName": "Omar Example",
                        "headline": "Senior Backend Engineer",
                        "location": "Cairo, Egypt",
                        "currentJobTitle": "Backend Engineer",
                        "currentCompany": "Example Co",
                        "url": "https://www.linkedin.com/in/omar-example/",
                    }
                ]
            )

    return MockClient


def test_actor_run_starts_and_imports_candidates_on_refresh(db_session, monkeypatch):
    record, organization, user = _record(db_session)
    monkeypatch.setattr(settings, "apify_api_token", "unit-test-token")
    monkeypatch.setattr(settings, "apify_sourcing_actor_id", "harvestapi/linkedin-profile-search")
    calls = []
    monkeypatch.setattr("app.services.sourcing_service.httpx.AsyncClient", _mock_client(calls))

    provider = ApifySourcingProvider()
    asyncio.run(provider.start(record))
    assert record.status == "running"
    assert record.actor_run_id == "run-1"
    assert calls[0][1].endswith("/acts/harvestapi~linkedin-profile-search/runs")
    assert calls[0][3]["searchQuery"] == record.query_text
    assert calls[0][3]["maxItems"] == MAX_RESULTS_PER_SEARCH

    asyncio.run(provider.refresh(record, db_session))
    db_session.flush()

    assert record.status == "succeeded"
    candidates = db_session.query(SourcingCandidate).filter_by(search_id=record.id).all()
    assert len(candidates) == 1
    assert candidates[0].full_name == "Omar Example"
    assert candidates[0].current_company == "Example Co"
    assert candidates[0].status == "suggested"


def test_candidate_mapper_ignores_malformed_items():
    assert candidate_from_provider_item(None) is None
    assert candidate_from_provider_item({}) is None
    assert candidate_from_provider_item({"fullName": "   "}) is None
    candidate = candidate_from_provider_item(
        {"fullName": "Sara Test", "profileUrl": "https://www.linkedin.com/in/sara-test/"}
    )
    assert candidate is not None
    assert candidate.full_name == "Sara Test"
    assert candidate.profile_url == "https://www.linkedin.com/in/sara-test/"


def test_failed_actor_run_marks_search_failed(db_session, monkeypatch):
    record, _, _ = _record(db_session)
    monkeypatch.setattr(settings, "apify_api_token", "unit-test-token")
    record.actor_run_id = "run-1"
    record.status = "running"

    class FailedClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, *, headers, params=None):
            return _Response({"data": {"status": "FAILED"}})

    monkeypatch.setattr("app.services.sourcing_service.httpx.AsyncClient", FailedClient)
    asyncio.run(ApifySourcingProvider().refresh(record, db_session))
    assert record.status == "failed"
    assert record.error_code is not None


def test_candidate_mapper_handles_real_harvestapi_search_shape():
    # Shape observed from a live harvestapi/linkedin-profile-search run
    # (Short mode): firstName/lastName, location as object, currentPosition list.
    candidate = candidate_from_provider_item(
        {
            "firstName": "Ahmed",
            "lastName": "Taha",
            "headline": "Backend Engineer @ Bosta",
            "location": {
                "linkedinText": "Giza, Al Jizah, Egypt",
                "parsed": {"text": "Giza, Egypt"},
            },
            "currentPosition": [{"position": "Backend Engineer", "companyName": "Bosta"}],
            "linkedinUrl": "https://www.linkedin.com/in/ahmed-taha1",
        }
    )
    assert candidate is not None
    assert candidate.full_name == "Ahmed Taha"
    assert candidate.location == "Giza, Al Jizah, Egypt"
    assert candidate.current_title == "Backend Engineer"
    assert candidate.current_company == "Bosta"
    assert candidate.profile_url == "https://www.linkedin.com/in/ahmed-taha1"


def test_candidate_mapper_extracts_email_from_provider_list():
    candidate = candidate_from_provider_item(
        {
            "firstName": "Sara",
            "lastName": "Test",
            "emails": [{"email": "sara@example.com"}, "ignored"],
            "linkedinUrl": "https://www.linkedin.com/in/sara-test/",
        }
    )
    assert candidate is not None
    assert candidate.email == "sara@example.com"
    assert candidate.phone is None


def test_candidate_mapper_prefers_validated_email_entry():
    candidate = candidate_from_provider_item(
        {
            "firstName": "A",
            "lastName": "B",
            "emails": [
                {"email": "guess@example.com", "validEmailServer": False, "qualityScore": 40},
                {"email": "real@example.com", "validEmailServer": True, "qualityScore": 90},
            ],
        }
    )
    assert candidate is not None
    assert candidate.email == "real@example.com"


def test_enrich_merges_profile_details_and_email(db_session, monkeypatch):
    record, _, _ = _record(db_session)
    monkeypatch.setattr(settings, "apify_api_token", "unit-test-token")
    monkeypatch.setattr(
        settings, "apify_sourcing_enrichment_actor_id", "harvestapi/linkedin-profile-scraper"
    )
    candidate = SourcingCandidate(
        search_id=record.id,
        full_name="Ahmed Taha",
        profile_url="https://www.linkedin.com/in/ahmed-taha1",
        status="suggested",
    )
    db_session.add(candidate)
    db_session.flush()
    calls = []

    class EnrichClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, *, headers, json):
            calls.append(("post", url, json))
            return _Response({"data": {"id": "run-e1"}})

        async def get(self, url, *, headers, params=None):
            if "/actor-runs/" in url:
                return _Response({"data": {"status": "SUCCEEDED", "defaultDatasetId": "ds-e1"}})
            return _Response(
                [
                    {
                        "firstName": "Ahmed",
                        "lastName": "Taha",
                        "headline": "Backend Engineer @ Bosta",
                        "emails": [
                            {
                                "email": "ahmed.taha@bosta.co",
                                "validEmailServer": True,
                                "qualityScore": 60,
                            }
                        ],
                    }
                ]
            )

    monkeypatch.setattr("app.services.sourcing_service.httpx.AsyncClient", EnrichClient)
    provider = ApifySourcingProvider()
    provider.enrich_poll_seconds = 0
    found = asyncio.run(provider.enrich(candidate))

    assert found is True
    assert candidate.email == "ahmed.taha@bosta.co"
    assert candidate.headline == "Backend Engineer @ Bosta"
    assert calls[0][1].endswith("/acts/harvestapi~linkedin-profile-scraper/runs")
    assert calls[0][2]["urls"] == ["https://www.linkedin.com/in/ahmed-taha1"]
    assert "email search" in calls[0][2]["profileScraperMode"]


def test_enrich_returns_false_without_profile_url(db_session):
    candidate = SourcingCandidate(search_id=None, status="suggested")
    assert asyncio.run(ApifySourcingProvider().enrich(candidate)) is False
