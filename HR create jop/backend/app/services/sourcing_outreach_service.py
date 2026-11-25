"""Assisted outreach drafts for sourced candidates.

Template-based by default; an on-demand AI-personalized variant reuses the
platform's configured AI provider. Drafts are generated per candidate on
request and never sent by the platform: the HR user reviews, edits, and sends
from their own mail client (mailto). No bulk sending anywhere in this flow.
"""

from __future__ import annotations

from typing import Any

from app.ai.providers.base import TextGenerationRequest
from app.ai.providers.factory import get_provider
from app.core.config import settings
from app.models import Job, SourcingCandidate


def _first_name(candidate: SourcingCandidate) -> str:
    if candidate.full_name:
        return candidate.full_name.split()[0]
    return "there"


def _role_line(candidate: SourcingCandidate) -> str:
    if candidate.current_title and candidate.current_company:
        return f"your work as {candidate.current_title} at {candidate.current_company}"
    if candidate.current_title:
        return f"your work as {candidate.current_title}"
    if candidate.headline:
        return f"your background ({candidate.headline[:120]})"
    return "your background"


def _job_summary(job: Job | None) -> str:
    if job is None:
        return ""
    text = (job.description_text or job.raw_description or "").strip().split("\n")[0]
    return text[:240]


def build_template_draft(
    *,
    candidate: SourcingCandidate,
    job: Job | None,
    organization_name: str,
    sender_name: str,
) -> dict[str, Any]:
    """Deterministic outreach draft. Always available, zero AI cost."""

    role = job.title if job else "a role"
    subject = f"{role} at {organization_name} - interested?"
    summary = _job_summary(job)
    lines = [
        f"Hi {_first_name(candidate)},",
        "",
        f"I came across your profile and was impressed by {_role_line(candidate)}.",
        f"We are hiring for {role} at {organization_name}, and I think you would be a strong fit.",
    ]
    if summary:
        lines += ["", f"About the role: {summary}"]
    lines += [
        "",
        "Would you be open to a short chat this week?",
        "",
        "Best,",
        sender_name,
        organization_name,
    ]
    return {"subject": subject[:200], "body": "\n".join(lines), "personalized": False}


_PERSONALIZE_PROMPT = """Write a short recruiting outreach email (at most 120 words of body text).

Candidate: {candidate_name}, {candidate_context}
Role: {role} at {organization}
{role_summary}

Rules: friendly and direct, no buzzwords, mention one specific detail about the
candidate, end with a simple ask for a short chat. Sign off as {sender}.
Output format: first line "Subject: ...", then a blank line, then the body."""


def _parse_ai_output(text: str, fallback_subject: str) -> dict[str, str]:
    subject = fallback_subject
    body = text.strip()
    if text.startswith("Subject:"):
        first, _, rest = text.partition("\n")
        candidate_subject = first.removeprefix("Subject:").strip()
        if candidate_subject:
            subject = candidate_subject[:200]
        body = rest.strip()
    return {"subject": subject, "body": body}


def build_ai_personalized_draft(
    *,
    candidate: SourcingCandidate,
    job: Job | None,
    organization_name: str,
    sender_name: str,
) -> dict[str, Any]:
    """AI-personalized draft for one candidate. Falls back to the template.

    Never raises for provider problems: outreach must keep working when the AI
    provider is down, rate-limited, or unconfigured.
    """

    template = build_template_draft(
        candidate=candidate,
        job=job,
        organization_name=organization_name,
        sender_name=sender_name,
    )
    role = job.title if job else "an open role"
    prompt = _PERSONALIZE_PROMPT.format(
        candidate_name=candidate.full_name or "the candidate",
        candidate_context=_role_line(candidate),
        role=role,
        organization=organization_name,
        role_summary=_job_summary(job),
        sender=sender_name,
    )
    try:
        provider = get_provider(settings)
        result = provider.generate_text(
            TextGenerationRequest(
                input=prompt,
                metadata={"feature": "sourcing_outreach", "purpose": "candidate_outreach_draft"},
            )
        )
        text = getattr(result, "text", None) or ""
        if not text.strip():
            raise ValueError("empty AI response")
    except Exception:  # noqa: BLE001 - provider problems degrade to the template draft
        return template
    parsed = _parse_ai_output(text, template["subject"])
    return {**parsed, "personalized": True}
