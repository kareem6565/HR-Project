from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import Mock
from uuid import UUID

import pytest
from pydantic import BaseModel
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.ai import cost_policy
from app.ai.actor_context import ai_actor_context
from app.ai.providers.base import StructuredGenerationRequest, TextGenerationRequest
from app.ai.providers.errors import ProviderRateLimitError, ProviderUnavailableError
from app.ai.providers.openrouter import OpenRouterProvider
from app.core.config import Settings
from app.core.database import Base
from app.core import logging as app_logging
from app.models.ai_usage import AIPolicyControl, AIUsageCounter, AIUsageEvent


class _Answer(BaseModel):
    answer: str


@pytest.fixture()
def policy_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'ai-policy.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(cost_policy, "SessionLocal", factory)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


def _settings(**overrides) -> Settings:
    values = {
        "app_env": "test",
        "jwt_secret_key": "unit-test-jwt-secret-that-is-long-enough",
        "ai_provider": "openrouter",
        "openrouter_api_key": "test-only-key",
        "openrouter_base_url": "https://openrouter.ai/api/v1",
        "openrouter_model": "openrouter/free",
        "ai_global_rpm_limit": 15,
        "ai_global_daily_limit": 40,
        "ai_user_rpm_limit": 5,
        "ai_user_daily_limit": 20,
        "ai_tester_user_ids": "",
        "ai_tester_user_rpm_limit": 10,
        "ai_tester_user_daily_limit": 60,
    }
    values.update(overrides)
    return Settings(**values)


def test_allowlisted_tester_gets_only_the_configured_higher_user_limits():
    tester_id = UUID("0b56197f-512d-4a61-92b7-8127283dfcfc")
    settings = _settings(ai_tester_user_ids=str(tester_id))

    assert cost_policy._user_quota_limits(tester_id, settings) == (10, 60)
    ordinary_user_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    assert cost_policy._user_quota_limits(ordinary_user_id, settings) == (5, 20)


def test_invalid_tester_allowlist_never_grants_elevated_limits():
    settings = _settings(ai_tester_user_ids="not-a-uuid, ")

    assert cost_policy._user_quota_limits(
        UUID("0b56197f-512d-4a61-92b7-8127283dfcfc"), settings
    ) == (5, 20)


def test_output_validation_failure_updates_provider_attempt_and_keeps_safe_field_paths(monkeypatch):
    request_id = "test-request-output-schema"
    from types import SimpleNamespace

    event = SimpleNamespace(status="succeeded", error_category=None)

    class SessionContext:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def scalar(self, _query):
            return event

    class SessionFactory:
        @staticmethod
        def begin():
            return SessionContext()

    monkeypatch.setattr(cost_policy, "SessionLocal", SessionFactory)
    token = app_logging.set_request_id(request_id)
    try:
        cost_policy.record_ai_output_validation_failure(error_code="invalid_ai_output")
    finally:
        app_logging.request_id_context.reset(token)

    assert event.status == "failed"
    assert event.error_category == "invalid_ai_output"
    safe_errors = app_logging._safe_diagnostic_context(
        "validation_errors",
        [{"location": ["title"], "type": "missing"}],
    )
    assert safe_errors == [{"location": ["title"], "type": "missing"}]
    assert app_logging._safe_diagnostic_context(
        "provider_request_id", "gen-1234567890123-abc"
    ) == "gen-1234567890123-abc"


def _catalog_model(*, prompt="0", completion="0", supported=None):
    return {
        "id": "example/model:free",
        "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
        "pricing": {"prompt": prompt, "completion": completion},
        "supported_parameters": supported or ["response_format"],
    }


def test_approved_free_model_is_catalog_verified_and_metered(policy_db, monkeypatch):
    s = _settings(
        openrouter_model="example/model:free",
        ai_free_model_allowlist="example/model:free",
    )
    monkeypatch.setattr(
        cost_policy, "_fetch_catalog", lambda: {"example/model:free": _catalog_model()}
    )
    event_id = cost_policy.authorize_and_reserve(
        provider="openrouter",
        model=s.openrouter_model,
        base_url=s.openrouter_base_url,
        structured=True,
        metadata={"workflow": "resume_extraction"},
        has_api_key=True,
        settings=s,
    )
    cost_policy.record_result(
        event_id,
        status="succeeded",
        response={"id": "req-test", "usage": {"prompt_tokens": 11, "completion_tokens": 7}},
    )
    with policy_db() as session:
        event = session.get(AIUsageEvent, event_id)
        assert event.status == "succeeded"
        assert event.feature == "resume_extraction"
        assert event.input_tokens == 11
        assert event.output_tokens == 7
        assert event.reported_cost_usd is None
        assert session.scalar(select(func.sum(AIUsageCounter.request_count))) == 2


@pytest.mark.parametrize(
    ("model", "catalog", "allowlist"),
    [
        ("deepseek/deepseek-v4.1-flash-1017", {}, ""),
        ("unlisted/model:free", {}, ""),
        (
            "example/model:free",
            {"example/model:free": _catalog_model(prompt="0.01")},
            "example/model:free",
        ),
        (
            "example/model:free",
            {
                "example/model:free": {
                    **_catalog_model(),
                    "pricing": {"prompt": "0", "completion": None},
                }
            },
            "example/model:free",
        ),
    ],
)
def test_paid_unknown_or_unpriced_model_is_rejected_before_inference(
    policy_db, monkeypatch, model, catalog, allowlist
):
    monkeypatch.setattr(cost_policy, "_fetch_catalog", lambda: catalog)
    provider = OpenRouterProvider(api_key="test-only-key", model=model)
    provider.cost_policy_enabled = True
    provider._client.chat.completions.create = Mock()
    s = _settings(openrouter_model=model, ai_free_model_allowlist=allowlist)
    monkeypatch.setattr(cost_policy, "get_settings", lambda: s)
    with pytest.raises(ProviderUnavailableError):
        provider.generate_text(TextGenerationRequest(input="synthetic"))
    provider._client.chat.completions.create.assert_not_called()


def test_direct_provider_construction_is_guarded_by_default():
    provider = OpenRouterProvider(
        api_key="test-only-key", model="deepseek/deepseek-v4.1-flash-1017"
    )
    provider._client.chat.completions.create = Mock()
    assert provider.cost_policy_enabled is True
    with pytest.raises(ProviderUnavailableError):
        provider.generate_text(TextGenerationRequest(input="synthetic"))
    provider._client.chat.completions.create.assert_not_called()


def test_special_openrouter_free_route_requires_parameter_compatible_routing(
    policy_db, monkeypatch
):
    monkeypatch.setattr(cost_policy, "get_settings", lambda: _settings())
    provider = OpenRouterProvider(api_key="test-only-key", model="openrouter/free")
    provider.cost_policy_enabled = True
    provider._client.chat.completions.create = Mock(
        return_value={
            "id": "req-free",
            "choices": [{"message": {"content": '{"answer":"ok"}'}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 2},
        }
    )
    result = provider.generate_structured(
        StructuredGenerationRequest(input="synthetic only", output_schema=_Answer)
    )
    assert result.data == {"answer": "ok"}
    kwargs = provider._client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "openrouter/free"
    assert kwargs["extra_body"]["provider"] == {"require_parameters": True}


def test_limits_return_429_and_never_fall_back_to_fake_or_paid(policy_db, monkeypatch):
    s = _settings(ai_global_rpm_limit=1)
    monkeypatch.setattr(cost_policy, "get_settings", lambda: s)
    provider = OpenRouterProvider(api_key="test-only-key", model="openrouter/free")
    provider.cost_policy_enabled = True
    provider._client.chat.completions.create = Mock(
        return_value={"choices": [{"message": {"content": "ok"}}]}
    )
    provider.generate_text(TextGenerationRequest(input="synthetic one"))
    with pytest.raises(ProviderRateLimitError):
        provider.generate_text(TextGenerationRequest(input="synthetic two"))
    assert provider._client.chat.completions.create.call_count == 1


@pytest.mark.parametrize("limit_name", ["ai_global_rpm_limit", "ai_global_daily_limit"])
def test_minute_and_daily_limits_enforced(policy_db, monkeypatch, limit_name):
    s = _settings(**{limit_name: 1})
    for _ in range(1):
        cost_policy.authorize_and_reserve(
            provider="openrouter",
            model="openrouter/free",
            base_url=s.openrouter_base_url,
            structured=False,
            metadata=None,
            has_api_key=True,
            settings=s,
        )
    with pytest.raises(ProviderRateLimitError):
        cost_policy.authorize_and_reserve(
            provider="openrouter",
            model="openrouter/free",
            base_url=s.openrouter_base_url,
            structured=False,
            metadata=None,
            has_api_key=True,
            settings=s,
        )


def test_concurrent_workers_cannot_exceed_global_window(policy_db):
    s = _settings(ai_global_rpm_limit=4)
    barrier = Barrier(12)

    def reserve_one() -> bool:
        barrier.wait()
        try:
            cost_policy.authorize_and_reserve(
                provider="openrouter",
                model="openrouter/free",
                base_url=s.openrouter_base_url,
                structured=False,
                metadata=None,
                has_api_key=True,
                settings=s,
            )
            return True
        except ProviderRateLimitError:
            return False

    with ThreadPoolExecutor(max_workers=12) as pool:
        outcomes = list(pool.map(lambda _: reserve_one(), range(12)))
    assert sum(outcomes) == 4


def test_per_user_limit_is_scoped_to_authenticated_actor(policy_db):
    s = _settings(ai_user_rpm_limit=1)
    actor_one = (
        UUID("00000000-0000-0000-0000-000000000001"),
        UUID("00000000-0000-0000-0000-000000000101"),
    )
    actor_two = (
        UUID("00000000-0000-0000-0000-000000000002"),
        UUID("00000000-0000-0000-0000-000000000102"),
    )
    token = ai_actor_context.set(actor_one)
    try:
        cost_policy.authorize_and_reserve(
            provider="openrouter",
            model="openrouter/free",
            base_url=s.openrouter_base_url,
            structured=False,
            metadata=None,
            has_api_key=True,
            settings=s,
        )
        with pytest.raises(ProviderRateLimitError):
            cost_policy.authorize_and_reserve(
                provider="openrouter",
                model="openrouter/free",
                base_url=s.openrouter_base_url,
                structured=False,
                metadata=None,
                has_api_key=True,
                settings=s,
            )
    finally:
        ai_actor_context.reset(token)
    token = ai_actor_context.set(actor_two)
    try:
        cost_policy.authorize_and_reserve(
            provider="openrouter",
            model="openrouter/free",
            base_url=s.openrouter_base_url,
            structured=False,
            metadata=None,
            has_api_key=True,
            settings=s,
        )
    finally:
        ai_actor_context.reset(token)


def test_sensitive_identifiers_are_minimized_without_erasing_dates():
    minimized = cost_policy.minimize_hr_identifiers(
        "Applied 2026-11-14; contact jordan.lee@example.test, +1 (555) 432-8765; "
        "profile https://linkedin.example/jordan"
    )
    assert "jordan.lee@example.test" not in minimized
    assert "+1 (555) 432-8765" not in minimized
    assert "https://linkedin.example" not in minimized
    assert "2026-11-14" in minimized


def test_paid_mode_or_nonzero_cost_fails_closed(policy_db, monkeypatch):
    s = _settings(ai_paid_mode_enabled=True)
    with pytest.raises(ProviderUnavailableError):
        cost_policy.authorize_and_reserve(
            provider="openrouter",
            model="openrouter/free",
            base_url=s.openrouter_base_url,
            structured=False,
            metadata=None,
            has_api_key=True,
            settings=s,
        )
    s.ai_paid_mode_enabled = False
    event_id = cost_policy.authorize_and_reserve(
        provider="openrouter",
        model="openrouter/free",
        base_url=s.openrouter_base_url,
        structured=False,
        metadata=None,
        has_api_key=True,
        settings=s,
    )
    with pytest.raises(ProviderUnavailableError, match="paused"):
        cost_policy.record_result(
            event_id, status="succeeded", response={"usage": {"cost": "0.0001"}}
        )
    with policy_db() as session:
        assert session.get(AIPolicyControl, "cost_alert").enabled is True


def test_missing_api_key_does_not_activate_fake_provider(monkeypatch):
    from app.ai.providers.errors import ProviderConfigurationError
    from app.ai.providers.factory import get_provider, resolve_ai_config

    s = _settings(openrouter_api_key=None)
    assert resolve_ai_config(s)["provider"] == "openrouter"
    assert resolve_ai_config(s)["is_fake"] is False
    with pytest.raises(ProviderConfigurationError):
        get_provider(s)


def test_explicit_other_provider_is_blocked_by_policy_before_http(policy_db):
    with pytest.raises(ProviderUnavailableError):
        cost_policy.authorize_and_reserve(
            provider="soal",
            model="gemini-3.5-flash",
            base_url="https://soal.help/api/v1",
            structured=False,
            metadata=None,
            has_api_key=True,
            settings=_settings(ai_provider="soal"),
        )
