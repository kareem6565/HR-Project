"""Fail-closed free-first enforcement and shared AI usage metering."""

from __future__ import annotations

import logging
import re
import threading
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import case, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.ai.actor_context import ai_actor_context
from app.ai.providers.errors import ProviderRateLimitError, ProviderUnavailableError
from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.core.logging import get_request_id
from app.models.ai_usage import AIPolicyControl, AIUsageCounter, AIUsageEvent

logger = logging.getLogger("app.ai.cost_policy")
_CATALOG_URL = "https://openrouter.ai/api/v1/models"
_CATALOG_TTL = timedelta(minutes=10)
_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_PATTERN = re.compile(r"(?<!\w)\+?\d[\d ().-]{7,}\d(?!\w)")
_SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
_catalog_lock = threading.Lock()
_catalog_cache: tuple[datetime, dict[str, dict[str, Any]]] | None = None


def minimize_hr_identifiers(text: str) -> str:
    """Mask direct contact identifiers and profile URLs before external inference."""
    text = _EMAIL_PATTERN.sub("[EMAIL REDACTED]", text)
    text = _SSN_PATTERN.sub("[GOVERNMENT ID REDACTED]", text)

    def redact_phone(match: re.Match[str]) -> str:
        return (
            "[PHONE REDACTED]"
            if sum(char.isdigit() for char in match.group()) >= 10
            else match.group()
        )

    text = _PHONE_PATTERN.sub(redact_phone, text)
    return _URL_PATTERN.sub("[PROFILE OR SOURCE URL REDACTED]", text)


def _fetch_catalog() -> dict[str, dict[str, Any]]:
    """Return public model metadata; no credentials or inference are sent."""
    global _catalog_cache
    now = datetime.now(UTC)
    with _catalog_lock:
        if _catalog_cache and now - _catalog_cache[0] < _CATALOG_TTL:
            return _catalog_cache[1]
        try:
            response = httpx.get(_CATALOG_URL, timeout=8.0)
            response.raise_for_status()
            data = response.json().get("data")
            if not isinstance(data, list):
                raise ValueError("Model catalog response is invalid.")
            catalog = {
                str(item["id"]): item
                for item in data
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            }
        except Exception as exc:  # noqa: BLE001 - public catalog failures must fail closed
            raise ProviderUnavailableError(
                "Could not verify free-model eligibility from the OpenRouter catalog."
            ) from exc
        _catalog_cache = (now, catalog)
        return catalog


def _zero_price(value: Any) -> bool:
    if value is None:
        return False
    try:
        return Decimal(str(value)) == 0
    except (InvalidOperation, ValueError):
        return False


def _approved_model(
    *,
    model: str,
    structured: bool,
    settings: Settings,
    catalog: dict[str, dict[str, Any]] | None = None,
) -> None:
    if model == "openrouter/free":
        return
    allowlist = {
        entry.strip() for entry in settings.ai_free_model_allowlist.split(",") if entry.strip()
    }
    if not model.endswith(":free") or model not in allowlist:
        raise ProviderUnavailableError(
            "The configured AI model is not approved for free inference."
        )
    models = catalog if catalog is not None else _fetch_catalog()
    item = models.get(model)
    if not item:
        raise ProviderUnavailableError(
            "The approved free model is missing from the current catalog."
        )
    pricing = item.get("pricing") or {}
    if not _zero_price(pricing.get("prompt")) or not _zero_price(pricing.get("completion")):
        raise ProviderUnavailableError("The selected model is not currently zero-priced.")
    architecture = item.get("architecture") or {}
    input_modalities = architecture.get("input_modalities") or []
    output_modalities = architecture.get("output_modalities") or []
    if "text" not in input_modalities or "text" not in output_modalities:
        raise ProviderUnavailableError("The selected model lacks required text capabilities.")
    if structured and "response_format" not in (item.get("supported_parameters") or []):
        raise ProviderUnavailableError(
            "The selected free model does not support structured JSON output."
        )


def _utc_windows(now: datetime) -> tuple[datetime, datetime]:
    utc_now = now.astimezone(UTC)
    minute = utc_now.replace(second=0, microsecond=0)
    day = datetime.combine(utc_now.date(), time.min, tzinfo=UTC)
    return minute, day


def _reserve_counter(session: Session, key: str, window: datetime, limit: int) -> bool:
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        insert_stmt = pg_insert(AIUsageCounter)
    elif dialect == "sqlite":
        insert_stmt = sqlite_insert(AIUsageCounter)
    else:
        raise ProviderUnavailableError("AI request metering requires PostgreSQL or SQLite.")
    excluded = insert_stmt.excluded
    table = AIUsageCounter.__table__
    upsert = (
        insert_stmt.values(bucket_key=key, window_start=window, request_count=1)
        .on_conflict_do_update(
            index_elements=[table.c.bucket_key],
            set_={
                "window_start": case(
                    (table.c.window_start < excluded.window_start, excluded.window_start),
                    else_=table.c.window_start,
                ),
                "request_count": case(
                    (table.c.window_start < excluded.window_start, 1),
                    else_=table.c.request_count + 1,
                ),
                "updated_at": datetime.now(UTC),
            },
            where=or_(table.c.window_start < excluded.window_start, table.c.request_count < limit),
        )
        .returning(table.c.request_count)
    )
    return session.execute(upsert).scalar_one_or_none() is not None


def _new_event(
    *,
    provider: str,
    model: str,
    metadata: dict[str, Any] | None,
    settings: Settings,
    quota_kind: str = "external",
) -> UUID:
    actor = ai_actor_context.get()
    user_id, organization_id = actor if actor else (None, None)
    feature_parts: list[str] = []
    if metadata:
        for name in ("workflow", "component", "operation"):
            value = metadata.get(name)
            if isinstance(value, str) and value.strip():
                feature_parts.append(
                    "".join(c for c in value.strip() if c.isalnum() or c in "._-")[:40]
                )
    feature = ":".join(part for part in feature_parts if part) or "unspecified"
    minute, day = _utc_windows(datetime.now(UTC))
    with SessionLocal.begin() as session:
        state = session.get(AIPolicyControl, "cost_alert")
        if state and state.enabled:
            raise ProviderUnavailableError(
                "AI requests are paused after an unexpected non-zero model cost."
            )
        try:
            if quota_kind == "self_hosted":
                checks = [
                    ("self_hosted:global:minute", minute, settings.ai_self_hosted_global_rpm_limit),
                    ("self_hosted:global:day", day, settings.ai_self_hosted_global_daily_limit),
                ]
            else:
                checks = [
                    ("global:minute", minute, settings.ai_global_rpm_limit),
                    ("global:day", day, settings.ai_global_daily_limit),
                ]
            if user_id is not None:
                suffix = str(user_id)
                user_key_prefix = "self_hosted:" if quota_kind == "self_hosted" else ""
                user_rpm_limit, user_daily_limit = (
                    (
                        settings.ai_self_hosted_user_rpm_limit,
                        settings.ai_self_hosted_user_daily_limit,
                    )
                    if quota_kind == "self_hosted"
                    else _user_quota_limits(user_id, settings)
                )
                checks.extend(
                    [
                        (
                            f"{user_key_prefix}user:{suffix}:minute",
                            minute,
                            user_rpm_limit,
                        ),
                        (
                            f"{user_key_prefix}user:{suffix}:day",
                            day,
                            user_daily_limit,
                        ),
                    ]
                )
            for key, window, limit in checks:
                if not _reserve_counter(session, key, window, limit):
                    raise ProviderRateLimitError(
                        "AI free-tier request limit reached. Try again later."
                    )
        except ProviderRateLimitError:
            raise
        except ProviderUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001 - storage failures fail closed
            logger.error("AI request metering could not reserve a request (%s)", type(exc).__name__)
            raise ProviderUnavailableError(
                "AI request metering is temporarily unavailable."
            ) from exc
        event = AIUsageEvent(
            user_id=user_id,
            organization_id=organization_id,
            feature=feature,
            provider=provider,
            model=model,
            status="started",
            request_id=get_request_id(),
        )
        session.add(event)
        session.flush()
        return event.id


def _user_quota_limits(user_id: UUID, settings: Settings) -> tuple[int, int]:
    """Select tester limits only for explicitly allowlisted account UUIDs."""
    tester_ids: set[UUID] = set()
    for raw_id in settings.ai_tester_user_ids.split(","):
        try:
            tester_ids.add(UUID(raw_id.strip()))
        except (ValueError, AttributeError):
            # Invalid configuration never grants elevated limits.
            continue
    if user_id in tester_ids:
        return settings.ai_tester_user_rpm_limit, settings.ai_tester_user_daily_limit
    return settings.ai_user_rpm_limit, settings.ai_user_daily_limit


def authorize_and_reserve(
    *,
    provider: str,
    model: str,
    base_url: str,
    structured: bool,
    metadata: dict[str, Any] | None,
    has_api_key: bool,
    settings: Settings | None = None,
) -> UUID:
    """Fail closed before network access, then reserve shared quota atomically."""
    active = settings or get_settings()
    if active.ai_paid_mode_enabled or active.ai_paid_budget_usd != 0:
        raise ProviderUnavailableError(
            "Paid AI mode has no owner-approved authorization and is disabled."
        )
    normalized_url = base_url.rstrip("/").lower()
    if provider != "openrouter" or normalized_url != "https://openrouter.ai/api/v1":
        raise ProviderUnavailableError(
            "Only the approved OpenRouter free-model route is enabled for AI inference."
        )
    if not has_api_key:
        raise ProviderUnavailableError("OpenRouter is not configured for free AI inference.")
    catalog = None
    if model != "openrouter/free":
        allowlist = {
            entry.strip() for entry in active.ai_free_model_allowlist.split(",") if entry.strip()
        }
        if not model.endswith(":free") or model not in allowlist:
            raise ProviderUnavailableError(
                "The configured AI model is not approved for free inference."
            )
        catalog = _fetch_catalog()
    _approved_model(model=model, structured=structured, settings=active, catalog=catalog)
    return _new_event(provider=provider, model=model, metadata=metadata, settings=active)


def authorize_self_hosted_and_reserve(
    *,
    provider: str,
    model: str,
    metadata: dict[str, Any] | None,
    settings: Settings | None = None,
) -> UUID:
    """Reserve isolated generous quotas and a usage event for a self-hosted server."""
    if provider not in {"local", "ollama_local"}:
        raise ProviderUnavailableError("Only explicitly self-hosted providers use this policy.")
    active = settings or get_settings()
    return _new_event(
        provider=provider,
        model=model,
        metadata=metadata,
        settings=active,
        quota_kind="self_hosted",
    )


def record_result(
    event_id: UUID,
    *,
    status: str,
    response: Any = None,
    error: Exception | None = None,
) -> None:
    usage = (
        response.get("usage") if isinstance(response, dict) else getattr(response, "usage", None)
    )
    if isinstance(usage, dict):
        usage_data = usage
    else:
        usage_data = vars(usage) if usage is not None and hasattr(usage, "__dict__") else {}
    input_tokens = usage_data.get("prompt_tokens", usage_data.get("input_tokens"))
    output_tokens = usage_data.get("completion_tokens", usage_data.get("output_tokens"))
    cost_value = usage_data.get("cost")
    if cost_value is None and isinstance(response, dict):
        cost_value = response.get("cost")
    cost = None
    if cost_value is not None:
        try:
            cost = Decimal(str(cost_value))
        except (InvalidOperation, ValueError):
            cost = None
    provider_request_id = (
        response.get("id") if isinstance(response, dict) else getattr(response, "id", None)
    )
    http_status = getattr(error, "status_code", None) if error else None
    error_category = type(error).__name__[:64] if error else None
    cost_alert = cost is not None and cost > 0
    with SessionLocal.begin() as session:
        event = session.get(AIUsageEvent, event_id)
        if event is None:
            raise ProviderUnavailableError("AI usage event could not be finalized.")
        event.status = "cost_alert" if cost_alert else status
        event.http_status = http_status if isinstance(http_status, int) else None
        event.error_category = "unexpected_nonzero_cost" if cost_alert else error_category
        event.provider_request_id = str(provider_request_id)[:160] if provider_request_id else None
        event.input_tokens = input_tokens if isinstance(input_tokens, int) else None
        event.output_tokens = output_tokens if isinstance(output_tokens, int) else None
        event.reported_cost_usd = cost
        event.completed_at = datetime.now(UTC)
        if cost_alert:
            dialect = session.get_bind().dialect.name
            insert_stmt = (
                pg_insert(AIPolicyControl)
                if dialect == "postgresql"
                else sqlite_insert(AIPolicyControl)
            )
            table = AIPolicyControl.__table__
            session.execute(
                insert_stmt.values(control_key="cost_alert", enabled=True).on_conflict_do_update(
                    index_elements=[table.c.control_key], set_={"enabled": True}
                )
            )
    if cost_alert:
        logger.critical(
            "AI free-model response reported nonzero cost; global AI circuit breaker enabled."
        )
        raise ProviderUnavailableError(
            "AI requests are paused after an unexpected non-zero model cost."
        )


def add_free_routing_constraints(kwargs: dict[str, Any], *, model: str, structured: bool) -> None:
    """Require parameter-compatible routing for the OpenRouter free router."""
    if model == "openrouter/free" and structured:
        # OpenAI's SDK rejects OpenRouter-specific fields as top-level kwargs.
        # `extra_body` serializes provider routing into the request JSON body.
        extra_body = kwargs.setdefault("extra_body", {})
        extra_body["provider"] = {"require_parameters": True}
