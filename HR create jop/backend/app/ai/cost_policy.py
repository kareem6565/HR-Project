"""Fail-closed free-first enforcement and shared AI usage metering."""

from __future__ import annotations

import logging
import re
import threading
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID, uuid4

import httpx
from sqlalchemy import case, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.ai.actor_context import ai_actor_context
from app.ai.providers.errors import (
    ProviderBudgetExceededError,
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderUnavailableError,
    ProviderUsageCheckError,
)
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
# The one-time owner-approved DeepSeek route is bounded by OpenRouter's
# per-million-token max_price fields. The cap is also reserved in our monthly
# ledger before the provider request is sent.
# Caps verified against the live OpenRouter catalog (GET /api/v1/models) on
# 2026-11-25 for deepseek/deepseek-v4.1-flash-1017: $0.15/M prompt, $0.60/M
# completion. The previous values (0.03/0.20) were below the real rates, so
# every paid request failed closed at preflight.
_PAID_DEEPSEEK_MODEL = "deepseek/deepseek-v4.1-flash-1017"
_PAID_PROMPT_MAX_PRICE_PER_MILLION = Decimal("0.15")
_PAID_COMPLETION_MAX_PRICE_PER_MILLION = Decimal("0.60")
_PAID_RESERVATION_BUFFER = Decimal("1.2")
_catalog_lock = threading.Lock()
_catalog_cache: tuple[datetime, dict[str, dict[str, Any]]] | None = None
_paid_budget_lock = threading.Lock()
_paid_pending: dict[UUID, Decimal] = {}
_paid_local_spend = Decimal("0")


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
            logger.warning(
                "OpenRouter model catalog check failed; inference was not sent.",
                extra={
                    "phase": "preflight_model_catalog",
                    "exception_class": type(exc).__name__,
                    "error_code": "provider_pricing_unavailable",
                },
            )
            raise ProviderUnavailableError(
                "Could not verify model pricing and eligibility from the OpenRouter catalog.",
                error_code="provider_pricing_unavailable",
                stage="preflight",
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


def _fetch_key_usage(api_key: str) -> Decimal:
    """Read current key spend from OpenRouter without sending inference input."""
    try:
        response = httpx.get(
            "https://openrouter.ai/api/v1/key",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=8.0,
        )
        response.raise_for_status()
        usage = response.json().get("data", {}).get("usage")
        if usage is None:
            raise ValueError("OpenRouter key usage was not returned.")
        return Decimal(str(usage))
    except Exception as exc:  # noqa: BLE001 - paid calls fail closed without live spend data
        logger.warning(
            "OpenRouter usage preflight failed; inference was not sent.",
            extra={
                "phase": "preflight_usage_check",
                "exception_class": type(exc).__name__,
                "error_code": "provider_usage_check_failed",
            },
        )
        raise ProviderUsageCheckError(
            "Could not verify OpenRouter key usage before the paid request.",
            error_code="provider_usage_check_failed",
        ) from exc


def _paid_request_estimate(
    *,
    model: str,
    prompt_characters: int,
    max_output_tokens: int,
    catalog: dict[str, dict[str, Any]],
) -> Decimal:
    item = catalog.get(model)
    if not item:
        raise ProviderUnavailableError("The selected paid model is missing from the catalog.")
    pricing = item.get("pricing") or {}
    try:
        prompt_price = Decimal(str(pricing["prompt"]))
        completion_price = Decimal(str(pricing["completion"]))
    except (KeyError, InvalidOperation, ValueError) as exc:
        raise ProviderUnavailableError("The selected model has no usable price metadata.") from exc
    if prompt_price <= 0 or completion_price <= 0:
        raise ProviderUnavailableError("Paid inference requires positive model pricing metadata.")
    # Character count is intentionally treated as a conservative token count,
    # then doubled to leave room for non-English tokenization and provider variance.
    estimated_input_tokens = max(1, prompt_characters * 2)
    estimate = (
        Decimal(estimated_input_tokens) * prompt_price
        + Decimal(max_output_tokens) * completion_price
    )
    return estimate * Decimal("2")


def _database_paid_spend(*, catalog: dict[str, dict[str, Any]], budget: Decimal) -> Decimal:
    """Use persisted usage rows to retain a conservative cap across process restarts."""
    with SessionLocal() as session:
        events = session.scalars(
            select(AIUsageEvent).where(
                AIUsageEvent.model != "openrouter/free",
                ~AIUsageEvent.model.like("%:free"),
            )
        ).all()
    total = Decimal("0")
    for event in events:
        if event.status == "started":
            # A crashed in-flight request has unknown cost; fail closed for this cap.
            raise ProviderBudgetExceededError(
                "A previous AI request has unknown final usage.",
                error_code="in_flight_cost_unknown",
            )
        if event.reported_cost_usd is not None:
            total += Decimal(str(event.reported_cost_usd)) * Decimal("2")
            continue
        if event.input_tokens is None or event.output_tokens is None:
            # Provider-reported key usage is checked live before every paid
            # request. Older OpenRouter responses can omit token usage, so
            # don't treat an unmetered historical row as if it exhausted the
            # entire budget; that permanently blocks later calls.
            continue
        pricing = (catalog.get(event.model) or {}).get("pricing") or {}
        try:
            total += (
                Decimal(event.input_tokens) * Decimal(str(pricing["prompt"]))
                + Decimal(event.output_tokens) * Decimal(str(pricing["completion"]))
            ) * Decimal("2")
        except (KeyError, InvalidOperation, ValueError):
            return budget
    return total


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
    reserved_cost_usd: Decimal | None = None,
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
        if reserved_cost_usd is not None:
            dialect = session.get_bind().dialect.name
            if dialect == "postgresql":
                # Serialize reservations so concurrent paid calls cannot both
                # observe the same remaining monthly budget.
                session.execute(text("SELECT pg_advisory_xact_lock(4815162342)"))
            month_start = datetime.now(UTC).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            reserved_total = session.scalar(
                select(func.coalesce(func.sum(AIUsageEvent.reported_cost_usd), 0)).where(
                    AIUsageEvent.created_at >= month_start
                )
            ) or Decimal("0")
            if reserved_total + reserved_cost_usd > Decimal(str(settings.ai_paid_budget_usd)):
                raise ProviderUnavailableError("The approved paid AI budget is exhausted.")
        state = session.get(AIPolicyControl, "cost_alert")
        if state and state.enabled:
            raise ProviderUnavailableError(
                "AI requests are paused after an unexpected non-zero model cost.",
                error_code="cost_guard_paused",
                stage="preflight",
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
                        "AI request rate limit reached. Try again later.",
                        error_code="app_rate_limit",
                        stage="preflight",
                    )
        except ProviderRateLimitError:
            raise
        except ProviderUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001 - storage failures fail closed
            logger.error("AI request metering could not reserve a request (%s)", type(exc).__name__)
            raise ProviderUnavailableError(
                "AI request metering is temporarily unavailable.",
                error_code="ai_metering_unavailable",
                stage="preflight",
            ) from exc
        event = AIUsageEvent(
            user_id=user_id,
            organization_id=organization_id,
            feature=feature,
            provider=provider,
            model=model,
            status="started",
            request_id=get_request_id() or str(uuid4()),
            reported_cost_usd=reserved_cost_usd,
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
    api_key: str | None = None,
    prompt_characters: int = 0,
    input_bytes: int = 0,
    max_output_tokens: int | None = None,
    has_api_key: bool | None = None,
    settings: Settings | None = None,
) -> UUID:
    """Fail closed before network access, then reserve quota and any paid budget."""
    active = settings or get_settings()
    paid_model = model != "openrouter/free" and not model.endswith(":free")
    if active.ai_paid_mode_enabled and active.ai_paid_budget_usd <= 0:
        raise ProviderConfigurationError("Paid AI mode requires a positive spend cap.")
    if active.ai_paid_budget_usd != 0 and not active.ai_paid_mode_enabled:
        raise ProviderConfigurationError(
            "Paid AI mode is disabled; enable it explicitly before setting a paid budget."
        )
    if paid_model and (not active.ai_paid_mode_enabled or active.ai_paid_budget_usd <= 0):
        raise ProviderConfigurationError("Paid AI mode is disabled or has no positive test cap.")
    if not api_key and not has_api_key:
        raise ProviderConfigurationError(
            "OPENROUTER_API_KEY is required for AI inference.", error_code="missing_api_key"
        )
    normalized_url = base_url.rstrip("/").lower()
    if provider != "openrouter" or normalized_url != "https://openrouter.ai/api/v1":
        raise ProviderConfigurationError(
            "Only the configured OpenRouter route is enabled for AI inference."
        )

    catalog = _fetch_catalog() if paid_model or model != "openrouter/free" else None
    estimate = Decimal("0")
    current_key_usage: Decimal | None = None
    if paid_model:
        paid_allowlist = {
            entry.strip() for entry in active.ai_paid_model_allowlist.split(",") if entry.strip()
        }
        if model != _PAID_DEEPSEEK_MODEL or model not in paid_allowlist:
            raise ProviderConfigurationError(
                "The configured paid model is not explicitly owner-approved."
            )
        if max_output_tokens is None:
            raise ProviderConfigurationError(
                "Paid AI requests require a finite output-token limit."
            )
        item = (catalog or {}).get(model)
        if not item:
            raise ProviderConfigurationError("The approved paid model is missing from OpenRouter.")
        architecture = item.get("architecture") or {}
        if "text" not in (architecture.get("input_modalities") or []) or "text" not in (
            architecture.get("output_modalities") or []
        ):
            raise ProviderConfigurationError("The approved model does not support text inference.")
        if structured and "response_format" not in (item.get("supported_parameters") or []):
            raise ProviderConfigurationError("The approved model lacks structured JSON support.")
        pricing = item.get("pricing") or {}
        try:
            input_rate = Decimal(str(pricing["prompt"])) * Decimal(1_000_000)
            output_rate = Decimal(str(pricing["completion"])) * Decimal(1_000_000)
        except (KeyError, InvalidOperation, ValueError):
            raise ProviderConfigurationError("Paid model pricing could not be verified.") from None
        if (
            input_rate <= 0
            or output_rate <= 0
            or input_rate > _PAID_PROMPT_MAX_PRICE_PER_MILLION
            or output_rate > _PAID_COMPLETION_MAX_PRICE_PER_MILLION
        ):
            raise ProviderConfigurationError(
                "Paid model pricing exceeds the approved per-call limit."
            )
        estimate = _paid_request_estimate(
            model=model,
            prompt_characters=max(prompt_characters, input_bytes),
            max_output_tokens=max_output_tokens,
            catalog=catalog or {},
        )
        current_key_usage = _fetch_key_usage(api_key or "")
        if current_key_usage < active.ai_paid_budget_baseline_usd:
            raise ProviderUsageCheckError(
                "OpenRouter usage does not match the configured test baseline; "
                "no request was sent.",
                error_code="usage_baseline_mismatch",
            )
    elif model != "openrouter/free":
        free_allowlist = {
            entry.strip() for entry in active.ai_free_model_allowlist.split(",") if entry.strip()
        }
        if not model.endswith(":free") or model not in free_allowlist:
            raise ProviderConfigurationError(
                "The configured AI model is not approved for free inference."
            )
    if not paid_model:
        _approved_model(model=model, structured=structured, settings=active, catalog=catalog)
        return _new_event(provider=provider, model=model, metadata=metadata, settings=active)

    global _paid_local_spend
    assert current_key_usage is not None
    provider_spend = max(
        Decimal("0"),
        Decimal(str(current_key_usage)) - Decimal(str(active.ai_paid_budget_baseline_usd)),
    )
    database_spend = _database_paid_spend(
        catalog=catalog or {}, budget=Decimal(str(active.ai_paid_budget_usd))
    )
    with _paid_budget_lock:
        spent = max(provider_spend, database_spend, _paid_local_spend)
        pending = sum(_paid_pending.values(), Decimal("0"))
        budget = Decimal(str(active.ai_paid_budget_usd))
        if spent + pending + estimate > budget:
            logger.warning(
                "AI request stopped by the application test budget; inference was not sent.",
                extra={
                    "phase": "preflight_budget_check",
                    "error_code": "app_test_budget_exceeded",
                    "provider": provider,
                    "model": model,
                    "estimated_cost_usd": str(estimate),
                    "spent_usd": str(spent),
                    "budget_usd": str(budget),
                    "remaining_usd": str(max(Decimal("0"), budget - spent - pending)),
                },
            )
            raise ProviderBudgetExceededError(
                "The configured OpenRouter test spend cap would be exceeded by this request."
            )
        event_id = _new_event(provider=provider, model=model, metadata=metadata, settings=active)
        _paid_pending[event_id] = estimate
        return event_id


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
    prompt_characters: int | None = None,
) -> None:
    """Persist provider diagnostics and pause inference on unexpected spend."""
    global _paid_local_spend
    usage = (
        response.get("usage") if isinstance(response, dict) else getattr(response, "usage", None)
    )
    usage_data = (
        usage
        if isinstance(usage, dict)
        else (vars(usage) if usage is not None and hasattr(usage, "__dict__") else {})
    )
    input_tokens = usage_data.get("prompt_tokens", usage_data.get("input_tokens"))
    output_tokens = usage_data.get("completion_tokens", usage_data.get("output_tokens"))
    cost_value = usage_data.get("cost")
    if cost_value is None and isinstance(response, dict):
        cost_value = response.get("cost")
    try:
        cost = Decimal(str(cost_value)) if cost_value is not None else None
    except (InvalidOperation, ValueError):
        cost = None
    provider_request_id = (
        response.get("id") if isinstance(response, dict) else getattr(response, "id", None)
    )
    if not provider_request_id and error is not None:
        provider_request_id = getattr(error, "provider_request_id", None)
    http_status = (
        getattr(error, "provider_status", None) or getattr(error, "status_code", None)
        if error
        else (200 if response is not None else None)
    )
    error_category = getattr(error, "error_code", type(error).__name__)[:64] if error else None
    cost_alert = cost is not None and cost > 0
    paid_model = False
    reserved = Decimal("0")
    log_fields: dict[str, Any] = {}
    with SessionLocal.begin() as session:
        event = session.get(AIUsageEvent, event_id)
        if event is None:
            raise ProviderUnavailableError("AI usage event could not be finalized.")
        paid_model = event.model == _PAID_DEEPSEEK_MODEL
        if paid_model:
            cost_alert = False
            with _paid_budget_lock:
                reserved = _paid_pending.pop(event_id, Decimal("0"))
        event.status = "cost_alert" if cost_alert else status
        event.http_status = http_status if isinstance(http_status, int) else None
        event.error_category = "unexpected_nonzero_cost" if cost_alert else error_category
        event.provider_request_id = str(provider_request_id)[:160] if provider_request_id else None
        event.input_tokens = input_tokens if isinstance(input_tokens, int) else None
        event.output_tokens = output_tokens if isinstance(output_tokens, int) else None
        if cost is not None:
            event.reported_cost_usd = cost
        completed_at = datetime.now(UTC)
        event.completed_at = completed_at
        started_at = event.created_at
        # SQLite drops timezone information from DateTime(timezone=True); treat
        # its naive value as UTC before computing a duration.
        if started_at is not None and started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=UTC)
        latency_ms = (
            round((completed_at - started_at).total_seconds() * 1000) if started_at else None
        )
        log_fields = {
            "request_id": event.request_id,
            "provider": event.provider,
            "model": event.model,
            "feature": event.feature,
            "phase": "provider_call",
            "status": "cost_alert" if cost_alert else status,
            "duration_ms": latency_ms,
            "input_characters": prompt_characters,
            "provider_status": http_status,
            "provider_request_id": str(provider_request_id)[:160] if provider_request_id else None,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "error_code": error_category,
            "retryable": getattr(error, "retryable", False) if error else False,
        }
        if paid_model:
            actual_cost = cost if cost is not None else reserved
            with _paid_budget_lock:
                _paid_local_spend += actual_cost
                active = get_settings()
                over_cap = _paid_local_spend > Decimal(str(active.ai_paid_budget_usd))
                estimate_exceeded = cost is not None and cost > reserved
            if over_cap or estimate_exceeded:
                event.status = "cost_alert"
                event.error_category = (
                    "paid_spend_cap_exceeded" if over_cap else "paid_cost_estimate_exceeded"
                )
                cost_alert = True
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
    logger.log(
        logging.WARNING if status != "succeeded" or cost_alert else logging.INFO,
        "AI provider call completed with an error"
        if status != "succeeded" or cost_alert
        else "AI provider call completed",
        extra=log_fields,
    )
    if cost_alert:
        logger.critical(
            "AI spend policy detected an unexpected charge; global AI circuit breaker enabled."
        )
        raise ProviderUnavailableError(
            "AI requests are paused after an unexpected non-zero model cost."
        )


def record_ai_output_validation_failure(*, error_code: str) -> None:
    """Mark the matching provider attempt failed when its JSON violates our schema."""
    request_id = get_request_id()
    if not request_id:
        return
    with SessionLocal.begin() as session:
        event = session.scalar(select(AIUsageEvent).where(AIUsageEvent.request_id == request_id))
        if event is not None and event.status == "succeeded":
            event.status = "failed"
            event.error_category = error_code[:64]


def add_free_routing_constraints(kwargs: dict[str, Any], *, model: str, structured: bool) -> None:
    """Require parameter-compatible routing for the OpenRouter free router."""
    if model == "openrouter/free" and structured:
        # OpenAI's SDK rejects OpenRouter-specific fields as top-level kwargs.
        # `extra_body` serializes provider routing into the request JSON body.
        extra_body = kwargs.setdefault("extra_body", {})
        extra_body["provider"] = {"require_parameters": True}


def add_paid_routing_constraints(kwargs: dict[str, Any], *, model: str) -> None:
    """Keep the approved DeepSeek request on parameter-compatible, price-capped routes."""
    if model != _PAID_DEEPSEEK_MODEL:
        raise ProviderUnavailableError("Paid routing is not approved for this model.")
    extra_body = kwargs.setdefault("extra_body", {})
    extra_body["provider"] = {
        "require_parameters": True,
        "sort": "price",
        "allow_fallbacks": False,
        "max_price": {
            "prompt": float(_PAID_PROMPT_MAX_PRICE_PER_MILLION),
            "completion": float(_PAID_COMPLETION_MAX_PRICE_PER_MILLION),
        },
    }
