"""Authorized read-only tool registry for the HERA assistant.

Every tool the assistant can invoke is registered here with a name, a
description, a JSON-schema-like argument spec, and a handler that calls a real
domain service. Nothing besides these handlers is ever reachable from the LLM:
the plan contract only produces tool names + scalar arguments, and
``validate_and_coerce_arguments`` rejects unknown arguments, non-scalar values,
and missing required fields before a handler runs.

Handlers are strictly read-only and organization-scoped: they receive the
``organization_id`` and ``user_id`` resolved from the request identity headers,
and every domain service call they perform scopes and validates ownership.
"""

from __future__ import annotations

import re
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.services.ai_activity_service import AIActivityService
from app.services.candidate_service import CandidateService
from app.services.errors import ValidationError
from app.services.interview_question_service import InterviewQuestionService
from app.services.interview_service import InterviewService
from app.services.job_service import JobService
from app.services.review_service import ReviewService

VALID_APPLICATION_STATUSES = frozenset({"created", "advanced", "hold", "rejected"})
VALID_JOB_STATUSES = frozenset({"draft", "active"})
VALID_INTERVIEW_STATUSES = frozenset({"scheduled", "completed", "cancelled"})

MAX_LIMIT = 50
DEFAULT_LIMIT = 10


@dataclass(frozen=True)
class RegisteredTool:
    """One authorized tool: metadata for the LLM + a domain-service handler."""

    name: str
    description: str
    arguments_schema: dict[str, Any]
    handler: Callable[..., dict[str, Any]]


def _bounded_limit(value: Any, default: int = DEFAULT_LIMIT) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = default
    if limit < 1:
        limit = 1
    return min(limit, MAX_LIMIT)


def _score_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Handlers
# --------------------------------------------------------------------------- #


def _summarize_pipeline(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    status: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    limit = _bounded_limit(limit, DEFAULT_LIMIT)
    if status is not None and status not in VALID_APPLICATION_STATUSES:
        raise ValidationError(
            f"Application status filter must be one of {sorted(VALID_APPLICATION_STATUSES)}."
        )
    rows = ReviewService().list_application_summaries(
        db, organization_id=organization_id, status=status
    )
    counts = Counter(row.application.status for row in rows)
    scored = [
        row
        for row in rows
        if row.current_evaluation is not None
        and _score_float(row.current_evaluation.score) is not None
    ]
    scored.sort(key=lambda row: _score_float(row.current_evaluation.score) or 0, reverse=True)
    return {
        "status_filter": status,
        "total": len(rows),
        "by_status": dict(sorted(counts.items())),
        "top_scored": [
            {
                "application_id": str(row.application.id),
                "applicant": row.candidate.full_name,
                "status": row.application.status,
                "job_title": row.job.title,
                "score": _score_float(row.current_evaluation.score),
            }
            for row in scored[:limit]
        ],
    }


def _list_jobs(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    status: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    limit = _bounded_limit(limit, DEFAULT_LIMIT)
    if status is not None and status not in VALID_JOB_STATUSES:
        raise ValidationError(f"Job status filter must be one of {sorted(VALID_JOB_STATUSES)}.")
    jobs = JobService().list(db, organization_id=organization_id)
    if status is not None:
        jobs = [job for job in jobs if job.status == status]
    return {
        "status_filter": status,
        "total": len(jobs),
        "jobs": [
            {
                "id": str(job.id),
                "title": job.title,
                "status": job.status,
                "department": job.department,
                "location": job.location,
            }
            for job in jobs[:limit]
        ],
    }


def _search_candidates(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    query: str,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    limit = _bounded_limit(limit, DEFAULT_LIMIT)
    candidates = CandidateService().list(
        db, organization_id=organization_id, search=(query or "").strip() or None
    )
    return {
        "query": query or "",
        "total": len(candidates),
        "candidates": [
            {
                "id": str(candidate.id),
                "full_name": candidate.full_name,
                "email": candidate.email,
                "status": candidate.status,
            }
            for candidate in candidates[:limit]
        ],
    }


def _get_talent_pool(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    limit = _bounded_limit(limit, DEFAULT_LIMIT)
    rows = ReviewService().list_talent_pool(db, organization_id=organization_id)
    return {
        "total": len(rows),
        "rows": [
            {
                "application_id": str(row.application.id),
                "name": row.candidate.full_name,
                "job_title": row.job.title,
                "status": row.application.status,
                "group": row.group,
                "score": _score_float(row.current_evaluation.score)
                if row.current_evaluation is not None
                else None,
                "decision": row.latest_decision.decision
                if row.latest_decision is not None
                else None,
            }
            for row in rows[:limit]
        ],
    }


def _list_interviews(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    status: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    limit = _bounded_limit(limit, DEFAULT_LIMIT)
    if status is not None and status not in VALID_INTERVIEW_STATUSES:
        raise ValidationError(
            f"Interview status filter must be one of {sorted(VALID_INTERVIEW_STATUSES)}."
        )
    interviews = InterviewService().list(db, organization_id=organization_id, status=status)
    return {
        "status_filter": status,
        "total": len(interviews),
        "interviews": [
            {
                "id": str(interview.id),
                "candidate_name": interview.job_application.candidate.full_name,
                "job_title": interview.job_application.job.title,
                "interview_type": interview.interview_type,
                "status": interview.status,
                "scheduled_date": interview.scheduled_date.isoformat(),
                "scheduled_time": interview.scheduled_time,
                "scheduled_duration_minutes": interview.scheduled_duration_minutes,
                "interviewer_name": (
                    interview.interviewer.full_name if interview.interviewer is not None else None
                ),
            }
            for interview in interviews[:limit]
        ],
    }


def _get_application_details(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    application_id: str,
) -> dict[str, Any]:
    application_uuid = uuid.UUID(application_id)
    review = ReviewService().get_review_bundle(
        db, application_id=application_uuid, organization_id=organization_id
    )
    current = review.current_evaluation
    question_set = InterviewQuestionService().get_current_or_latest(
        db, job_application_id=review.application.id, organization_id=organization_id
    )
    return {
        "application_id": str(review.application.id),
        "status": review.application.status,
        "candidate": {
            "id": str(review.candidate.id),
            "full_name": review.candidate.full_name,
            "email": review.candidate.email,
        },
        "job_title": review.job.title,
        "group": review.group,
        "score": _score_float(current.score) if current is not None else None,
        "recommendation": current.recommendation if current is not None else None,
        "latest_decision": (
            review.latest_decision.decision if review.latest_decision is not None else None
        ),
        "decision_reason": (
            review.latest_decision.reason if review.latest_decision is not None else None
        ),
        "evaluations_count": len(review.evaluations),
        "evidence_count": len(review.evidence),
        "evidence_sample": [
            {
                "evidence_type": item.evidence_type,
                "snippet": (item.candidate_evidence or "")[:200],
            }
            for item in review.evidence[:3]
        ],
        "question_set": (
            {
                "status": question_set.status,
                "version_number": question_set.version_number,
            }
            if question_set is not None
            else None
        ),
    }


def _get_interview_slots(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    scheduled_date: str,
    interviewer_user_id: str | None = None,
) -> dict[str, Any]:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", scheduled_date.strip()) is None:
        raise ValidationError(
            "scheduled_date must use the YYYY-MM-DD format for the availability query."
        )
    parsed_date = date.fromisoformat(scheduled_date.strip())
    interviewer = uuid.UUID(interviewer_user_id) if interviewer_user_id else None
    occupied = InterviewService().list_slots_for_date(
        db,
        organization_id=organization_id,
        scheduled_date=parsed_date,
        interviewer_user_id=interviewer,
    )
    return {
        "scheduled_date": parsed_date.isoformat(),
        "occupied_count": len(occupied),
        "occupied_windows": [
            {
                "start_time": window["start_time"],
                "end_time": window["end_time"],
                "interview_id": str(window["interview_id"]),
            }
            for window in occupied[:MAX_LIMIT]
        ],
    }


def _get_ai_activity(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict[str, Any]:
    stats = AIActivityService().get_stats(db, organization_id=organization_id)
    return {
        key: stats.get(key) for key in ("total_runs_24h", "successful", "failed", "avg_latency_ms")
    }


# --------------------------------------------------------------------------- #
# Tool catalog
# --------------------------------------------------------------------------- #


def _arguments(**properties: dict[str, Any]) -> dict[str, Any]:
    """Build a compact JSON-schema-like argument spec from property specs."""
    return {"properties": properties, "required": []}


PIPELINE_TOOLS: list[RegisteredTool] = [
    RegisteredTool(
        name="summarize_pipeline",
        description=(
            "Summarize the recruitment pipeline for the caller's organization: total "
            "applications (optionally filtered by status: created, advanced, hold, "
            "rejected) and the highest-scored applications. For pipeline counts, "
            "statuses, and 'who is in progress' questions."
        ),
        arguments_schema=_arguments(
            status={"type": "string", "description": "created|advanced|hold|rejected"},
            limit={"type": "integer"},
        ),
        handler=_summarize_pipeline,
    ),
    RegisteredTool(
        name="list_jobs",
        description=(
            "List open jobs in the caller's organization (optionally filtered by "
            "status: draft or active). For 'which jobs are open/active' questions."
        ),
        arguments_schema=_arguments(
            status={"type": "string", "description": "draft|active"},
            limit={"type": "integer"},
        ),
        handler=_list_jobs,
    ),
    RegisteredTool(
        name="search_candidates",
        description=(
            "Search candidates by name or email text (case-insensitive substring). "
            "For 'who is <name>', 'find a candidate', and candidate roster counts."
        ),
        arguments_schema=_arguments(
            query={"type": "string", "description": "name or email text to match"},
            limit={"type": "integer"},
        ),
        handler=_search_candidates,
    ),
    RegisteredTool(
        name="get_talent_pool",
        description=(
            "List the organization's talent pool: hold/advanced candidates ranked by "
            "current evaluation score, with their score band (must_review / consider / "
            "lower_priority) and latest HR decision. For top-candidate and shortlist "
            "questions."
        ),
        arguments_schema=_arguments(limit={"type": "integer"}),
        handler=_get_talent_pool,
    ),
    RegisteredTool(
        name="list_interviews",
        description=(
            "List scheduled/completed/cancelled interviews with candidate, job, "
            "interviewer, date and time. For 'what interviews are scheduled' questions."
        ),
        arguments_schema=_arguments(
            status={"type": "string", "description": "scheduled|completed|cancelled"},
            limit={"type": "integer"},
        ),
        handler=_list_interviews,
    ),
    RegisteredTool(
        name="get_application_details",
        description=(
            "Return the full read-only context of one job application: status, score, "
            "recommendation, latest HR decision, evidence highlights, and the current "
            "interview question set. Requires the exact application UUID the user "
            "provided — never invent one."
        ),
        arguments_schema=_arguments(
            application_id={
                "type": "string",
                "description": "UUID of a job application the user referenced",
            }
        ),
        handler=_get_application_details,
    ),
    RegisteredTool(
        name="get_interview_slots",
        description=(
            "Show the occupied interview windows for a given calendar date "
            "(YYYY-MM-DD) in the caller's organization. For availability questions "
            "like 'is Thursday free?'."
        ),
        arguments_schema=_arguments(
            scheduled_date={"type": "string", "description": "calendar date in YYYY-MM-DD"},
            interviewer_user_id={"type": "string"},
        ),
        handler=_get_interview_slots,
    ),
    RegisteredTool(
        name="get_ai_activity",
        description=(
            "Report AI activity over the last 24 hours for the caller's organization: "
            "total runs, successes, failures, average latency. For 'is the AI working?' "
            "and observability questions."
        ),
        arguments_schema=_arguments(),
        handler=_get_ai_activity,
    ),
]
