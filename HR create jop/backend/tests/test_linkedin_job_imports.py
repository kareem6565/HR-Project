from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest

from app.core.config import settings
from app.models import LinkedInJobImport, Organization, User
from app.services.linkedin_job_import_service import (
    LinkedInJobImportService,
    canonicalize_linkedin_job_url,
)


def _record(db_session, *, source_url="https://www.linkedin.com/jobs/view/1234567890/"):
    organization = Organization(name=f"Org {uuid.uuid4()}")
    user = User(organization=organization, email=f"{uuid.uuid4()}@example.test", full_name="HR")
    db_session.add_all([organization, user])
    db_session.flush()
    record = LinkedInJobImport(
        organization_id=organization.id,
        requested_by_user_id=user.id,
        source_url=source_url,
        source_job_id="1234567890",
        actor_id="fetch_cat/linkedin-jobs-scraper",
        status="queued",
    )
    db_session.add(record)
    db_session.flush()
    return record, organization, user


def test_canonicalize_accepts_job_link_and_discards_tracking_query():
    assert canonicalize_linkedin_job_url(
        "https://www.linkedin.com/jobs/view/1234567890/?trk=public_jobs"
    ) == ("https://www.linkedin.com/jobs/view/1234567890/", "1234567890")


@pytest.mark.parametrize(
    "url",
    [
        "http://www.linkedin.com/jobs/view/1234567890/",
        "https://evil.example/jobs/view/1234567890/",
        "https://linkedin.com/jobs/search/?keywords=engineer",
        "https://www.linkedin.com@evil.example/jobs/view/1234567890/",
    ],
)
def test_canonicalize_rejects_non_job_or_untrusted_urls(url):
    with pytest.raises(ValueError):
        canonicalize_linkedin_job_url(url)


def test_actor_run_uses_fixed_config_and_dynamically_follows_default_dataset(
    db_session, monkeypatch
):
    record, _, _ = _record(db_session)
    monkeypatch.setattr(settings, "apify_api_token", "unit-test-token")
    monkeypatch.setattr(settings, "apify_linkedin_jobs_actor_id", "fetch_cat/linkedin-jobs-scraper")
    calls = []

    class Response:
        def __init__(self, payload, status_code=200):
            self.payload = payload
            self.status_code = status_code

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class MockClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, *, headers, json):
            calls.append(("post", url, headers, json))
            return Response({"data": {"id": "run-1", "defaultDatasetId": "returned-dataset"}})

        async def get(self, url, *, headers, params=None):
            calls.append(("get", url, headers, params))
            if "/actor-runs/" in url:
                return Response(
                    {"data": {"status": "SUCCEEDED", "defaultDatasetId": "returned-dataset"}}
                )
            return Response(
                [
                    {
                        "jobId": "1234567890",
                        "jobUrl": "https://www.linkedin.com/jobs/view/1234567890/",
                        "title": "Backend Engineer",
                        "companyName": "Example Co",
                        "description": "Build reliable services.",
                        "location": "Remote",
                        "workplaceType": "Remote",
                    }
                ]
            )

    monkeypatch.setattr("app.services.linkedin_job_import_service.httpx.AsyncClient", MockClient)
    service = LinkedInJobImportService()
    asyncio.run(service.start_actor(record))
    assert record.status == "running"
    asyncio.run(service.refresh(record))

    assert record.status == "succeeded"
    assert record.result_data["title"] == "Backend Engineer"
    assert calls[0][1].endswith("/acts/fetch_cat~linkedin-jobs-scraper/runs")
    assert calls[0][3] == {
        "startUrls": [{"url": record.source_url}],
        "keywords": [],
        "maxItems": 1,
        "includeDetails": True,
    }
    assert calls[-1][1].endswith("/datasets/returned-dataset/items")
    assert all(call[2]["Authorization"] == "Bearer unit-test-token" for call in calls)


def test_import_lookup_is_scoped_to_organization(db_session):
    record, _, _ = _record(db_session)
    other_org = Organization(name=f"Other {uuid.uuid4()}")
    db_session.add(other_org)
    db_session.flush()

    assert (
        LinkedInJobImportService.get_by_id(
            db_session, import_id=record.id, organization_id=other_org.id
        )
        is None
    )


def test_ambiguous_actor_start_timeout_is_not_retried(db_session, monkeypatch):
    record, _, _ = _record(db_session)
    monkeypatch.setattr(settings, "apify_api_token", "unit-test-token")

    class MockClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            raise httpx.ReadTimeout("local mock timeout")

    monkeypatch.setattr("app.services.linkedin_job_import_service.httpx.AsyncClient", MockClient)
    asyncio.run(LinkedInJobImportService().start_actor(record))

    assert record.status == "failed"
    assert record.error_code == "start_unknown"
    assert record.actor_run_id is None


@pytest.mark.parametrize(
    ("items", "expected_code"),
    [
        ([], "empty_result"),
        (
            [
                {
                    "jobId": "1234567890",
                    "jobUrl": "https://www.linkedin.com/jobs/view/1234567890/",
                    "title": "Engineer",
                }
            ],
            "missing_description",
        ),
        ([{"title": "Engineer", "description": "Text without required ids"}], "malformed_result"),
    ],
)
def test_refresh_reports_empty_or_missing_description_without_persisting_a_job(
    db_session, monkeypatch, items, expected_code
):
    from datetime import UTC, datetime

    record, _, _ = _record(db_session)
    record.status = "running"
    record.actor_run_id = "run-1"
    record.last_checked_at = datetime(2000, 1, 1, tzinfo=UTC)
    monkeypatch.setattr(settings, "apify_api_token", "unit-test-token")

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class MockClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, *, headers, params=None):
            if "/actor-runs/" in url:
                return Response({"data": {"status": "SUCCEEDED", "defaultDatasetId": "dynamic-id"}})
            return Response(items)

    monkeypatch.setattr("app.services.linkedin_job_import_service.httpx.AsyncClient", MockClient)
    asyncio.run(LinkedInJobImportService().refresh(record))

    assert record.status == "failed"
    assert record.error_code == expected_code
    assert record.result_data is None
