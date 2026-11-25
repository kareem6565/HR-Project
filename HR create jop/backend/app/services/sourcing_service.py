from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import SourcingCandidate, SourcingSearch

ACTOR_ERRORS = {
    "start_unknown": (
        "Apify did not confirm whether the search started. This search was not retried."
    ),
    "apify_unavailable": "The sourcing provider is temporarily unavailable. Try again shortly.",
    "rate_limited": "The sourcing provider rate-limited this request. Try again later.",
    "actor_failed": "The sourcing provider could not complete this search.",
    "empty_result": "No external profiles matched this search. Try broadening the criteria.",
    "malformed_result": "The sourcing provider returned data in an unsupported format.",
}

# Result cap kept low on purpose: sourcing is pay-per-result and this is the
# first integration pass. Raise once cost behaviour is understood.
MAX_RESULTS_PER_SEARCH = 10


def _first_str(item: dict[str, Any], *keys: str, max_length: int = 500) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:max_length]
    return None


def candidate_from_provider_item(item: dict[str, Any]) -> SourcingCandidate | None:
    """Map one provider result row to a SourcingCandidate (defensive on keys).

    Returns None when the row carries neither a usable name nor headline, which
    keeps malformed provider rows out of the pipeline.
    """

    if not isinstance(item, dict):
        return None
    full_name = _first_str(item, "fullName", "full_name", "name", max_length=255)
    if not full_name:
        parts = [
            p
            for p in (_first_str(item, "firstName"), _first_str(item, "lastName"))
            if p
        ]
        full_name = " ".join(parts)[:255] if parts else None
    headline = _first_str(item, "headline", "occupation", "title", max_length=512)
    if not full_name and not headline:
        return None
    location = _first_str(item, "address", "addressWithCountry", max_length=255)
    raw_location = item.get("location")
    if not location and isinstance(raw_location, str):
        location = raw_location.strip()[:255] or None
    if not location and isinstance(raw_location, dict):
        parsed = raw_location.get("parsed") if isinstance(raw_location.get("parsed"), dict) else {}
        location = _first_str(raw_location, "linkedinText") or _first_str(parsed, "text")
        if location:
            location = location[:255]
    current_title = _first_str(
        item, "currentJobTitle", "current_job_title", "jobTitle", max_length=255
    )
    current_company = _first_str(item, "currentCompany", "companyName", "company", max_length=255)
    current_position = item.get("currentPosition")
    if isinstance(current_position, list) and current_position:
        first = current_position[0]
        if isinstance(first, dict):
            current_title = current_title or _first_str(first, "position", "title", max_length=255)
            current_company = current_company or _first_str(
                first, "companyName", "company", max_length=255
            )
    return SourcingCandidate(
        full_name=full_name,
        headline=headline,
        location=location,
        current_title=current_title,
        current_company=current_company,
        profile_url=_first_str(
            item, "linkedinUrl", "profileUrl", "profile_url", "url", max_length=512
        ),
        provider_payload=item,
        status="suggested",
    )


class SourcingProvider(Protocol):
    """Provider boundary. Swap Apify for a licensed provider here later."""

    name: str

    async def start(self, search: SourcingSearch) -> None: ...

    async def refresh(self, search: SourcingSearch, db: Session) -> None: ...


class ApifySourcingProvider:
    """Apify actor integration (no-login / public-data actors only).

    Mirrors the LinkedIn job-import flow: start an actor run, then poll the run
    and read its default dataset when it succeeds.
    """

    name = "apify"
    api_root = "https://api.apify.com/v2"

    async def start(self, search: SourcingSearch) -> None:
        actor_path = settings.apify_sourcing_actor_id.replace("/", "~")
        search.actor_id = settings.apify_sourcing_actor_id
        timeout = httpx.Timeout(connect=8.0, read=25.0, write=10.0, pool=5.0)
        payload = {
            "searchQuery": search.query_text,
            "maxItems": MAX_RESULTS_PER_SEARCH,
        }
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.api_root}/acts/{actor_path}/runs",
                    headers={"Authorization": f"Bearer {settings.apify_api_token}"},
                    json=payload,
                )
            if response.status_code == 429:
                self._fail(search, "rate_limited")
                return
            response.raise_for_status()
            body = response.json()
            run = body.get("data") if isinstance(body, dict) else None
            run_id = run.get("id") if isinstance(run, dict) else None
            if not isinstance(run_id, str) or not run_id:
                self._fail(search, "start_unknown")
                return
            search.actor_run_id = run_id
            search.status = "running"
            search.error_code = None
            search.last_checked_at = None
        except httpx.TimeoutException:
            # A timed-out POST may have reached Apify; never retry implicitly.
            self._fail(search, "start_unknown")
        except httpx.HTTPStatusError as error:
            self._fail(
                search,
                "rate_limited" if error.response.status_code == 429 else "apify_unavailable",
            )
        except httpx.HTTPError:
            self._fail(search, "apify_unavailable")

    async def refresh(self, search: SourcingSearch, db: Session) -> None:
        if search.status != "running" or not search.actor_run_id:
            return
        now = datetime.now(UTC)
        if search.last_checked_at:
            last_checked = search.last_checked_at
            if last_checked.tzinfo is None:
                last_checked = last_checked.replace(tzinfo=UTC)
            if (now - last_checked).total_seconds() < 2:
                return
        search.last_checked_at = now
        headers = {"Authorization": f"Bearer {settings.apify_api_token}"}
        timeout = httpx.Timeout(connect=8.0, read=15.0, write=10.0, pool=5.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    f"{self.api_root}/actor-runs/{search.actor_run_id}", headers=headers
                )
                response.raise_for_status()
                body = response.json()
                run = body.get("data") if isinstance(body, dict) else None
                if not isinstance(run, dict):
                    raise ValueError("Malformed run metadata")
                run_status = run.get("status")
                if run_status in {"READY", "RUNNING", "TIMING-OUT"}:
                    return
                if run_status != "SUCCEEDED":
                    self._fail(search, "actor_failed")
                    return
                dataset_id = run.get("defaultDatasetId")
                if not isinstance(dataset_id, str) or not dataset_id:
                    raise ValueError("Missing result dataset id")
                items_response = await client.get(
                    f"{self.api_root}/datasets/{dataset_id}/items",
                    params={"limit": MAX_RESULTS_PER_SEARCH, "clean": "true", "format": "json"},
                    headers=headers,
                )
                items_response.raise_for_status()
                items = items_response.json()
                if not isinstance(items, list):
                    raise ValueError("Malformed dataset payload")
                added = 0
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    candidate = candidate_from_provider_item(item)
                    if candidate is None:
                        continue
                    candidate.search_id = search.id
                    db.add(candidate)
                    added += 1
                if added == 0:
                    self._fail(search, "empty_result")
                    return
                search.status = "succeeded"
                search.error_code = None
                search.finished_at = now
        except httpx.HTTPStatusError as error:
            search.error_code = (
                "rate_limited" if error.response.status_code == 429 else "apify_unavailable"
            )
        except httpx.TimeoutException:
            search.error_code = "apify_unavailable"
        except (httpx.HTTPError, ValueError, TypeError):
            self._fail(search, "malformed_result")

    @staticmethod
    def _fail(search: SourcingSearch, code: str) -> None:
        search.status = "failed"
        search.error_code = code
        search.finished_at = datetime.now(UTC)


def get_sourcing_provider() -> SourcingProvider:
    # Single provider today; licensed providers plug in behind this factory.
    return ApifySourcingProvider()


class SourcingSearchService:
    """Organization-scoped persistence and polling for sourcing searches."""

    @staticmethod
    def get_by_id(db: Session, *, search_id: uuid.UUID, organization_id: uuid.UUID):
        return db.scalar(
            select(SourcingSearch).where(
                SourcingSearch.id == search_id,
                SourcingSearch.organization_id == organization_id,
            )
        )

    @staticmethod
    def response_payload(search: SourcingSearch) -> dict:
        return {
            "id": search.id,
            "job_id": search.job_id,
            "query_text": search.query_text,
            "provider": search.provider,
            "status": search.status,
            "error_code": search.error_code,
            "error_message": ACTOR_ERRORS.get(search.error_code or ""),
            "candidates": [
                {
                    "id": c.id,
                    "full_name": c.full_name,
                    "headline": c.headline,
                    "location": c.location,
                    "current_title": c.current_title,
                    "current_company": c.current_company,
                    "profile_url": c.profile_url,
                    "fit_score": c.fit_score,
                    "status": c.status,
                }
                for c in search.candidates
            ],
            "created_at": search.created_at,
            "updated_at": search.updated_at,
        }
