"""HERA assistant Chat API.

Threads + messages, org-scoped through the request identity headers. Sending a
message runs the HERA assistant agent (plan -> authorized tools -> compose)
through the same provider abstraction as every other AI workflow, persists the
user turn and the grounded assistant reply, and returns the reply.

In fake-provider mode the plan and compose payloads are derived
deterministically from the user message (plan) and from the real executed tool
results (compose), so the deterministic path is always grounded in real
pipeline data — the same principle as the evaluation/question-set fake payloads.
"""

import logging
import re
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.contracts import AI_CONTRACT_SCHEMA_VERSION
from app.api.v1.deps import RequestContext, get_request_context
from app.api.v1.schemas.chat import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatSendResponse,
    ChatThreadCreate,
    ChatThreadDetailResponse,
    ChatThreadListResponse,
    ChatThreadRename,
    ChatThreadResponse,
    ChatToolCallResponse,
    ChatToolResultResponse,
)
from app.core.database import get_db
from app.services.chat_service import ChatService
from app.services.errors import ValidationError

router = APIRouter()

logger = logging.getLogger(__name__)

_UUID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_DATE_PATTERN = re.compile(r"(\d{2,4})-(\d{1,2})-(\d{1,2})")


@router.post("/chat/threads", response_model=ChatThreadResponse, status_code=201)
def create_chat_thread(
    body: ChatThreadCreate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Create a new HERA conversation thread for the caller's organization."""
    thread = ChatService().create_thread(
        db,
        organization_id=ctx.organization_id,
        created_by_user_id=ctx.user_id,
        title=body.title,
    )
    db.commit()
    return thread


@router.get("/chat/threads", response_model=ChatThreadListResponse)
def list_chat_threads(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """List the caller's organization chat threads, most recent first."""
    threads = ChatService().list_threads(db, organization_id=ctx.organization_id)
    return ChatThreadListResponse(threads=threads, total=len(threads))


@router.get("/chat/threads/{thread_id}", response_model=ChatThreadDetailResponse)
def get_chat_thread(
    thread_id: str,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Return a thread with its messages (oldest first)."""
    service = ChatService()
    thread = service.get_thread(
        db, thread_id=uuid.UUID(thread_id), organization_id=ctx.organization_id
    )
    messages = service.list_messages(db, thread_id=thread.id, organization_id=ctx.organization_id)
    return ChatThreadDetailResponse(
        thread=thread,
        messages=[_message_response(message) for message in messages],
    )


@router.patch("/chat/threads/{thread_id}", response_model=ChatThreadResponse)
def rename_chat_thread(
    thread_id: str,
    body: ChatThreadRename,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Rename a chat thread."""
    thread = ChatService().rename_thread(
        db,
        thread_id=uuid.UUID(thread_id),
        organization_id=ctx.organization_id,
        title=body.title,
    )
    db.commit()
    return thread


@router.post("/chat/threads/{thread_id}/messages", response_model=ChatSendResponse)
def send_chat_message(
    thread_id: str,
    body: ChatMessageCreate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Send a user turn and return the agent's grounded reply."""
    from app.ai.providers import get_provider
    from app.ai.providers.errors import ProviderError
    from app.ai.providers.factory import resolve_ai_config
    from app.ai.workflows import HERAAssistantWorkflow
    from app.core.config import settings

    service = ChatService()
    thread = service.get_thread(
        db, thread_id=uuid.UUID(thread_id), organization_id=ctx.organization_id
    )
    service.add_message(
        db,
        thread_id=thread.id,
        organization_id=ctx.organization_id,
        role="user",
        content=body.content,
    )
    history = service.history_text(db, thread_id=thread.id, organization_id=ctx.organization_id)

    plan_provider = get_provider(
        settings,
        provider="fake",
        model="fake-hera-planner",
        structured_payload=_derive_chat_plan_payload(body.content),
    )
    use_real_provider = not resolve_ai_config(settings)["is_fake"]

    def compose_factory(invocations):
        if use_real_provider:
            return get_provider(settings)
        payload = _derive_chat_reply_payload(body.content, invocations)
        return get_provider(
            settings,
            provider="fake",
            model="fake-hera-composer",
            structured_payload=payload,
        )

    workflow = HERAAssistantWorkflow()
    try:
        result = workflow.run(
            db,
            organization_id=ctx.organization_id,
            user_id=ctx.user_id,
            chat_thread_id=thread.id,
            user_message=body.content,
            history_text=history,
            plan_provider=plan_provider,
            compose_provider_factory=compose_factory,
        )
    except (ProviderError, ValidationError) as exc:
        logger.warning(
            "chat send failed for thread=%s org=%s user=%s: %s: %s",
            thread.id,
            ctx.organization_id,
            ctx.user_id,
            type(exc).__name__,
            str(exc),
        )
        db.rollback()
        raise

    assistant_message = service.add_message(
        db,
        thread_id=thread.id,
        organization_id=ctx.organization_id,
        role="assistant",
        content=result.reply.answer,
        tool_calls=[
            {"tool": invocation.tool, "arguments": invocation.arguments}
            for invocation in result.invocations
        ],
        tool_results=[
            {
                "tool": invocation.tool,
                "ok": invocation.ok,
                "data": invocation.data if invocation.ok else None,
                "error": invocation.error,
            }
            for invocation in result.invocations
        ],
        workflow_run_id=result.workflow_run_id,
    )
    if not thread.title:
        thread.title = _derive_title(body.content)
    db.commit()
    return ChatSendResponse(thread=thread, message=_message_response(assistant_message))


# --------------------------------------------------------------------------- #
# Response helpers
# --------------------------------------------------------------------------- #


def _message_response(message) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=message.id,
        chat_thread_id=message.chat_thread_id,
        role=message.role,
        content=message.content,
        tool_calls=(
            [ChatToolCallResponse(**item) for item in message.tool_calls]
            if message.tool_calls
            else None
        ),
        tool_results=(
            [ChatToolResultResponse(**item) for item in message.tool_results]
            if message.tool_results
            else None
        ),
        workflow_run_id=message.workflow_run_id,
        created_at=message.created_at,
    )


def _derive_title(content: str) -> str:
    cleaned = " ".join((content or "").split())
    return cleaned[:120]


# --------------------------------------------------------------------------- #
# Deterministic fake-mode payload derivation
# --------------------------------------------------------------------------- #


def _find_uuid(text: str) -> str | None:
    match = _UUID_PATTERN.search(text)
    return match.group(0) if match is not None else None


def _find_date(text: str) -> str | None:
    match = _DATE_PATTERN.search(text)
    if match is None:
        return None
    year = match.group(1).zfill(4)
    month = match.group(2).zfill(2)
    day = match.group(3).zfill(2)
    return f"{year}-{month}-{day}"


def _first_present(text: str, candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in text:
            return candidate
    return None


def _derive_chat_plan_payload(message: str) -> dict:
    """Deterministic stand-in for the planner step in fake-provider mode."""
    lowered = (message or "").lower()
    tool_calls: list[dict] = []
    application_uuid = _find_uuid(message or "")
    iso_date = _find_date(message or "")

    if application_uuid is not None and "application" in lowered:
        tool_calls.append(
            {
                "tool": "get_application_details",
                "arguments": {"application_id": application_uuid},
            }
        )
    elif iso_date is not None and any(
        keyword in lowered for keyword in ("interview", "slot", "free", "availability", "booked")
    ):
        tool_calls.append(
            {"tool": "get_interview_slots", "arguments": {"scheduled_date": iso_date}}
        )
    elif "interview" in lowered:
        status = _first_present(lowered, ("scheduled", "completed", "cancelled"))
        tool_calls.append(
            {
                "tool": "list_interviews",
                "arguments": {"status": status} if status else {},
            }
        )
    elif any(
        keyword in lowered
        for keyword in ("talent", "pool", "shortlist", "top candidate", "top-rated")
    ):
        tool_calls.append({"tool": "get_talent_pool", "arguments": {}})
    elif any(
        keyword in lowered for keyword in ("job", "jobs", "role", "position", "opening", "hiring")
    ):
        status = "active" if "active" in lowered or "open" in lowered else None
        tool_calls.append(
            {
                "tool": "list_jobs",
                "arguments": {"status": status} if status else {},
            }
        )
    elif "pipeline" in lowered or (
        any(keyword in lowered for keyword in ("how many", "count", "status", "progress"))
        and any(keyword in lowered for keyword in ("application", "applicant", "candidate"))
    ):
        status = _first_present(lowered, ("advanced", "hold", "rejected", "created"))
        tool_calls.append(
            {
                "tool": "summarize_pipeline",
                "arguments": {"status": status} if status else {},
            }
        )
    elif any(keyword in lowered for keyword in ("candidate", "candidates", "applicant")):
        tool_calls.append({"tool": "search_candidates", "arguments": {"query": ""}})
    elif "ai" in lowered and any(
        keyword in lowered for keyword in ("activity", "work", "trace", "run", "status")
    ):
        tool_calls.append({"tool": "get_ai_activity", "arguments": {}})

    return {"schema_version": AI_CONTRACT_SCHEMA_VERSION, "tool_calls": tool_calls}


def _no_data_reply(lowered: str) -> str:
    if any(keyword in lowered for keyword in ("hello", "hi ", "hey", "thanks", "thank you")):
        return (
            "Hi! I'm HERA, your HR assistant. Ask me about the pipeline, candidates, "
            "jobs, interviews and availability, application details, or AI activity."
        )
    return (
        "I can help with the recruitment pipeline: who's shortlisted, active jobs, "
        "finding candidates, interviews and availability, an application's review "
        "details, or how the AI is performing. Try one of those!"
    )


def _fmt_score(score: float | None) -> str:
    if score is None:
        return "no score yet"
    return f"{score:.0f}%"


def _plural(count: int, noun: str) -> str:
    return noun if count == 1 else f"{noun}s"


def _format_interview_row(row: dict) -> str:
    base = (
        f"{row.get('candidate_name')} for {row.get('job_title')} on "
        f"{row.get('scheduled_date')} at {row.get('scheduled_time')} ({row.get('status')}"
    )
    if row.get("interviewer_name"):
        return f"{base}, {row.get('interviewer_name')})"
    return f"{base})"


def _render_tool(tool: str, data: dict, parts: list[str], links: list[dict]) -> None:
    if tool == "summarize_pipeline":
        total = data.get("total", 0)
        status_filter = data.get("status_filter")
        if status_filter:
            parts.append(f"There are {total} applications with status {status_filter}.")
        else:
            parts.append(f"There are {total} applications in your pipeline.")
        by_status = data.get("by_status") or {}
        if by_status:
            pieces = ", ".join(f"{key}: {value}" for key, value in sorted(by_status.items()))
            parts.append(f"By status — {pieces}.")
        top = data.get("top_scored") or []
        if top:
            rendered = "; ".join(
                f"{row['applicant']} ({_fmt_score(row.get('score'))} for "
                f"{row.get('job_title') or 'a role'})"
                for row in top
            )
            parts.append(f"Top scored: {rendered}.")
        links.append({"label": "View Applications", "path": "/applications"})
    elif tool == "list_jobs":
        jobs = data.get("jobs") or []
        filter_text = f" ({data.get('status_filter')})" if data.get("status_filter") else ""
        total = data.get("total", 0)
        parts.append(f"You have {total} {_plural(total, 'job')}{filter_text} right now.")
        if jobs:
            parts.append(" / ".join(job.get("title", "") for job in jobs) + ".")
        links.append({"label": "View Jobs", "path": "/jobs"})
    elif tool == "search_candidates":
        candidates = data.get("candidates") or []
        total = data.get("total", 0)
        parts.append(f"Found {total} {_plural(total, 'candidate')}.")
        if candidates:
            names = ", ".join(c.get("full_name", "") for c in candidates)
            parts.append(f"{names}.")
        links.append({"label": "View Candidates", "path": "/candidates"})
    elif tool == "get_talent_pool":
        rows = data.get("rows") or []
        total = data.get("total", 0)
        parts.append(f"There are {total} {_plural(total, 'candidate')} in the talent pool.")
        if rows:
            rendered = "; ".join(
                f"{row.get('name')} ({_fmt_score(row.get('score'))} — "
                f"{row.get('job_title') or 'a role'}, {row.get('group')})"
                for row in rows
            )
            parts.append(rendered + ".")
        links.append({"label": "View Talent Pool", "path": "/talent-pool"})
    elif tool == "list_interviews":
        interviews = data.get("interviews") or []
        total = data.get("total", 0)
        status_filter = data.get("status_filter")
        suffix = f" ({status_filter})" if status_filter else ""
        parts.append(f"There are {total} {_plural(total, 'interview')}{suffix}.")
        if interviews:
            rendered = "; ".join(_format_interview_row(row) for row in interviews)
            parts.append(rendered + ".")
        links.append({"label": "View Interviews", "path": "/interviews"})
    elif tool == "get_application_details":
        candidate = data.get("candidate") or {}
        parts.append(
            f"{candidate.get('full_name', 'This candidate')} for "
            f"{data.get('job_title') or 'the role'} is {data.get('status')}"
            f" with score {_fmt_score(data.get('score'))}."
        )
        if data.get("latest_decision"):
            parts.append(f"Latest HR decision: {data['latest_decision']}.")
        parts.append(
            f"{data.get('evaluations_count', 0)} evaluation(s), "
            f"{data.get('evidence_count', 0)} evidence item(s)."
        )
        if data.get("question_set"):
            parts.append(
                f"Interview question set v{data['question_set'].get('version_number')} "
                f"is {data['question_set'].get('status')}."
            )
        links.append(
            {
                "label": "Open Review",
                "path": f"/applications/{data.get('application_id', '')}/review",
            }
        )
    elif tool == "get_interview_slots":
        date_iso = data.get("scheduled_date", "")
        count = data.get("occupied_count", 0)
        windows = data.get("occupied_windows") or []
        parts.append(
            f"On {date_iso} there {'is' if count == 1 else 'are'} {count} "
            f"occupied interview window{'' if count == 1 else 's'}."
        )
        if windows:
            rendered = ", ".join(f"{w.get('start_time')}-{w.get('end_time')}" for w in windows)
            parts.append(f"Occupied: {rendered}.")
        links.append({"label": "Open Scheduler", "path": "/interviews/schedule"})
    elif tool == "get_ai_activity":
        parts.append(
            f"In the last 24 hours HERA ran {data.get('total_runs_24h', 0)} AI "
            f"job(s) — {data.get('successful', 0)} succeeded, "
            f"{data.get('failed', 0)} failed, avg latency "
            f"{data.get('avg_latency_ms')} ms."
        )
        links.append({"label": "View AI Activity", "path": "/ai-activity"})


def _derive_chat_reply_payload(message: str, invocations) -> dict:
    """Deterministic stand-in for the compose step in fake-provider mode.

    Builds the reply from the *actual* executed tool results so the fake path is
    always grounded in real pipeline data (never fabricated figures).
    """
    lowered = (message or "").lower()
    if not invocations:
        return {
            "schema_version": AI_CONTRACT_SCHEMA_VERSION,
            "answer": _no_data_reply(lowered),
            "used_tool_indices": [],
            "links": [],
        }
    parts: list[str] = []
    links: list[dict] = []
    for invocation in invocations:
        if not invocation.ok:
            parts.append(
                f"I couldn't look that up: {invocation.error or 'the request was not valid'}."
            )
            continue
        _render_tool(invocation.tool, invocation.data or {}, parts, links)
    answer = " ".join(parts).strip()
    if not answer:
        answer = "I did not find anything for that — try rephrasing your question."
    return {
        "schema_version": AI_CONTRACT_SCHEMA_VERSION,
        "answer": answer,
        "used_tool_indices": [
            index for index, invocation in enumerate(invocations) if invocation.ok
        ],
        "links": links[:3],
    }
