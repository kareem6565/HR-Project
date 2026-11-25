"""Known-label checks for the synthetic A5 benchmark and lexical baseline."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "tools" / "eval_a5_preranking.py"
_SPEC = importlib.util.spec_from_file_location("hera_eval_a5", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_EVAL = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_EVAL)


def test_data_analyst_ground_truth_contains_all_required_skills_for_strong_labels():
    candidates, positives, profile = _EVAL.synthetic_cohort("analytics")

    _EVAL.validate_analytics_labels(candidates, positives)
    assert len(candidates) == 120
    assert len(positives) == 24
    strong_texts = [
        candidate.cv_text for candidate in candidates if candidate.identity in positives
    ]
    arabic_strong = sum(any("\u0600" <= char <= "\u06ff" for char in text) for text in strong_texts)
    assert arabic_strong == 12
    assert len(profile["requirements"]) == 4
    assert profile["requirements"] == ["SQL", "Python", "Tableau", "Microsoft Excel"]


def test_lexical_baseline_reports_r_precision_at_known_positive_count():
    candidates, positives, profile = _EVAL.synthetic_cohort("analytics")

    ranked = _EVAL.lexical_rank(candidates, profile["requirements"])
    hits, n, precision = _EVAL.r_precision(ranked, positives)

    assert n == len(positives)
    assert hits == n
    assert precision == 1.0


def test_bilingual_skill_aliases_retrieve_cross_language_known_positive_cases():
    for _case_id, requirements, candidates, positives in _EVAL.cross_language_cases():
        ranked = _EVAL.lexical_rank(candidates, requirements, bilingual_aliases=True)
        assert ranked[0] in positives


def test_synonym_case_matches_accountant_and_arabic_mohaseb():
    import pytest

    from app.services.advisory_preranking_service import PreRankingUnavailable

    _case_id, requirements, candidates, positives = _EVAL.cross_language_cases()[2]
    with pytest.raises(PreRankingUnavailable, match="No eligible CV terms matched"):
        _EVAL.lexical_rank(candidates, requirements, bilingual_aliases=False)
    bilingual = _EVAL.lexical_rank(candidates, requirements, bilingual_aliases=True)
    assert bilingual[0] in positives
