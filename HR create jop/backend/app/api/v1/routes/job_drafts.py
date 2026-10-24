"""Advisory job-form auto-fill endpoint.

POST /jobs/ai/suggest-form takes a raw job description and returns advisory
suggestions for the JobForm fields the ``jobs`` table actually stores. It is
strictly read-only: nothing is persisted, no Job or JobProfile is created, no
scoring, matching, or hiring decision happens, and no confidence fields are
exposed. As with every other AI workflow it goes through the ``AIProvider``
abstraction; in fake-provider mode the suggestions are derived
deterministically from the input so the endpoint stays hermetic without a gate.
"""

import re

from fastapi import APIRouter, Depends

from app.ai.contracts import AI_CONTRACT_SCHEMA_VERSION
from app.ai.providers.base import StructuredGenerationRequest
from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.job_drafts import (
    JobDraftSuggestionRequest,
    JobDraftSuggestionResponse,
)

router = APIRouter()


@router.post("/jobs/ai/suggest-form", response_model=JobDraftSuggestionResponse)
def suggest_job_form(
    body: JobDraftSuggestionRequest,
    ctx: RequestContext = Depends(get_request_context),
):
    from app.ai.contracts.job_draft import JobDraftSuggestionOutput
    from app.ai.contracts.validation import validate_job_draft_suggestion
    from app.ai.providers import get_provider
    from app.ai.providers.factory import resolve_ai_config
    from app.core.config import settings

    use_real_provider = not resolve_ai_config(settings)["is_fake"]
    if use_real_provider:
        provider = get_provider(settings)
    else:
        provider = get_provider(
            settings,
            provider="fake",
            model="fake-job-draft-suggester",
            structured_payload=_derive_suggestion_payload(body.raw_description),
        )

    result = provider.generate_structured(
        StructuredGenerationRequest(
            input=body.raw_description,
            output_schema=JobDraftSuggestionOutput,
            schema_version=AI_CONTRACT_SCHEMA_VERSION,
            metadata={"workflow": "job_draft_suggestion"},
        )
    )

    suggestion = validate_job_draft_suggestion(_clamp_suggestion_payload(result.data))
    return JobDraftSuggestionResponse(
        schema_version=suggestion.schema_version,
        title=suggestion.title,
        department=suggestion.department,
        location=suggestion.location,
        job_type=suggestion.job_type,
        experience=suggestion.experience,
        requirements=suggestion.requirements,
        required_skills=suggestion.required_skills,
    )


# --------------------------------------------------------------------------- #
# Deterministic fake-mode payload derivation
# --------------------------------------------------------------------------- #


def _clamp_text(value: str | None, limit: int) -> str | None:
    """Truncate a string to ``limit`` characters on a word boundary."""
    if value is None or len(value) <= limit:
        return value
    head = value[:limit]
    cut = head.rfind(" ")
    if cut > 0:
        return head[:cut].rstrip()
    return head


_STRING_LIMITS = {
    "title": 255,
    "department": 100,
    "location": 100,
    "job_type": 50,
    "experience": 100,
}
_LIST_LIMIT = 50


def _clamp_suggestion_payload(data: dict | None) -> dict | None:
    """Clamp AI suggestions to the column ceilings the job table allows.

    The model sometimes returns values that overflow a column (e.g. an
    ``experience`` sentence longer than 100 chars). One oversized field would
    otherwise fail the whole advisory suggestion with a 422; clamping keeps the
    remaining (valid) suggestions usable instead.
    """
    if not isinstance(data, dict):
        return data
    for key, limit in _STRING_LIMITS.items():
        value = data.get(key)
        if isinstance(value, str):
            data[key] = _clamp_text(value, limit)
    for key in ("requirements", "required_skills"):
        values = data.get(key)
        if isinstance(values, list):
            data[key] = values[:_LIST_LIMIT]
    return data


def _matches(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _derive_suggestion_payload(raw_description: str) -> dict:
    """Deterministic stand-in for the auto-fill step in fake-provider mode."""
    lowered = (raw_description or "").lower()
    lines = [line.strip() for line in (raw_description or "").splitlines() if line.strip()]

    title = lines[0] if lines else None
    if title and len(title) > 255:
        title = title[:255].rsplit(" ", 1)[0]

    if _matches(raw_description, _REMOTE_KEYWORDS):
        location = "Remote"
    elif _matches(raw_description, ("hybrid",)):
        location = "Hybrid"
    else:
        location = None

    if _matches(raw_description, ("contract", "freelance", "temporary", "temp ")):
        job_type = "Contract"
    elif _matches(raw_description, ("part-time", "part time", "evening", "weekend")):
        job_type = "Part-time"
    elif _matches(raw_description, ("intern", "internship", "graduate")):
        job_type = "Internship"
    elif _matches(raw_description, ("full-time", "full time", "permanent")):
        job_type = "Full-time"
    else:
        job_type = None

    department = next(
        (name for name in _DEPARTMENT_NAMES if name.lower() in lowered),
        None,
    )

    requirements = [
        line[2:].strip() for line in lines if line.lower().startswith("- ") or line.startswith("* ")
    ]
    skills = []
    for line in lines:
        marker = next(
            (candidate for candidate in _SKILL_MARKERS if candidate in line.lower()),
            None,
        )
        if marker is not None:
            tail = line[line.lower().find(marker) + len(marker) :]
            skills.extend(item.strip() for item in tail.split(",") if item.strip())

    return {
        "schema_version": AI_CONTRACT_SCHEMA_VERSION,
        "title": title,
        "department": department,
        "location": location,
        "job_type": job_type,
        "experience": _match_experience(lowered),
        "requirements": requirements[:50],
        "required_skills": skills[:50],
    }


_REMOTE_KEYWORDS = ("remote", "work from home", "wfh", "anywhere", "100% remote")

_DEPARTMENT_NAMES = (
    "engineering",
    "product",
    "design",
    "sales",
    "marketing",
    "finance",
    "operations",
    "customer support",
    "human resources",
    "legal",
)

_SKILL_MARKERS = ("skills:", "skills -", "required skills:", "comma separated:")


def _match_experience(lowered: str) -> str | None:
    matches = re.findall(r"(\d+)\s*\+?\s*(?:years?|yrs?|y)\b", lowered)
    if matches:
        return f"{int(matches[0])}+ years"
    if "experience" in lowered or "experienced" in lowered:
        return "Relevant experience preferred"
    return None
