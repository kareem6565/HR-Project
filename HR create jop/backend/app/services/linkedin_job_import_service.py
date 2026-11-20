from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.schemas.linkedin_job_imports import LinkedInJobImportResult
from app.core.config import settings
from app.models import LinkedInJobImport

ACTOR_ERRORS = {
    "start_unknown": (
        "Apify did not confirm whether the run started. This import was not retried."
    ),
    "apify_unavailable": (
        "Apify is temporarily unavailable. You can paste the job description manually."
    ),
    "rate_limited": (
        "Apify or LinkedIn rate-limited this request. Try later or paste the description manually."
    ),
    "actor_failed": "Apify could not extract this job. You can paste the description manually.",
    "empty_result": (
        "Apify returned no job for this URL. Check the link or paste the description manually."
    ),
    "malformed_result": (
        "Apify returned job data in an unsupported format. Paste the description manually."
    ),
    "missing_description": (
        "The public job description was unavailable. Paste the description manually."
    ),
}
_JOB_URL = re.compile(r"^/jobs/view/(\d+)/?$", re.IGNORECASE)


def canonicalize_linkedin_job_url(raw_url: str) -> tuple[str, str]:
    parts = urlsplit(raw_url)
    if (
        parts.scheme.lower() != "https"
        or (parts.hostname or "").lower() not in {"linkedin.com", "www.linkedin.com"}
        or parts.username is not None
        or parts.password is not None
        or parts.port not in (None, 443)
        or parts.fragment
    ):
        raise ValueError("Enter a public LinkedIn job URL in the /jobs/view/{id} format.")
    match = _JOB_URL.fullmatch(parts.path)
    if not match:
        raise ValueError("Enter a public LinkedIn job URL in the /jobs/view/{id} format.")
    job_id = match.group(1)
    return f"https://www.linkedin.com/jobs/view/{job_id}/", job_id


class LinkedInJobImportService:
    """Organization-scoped persistence and asynchronous Apify REST integration."""

    api_root = "https://api.apify.com/v2"

    @staticmethod
    def get_by_id(db: Session, *, import_id: uuid.UUID, organization_id: uuid.UUID):
        return db.scalar(
            select(LinkedInJobImport).where(
                LinkedInJobImport.id == import_id,
                LinkedInJobImport.organization_id == organization_id,
            )
        )

    async def start_actor(self, record: LinkedInJobImport) -> None:
        actor_path = settings.apify_linkedin_jobs_actor_id.replace("/", "~")
        record.actor_id = settings.apify_linkedin_jobs_actor_id
        timeout = httpx.Timeout(connect=8.0, read=25.0, write=10.0, pool=5.0)
        payload = {
            "startUrls": [{"url": record.source_url}],
            "keywords": [],
            "maxItems": 1,
            "includeDetails": True,
        }
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.api_root}/acts/{actor_path}/runs",
                    headers={"Authorization": f"Bearer {settings.apify_api_token}"},
                    json=payload,
                )
            if response.status_code == 429:
                record.status = "failed"
                record.error_code = "rate_limited"
                record.finished_at = datetime.now(UTC)
                return
            response.raise_for_status()
            body = response.json()
            run = body.get("data") if isinstance(body, dict) else None
            run_id = run.get("id") if isinstance(run, dict) else None
            if not isinstance(run_id, str) or not run_id:
                record.status = "failed"
                record.error_code = "malformed_result"
                record.finished_at = datetime.now(UTC)
                return
            record.actor_run_id = run_id
            record.status = "running"
            record.error_code = None
            record.last_checked_at = None
        except httpx.TimeoutException:
            # A timed-out POST may have reached Apify; never retry it implicitly.
            record.status = "failed"
            record.error_code = "start_unknown"
            record.finished_at = datetime.now(UTC)
        except httpx.HTTPStatusError as error:
            record.status = "failed"
            record.error_code = (
                "rate_limited" if error.response.status_code == 429 else "apify_unavailable"
            )
            record.finished_at = datetime.now(UTC)
        except (httpx.HTTPError, ValueError):
            record.status = "failed"
            record.error_code = "apify_unavailable"
            record.finished_at = datetime.now(UTC)

    async def refresh(self, record: LinkedInJobImport) -> None:
        if record.status != "running" or not record.actor_run_id:
            return
        now = datetime.now(UTC)
        if record.last_checked_at:
            last_checked = record.last_checked_at
            if last_checked.tzinfo is None:
                last_checked = last_checked.replace(tzinfo=UTC)
            if (now - last_checked).total_seconds() < 2:
                return
        record.last_checked_at = now
        headers = {"Authorization": f"Bearer {settings.apify_api_token}"}
        timeout = httpx.Timeout(connect=8.0, read=15.0, write=10.0, pool=5.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    f"{self.api_root}/actor-runs/{record.actor_run_id}", headers=headers
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
                    record.status = "failed"
                    record.error_code = "actor_failed"
                    record.finished_at = now
                    return
                dataset_id = run.get("defaultDatasetId")
                if not isinstance(dataset_id, str) or not dataset_id:
                    raise ValueError("Missing result dataset id")
                items_response = await client.get(
                    f"{self.api_root}/datasets/{dataset_id}/items",
                    params={"limit": 1, "clean": "true", "format": "json"},
                    headers=headers,
                )
                items_response.raise_for_status()
                items = items_response.json()
                if not isinstance(items, list) or not items:
                    record.status = "failed"
                    record.error_code = "empty_result"
                    record.finished_at = now
                    return
                if not isinstance(items[0], dict):
                    raise ValueError("Malformed dataset item")
                description = items[0].get("description")
                if not isinstance(description, str) or not description.strip():
                    record.status = "failed"
                    record.error_code = "missing_description"
                    record.finished_at = now
                    return
                result = LinkedInJobImportResult.model_validate(items[0])
                result_url, result_job_id = canonicalize_linkedin_job_url(str(result.job_url))
                if result_job_id != record.source_job_id or result_url != record.source_url:
                    record.status = "failed"
                    record.error_code = "malformed_result"
                    record.finished_at = now
                    return
                record.source_job_id = result.job_id
                record.result_data = result.model_dump(mode="json", by_alias=False)
                record.status = "succeeded"
                record.error_code = None
                record.finished_at = now
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 429:
                record.error_code = "rate_limited"
            else:
                record.error_code = "apify_unavailable"
        except httpx.TimeoutException:
            record.error_code = "apify_unavailable"
        except (httpx.HTTPError, ValueError, TypeError):
            record.status = "failed"
            record.error_code = "malformed_result"
            record.finished_at = now

    @staticmethod
    def response_payload(record: LinkedInJobImport) -> dict:
        return {
            "id": record.id,
            "source_url": record.source_url,
            "status": record.status,
            "error_code": record.error_code,
            "error_message": ACTOR_ERRORS.get(record.error_code),
            "result": record.result_data,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
