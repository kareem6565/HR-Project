"""Offline regression checks for the versioned synthetic Ollama quality set."""

from __future__ import annotations

import json
from pathlib import Path

from app.ai.contracts import normalize_job_profile_requirements
from app.services.scoring_service import ScoringService

CASES_PATH = Path(__file__).parent / "data" / "ollama_quality_cases.json"


def load_cases() -> list[dict]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def test_synthetic_model_cases_are_versioned_and_distinct() -> None:
    cases = load_cases()

    assert len(cases) == 8
    assert len({case["id"] for case in cases}) == 8
    assert all(case["cv_text"].strip() for case in cases)
    assert all(case["expected_score"] in range(101) for case in cases)


def test_expected_scores_follow_unchanged_backend_scoring_rules() -> None:
    for case in load_cases():
        requirements = normalize_job_profile_requirements(case["requirements"])
        expected_by_text = case["expected_evidence"]
        evidence_by_key = {
            requirement.key: expected_by_text[requirement.text]
            for requirement in requirements
        }

        result = ScoringService().compute(requirements, evidence_by_key)

        assert float(result["score"]) == case["expected_score"], case["id"]


def test_positive_expected_evidence_has_an_exact_source_quote() -> None:
    for case in load_cases():
        for requirement, quote_fragment in case["expected_quote_fragments"].items():
            assert quote_fragment in case["cv_text"], (case["id"], requirement)


def test_injection_case_contains_unsupported_claim_only_in_instruction_text() -> None:
    injection_case = next(
        case for case in load_cases() if case["id"] == "prompt_injection_and_fabricated_claim"
    )

    assert "SYSTEM INSTRUCTION" in injection_case["cv_text"]
    assert "I operated Kubernetes clusters for five years." in injection_case["cv_text"]
    assert injection_case["expected_evidence"]["Kubernetes"] == "missing"
