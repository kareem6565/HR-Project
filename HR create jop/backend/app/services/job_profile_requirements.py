"""Resolve approved screening criteria with compatibility for older job records."""

from __future__ import annotations

from typing import Any

from app.ai.contracts import normalize_job_profile_requirements
from app.services.errors import ValidationError


def get_effective_job_requirements(job: Any, approved_profile: Any) -> tuple[list[Any], str]:
    """Return criteria from the approved profile or from explicit legacy job fields.

    Older jobs can have recruiter-authored requirements and skills on ``Job``
    while their approved JobProfile has an empty requirements array. Use those
    explicit fields as a compatibility source so screening remains grounded in
    the criteria already saved on the job. If neither source has criteria, fail
    clearly instead of persisting a completed zero-evidence evaluation.
    """
    profile_data = getattr(approved_profile, "profile_data", None) or {}
    profile_requirements = profile_data.get("requirements") or []
    if normalize_job_profile_requirements(profile_requirements):
        return profile_requirements, "approved_profile"

    requirements: list[dict[str, str]] = []
    seen: set[str] = set()
    for values, dimension in (
        (getattr(job, "required_skills", None) or [], "technical_skill"),
        (getattr(job, "requirements", None) or [], "skill"),
    ):
        for value in values:
            text = str(value or "").strip()
            normalized = text.casefold()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            requirements.append(
                {"text": text, "category": "must_have", "dimension": dimension}
            )

    experience = str(getattr(job, "experience", None) or "").strip()
    if experience:
        text = f"Relevant professional experience: {experience}"
        if text.casefold() not in seen:
            requirements.append(
                {"text": text, "category": "must_have", "dimension": "experience"}
            )

    if not requirements:
        raise ValidationError(
            "The approved job profile has no screening criteria. Add or extract job requirements, "
            "then approve the profile before screening candidates."
        )

    return requirements, "job_fields_compatibility"
