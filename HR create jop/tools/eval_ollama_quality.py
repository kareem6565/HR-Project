#!/usr/bin/env python3
"""Opt-in, database-free synthetic quality check for Ollama gemma4:31b.

Run from the repository root with:
    python tools/eval_ollama_quality.py

This script uses only ``CandidateEvaluationWorkflow.generate``. It does not
open a database, call ``run``/``persist``, or use candidate records.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ai.providers.ollama_cloud import OllamaCloudProvider
from app.ai.workflows import CandidateEvaluationWorkflow
from app.core.config import Settings
from app.services.text_normalization import find_quote_in_source

CASES_PATH = BACKEND_DIR / "tests" / "data" / "ollama_quality_cases.json"
PINNED_MODEL = "gemma4:31b"


def _token_total(usage: dict[str, Any] | None) -> int | None:
    if not usage:
        return None
    total = usage.get("total_tokens")
    if isinstance(total, int):
        return total
    input_tokens = usage.get("input_tokens", usage.get("prompt_tokens"))
    output_tokens = usage.get("output_tokens", usage.get("completion_tokens"))
    values = [value for value in (input_tokens, output_tokens) if isinstance(value, int)]
    return sum(values) if values else None


def _render_optional(value: int | None) -> str:
    return str(value) if value is not None else "n/a"


def main() -> int:
    settings = Settings(_env_file=BACKEND_DIR / ".env")
    api_key = settings.ollama_api_key
    if not api_key:
        print("OLLAMA_API_KEY is not configured; no requests were sent.", file=sys.stderr)
        return 2

    provider = OllamaCloudProvider(
        api_key=api_key,
        model=PINNED_MODEL,
        base_url=settings.ollama_base_url,
    )
    workflow = CandidateEvaluationWorkflow(
        evidence_provider=provider,
        explanation_provider=provider,
    )
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    failures = 0
    aggregate_latency = 0
    aggregate_tokens = 0
    token_reports = 0

    print(f"Synthetic Ollama evaluation: model={PINNED_MODEL}, cases={len(cases)}")
    print("No database is opened; no candidate records are read or written.")

    for case in cases:
        try:
            payload = workflow.generate(
                job_title=f"Synthetic evaluation: {case['id']}",
                requirements_data=case["requirements"],
                candidate_skills=[],
                resume_text=case["cv_text"],
            )
            requirement_text_by_key = {
                requirement.key: requirement.text for requirement in payload.requirements
            }
            actual_by_text = {
                requirement_text_by_key[item.requirement_ref["requirement_key"]]: item
                for item in payload.evidence.evidence_items
            }
            expected_by_text = case["expected_evidence"]
            evidence_ok = True
            for requirement_text, expected_type in expected_by_text.items():
                item = actual_by_text.get(requirement_text)
                if item is None or item.evidence_type != expected_type:
                    evidence_ok = False
                    continue
                if expected_type in {"matched", "partial"}:
                    candidate_evidence = item.candidate_evidence or {}
                    quote = candidate_evidence.get("quote")
                    expected_quote_fragment = case.get("expected_quote_fragments", {}).get(
                        requirement_text
                    )
                    quote_is_grounded, _location = find_quote_in_source(
                        str(quote or ""), case["cv_text"]
                    )
                    if (
                        candidate_evidence.get("quote_verified") is not True
                        or not quote
                        or not quote_is_grounded
                        or (
                            expected_quote_fragment is not None
                            and expected_quote_fragment not in str(quote)
                        )
                    ):
                        evidence_ok = False

            score = float(payload.score_result["score"])
            score_ok = score == case["expected_score"]
            passed = evidence_ok and score_ok
            failures += not passed
            latency = (payload.evidence_result.latency_ms or 0) + (
                payload.explanation_result.latency_ms or 0
            )
            aggregate_latency += latency
            evidence_tokens = _token_total(payload.evidence_result.token_usage)
            explanation_tokens = _token_total(payload.explanation_result.token_usage)
            case_tokens = [
                value for value in (evidence_tokens, explanation_tokens) if value is not None
            ]
            if case_tokens:
                aggregate_tokens += sum(case_tokens)
                token_reports += 1

            matched = sum(
                item.evidence_type == "matched" for item in payload.evidence.evidence_items
            )
            partial = sum(
                item.evidence_type == "partial" for item in payload.evidence.evidence_items
            )
            missing = sum(
                item.evidence_type == "missing" for item in payload.evidence.evidence_items
            )
            print(
                f"{case['id']}: {'PASS' if passed else 'FAIL'} "
                f"score={score:g}/{case['expected_score']} "
                f"evidence={matched}/{partial}/{missing} "
                f"quote_checks={'passed' if evidence_ok else 'failed'} "
                f"latency_ms={latency} "
                f"tokens={_render_optional(sum(case_tokens) if case_tokens else None)}"
            )
        except Exception as error:  # report a safe type only; never print CV/provider payloads
            failures += 1
            print(f"{case['id']}: ERROR type={type(error).__name__}")

    average_latency = aggregate_latency / len(cases) if cases else 0
    print(
        f"Summary: passed={len(cases) - failures}/{len(cases)} "
        f"average_latency_ms={average_latency:.0f} "
        f"reported_token_cases={token_reports}/{len(cases)} "
        f"total_reported_tokens={aggregate_tokens if token_reports else 'n/a'}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
