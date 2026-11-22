"""Offline regression tests for synthetic provider benchmark metrics."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.ai.providers.base import StructuredGenerationRequest
from app.ai.providers.errors import ProviderTimeoutError
from app.ai.providers.fake import FakeAIProvider

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "tools" / "eval_quality.py"
_SPEC = importlib.util.spec_from_file_location("hera_eval_quality", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_QUALITY = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_QUALITY)
MeteredProvider = _QUALITY.MeteredProvider
evidence_metrics = _QUALITY.evidence_metrics
render_provider_report = _QUALITY.render_provider_report
run_provider_benchmark = _QUALITY.run_provider_benchmark
Settings = _QUALITY.Settings


def test_evidence_metrics_compare_expected_labels_and_grounded_quotes() -> None:
    cases = [
        {
            "cv_text": "I use Python daily and build services with FastAPI.",
            "expected_evidence": {
                "Python": "matched",
                "SQL Database": "missing",
                "FastAPI": "matched",
            },
            "expected_quote_fragments": {"Python": "I use Python daily."},
        }
    ]
    predictions = [
        {
            "Python": {
                "evidence_type": "matched",
                "candidate_evidence": {
                    "quote": "I use Python daily.",
                    "quote_verified": True,
                },
            },
            "SQL Database": {"evidence_type": "partial", "candidate_evidence": {}},
        }
    ]

    metrics = evidence_metrics(cases, predictions)

    assert metrics["evidence_true_positive"] == 1
    assert metrics["evidence_false_positive"] == 1
    assert metrics["evidence_false_negative"] == 1
    assert metrics["evidence_precision"] == 0.5
    assert metrics["evidence_recall"] == 0.5
    assert metrics["verified_quote_rate"] == 0.5


def test_failed_case_counts_expected_support_as_a_false_negative() -> None:
    cases = [{"cv_text": "I use Python.", "expected_evidence": {"Python": "matched"}}]

    metrics = evidence_metrics(cases, [None])

    assert metrics["evidence_false_negative"] == 1
    assert metrics["evidence_recall"] == 0.0


def test_metered_provider_counts_valid_json_and_safe_provider_failures() -> None:
    request = StructuredGenerationRequest(input="synthetic-only")
    provider = MeteredProvider(FakeAIProvider(structured_payload={"items": []}))
    provider.generate_structured(request)

    assert provider.calls == 1
    assert provider.valid_json_responses == 1
    assert provider.failed_calls == 0

    failing_provider = MeteredProvider(FakeAIProvider(failure=ProviderTimeoutError("timeout")))
    with pytest.raises(ProviderTimeoutError):
        failing_provider.generate_structured(request)

    assert failing_provider.calls == 1
    assert failing_provider.valid_json_responses == 0
    assert failing_provider.failed_calls == 1


def test_compact_report_includes_required_metrics_without_inputs() -> None:
    output = render_provider_report(
        {
            "provider": "local",
            "model": "synthetic-model",
            "cases": 9,
            "valid_json_rate": 1.0,
            "evidence_precision": 0.8,
            "evidence_recall": 0.75,
            "verified_quote_rate": 0.9,
            "average_latency_ms": 120.4,
            "provider_calls_per_cv": 2.0,
            "provider_failures": 0,
            "case_failures": 0,
        }
    )

    assert "Valid JSON rate" in output
    assert "Evidence precision" in output
    assert "Evidence recall" in output
    assert "Verified quote rate" in output
    assert "Average latency / CV" in output
    assert "Provider calls / CV" in output
    assert "synthetic-only" not in output


def test_benchmark_refuses_fake_mode_as_a_model_candidate(capsys) -> None:
    status = run_provider_benchmark(Settings(APP_ENV="test", AI_PROVIDER="fake"))

    assert status == 2
    assert "cannot benchmark a model" in capsys.readouterr().err
