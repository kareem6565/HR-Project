from __future__ import annotations

import pytest

from app.core.config import Settings, settings
from app.services.advisory_preranking_service import CandidateText, PreRankingUnavailable
from app.services.lexical_preranking_service import rank_lexically
from app.services.text_normalization import normalize_for_matching


def test_arabic_alef_diacritics_and_tatweel_normalize_to_same_terms():
    assert normalize_for_matching("إِكْســــل") == normalize_for_matching("اكسل")


def test_bilingual_alias_matches_accountant_and_arabic_synonym():
    ranked = rank_lexically(
        ["Accountant", "Accounts payable", "Microsoft Excel"],
        [
            CandidateText("decoy", "Experience\nBuilt dashboards with Python and Tableau."),
            CandidateText(
                "strong",
                "Experience\nعملت محاسبا ماليا وأدرت الحسابات الدائنة وتسوية الفواتير.\n"
                "Skills\nمحاسب، الحسابات الدائنة، Excel",
            ),
        ],
        timeout_seconds=2,
    )
    assert ranked[0].identity == "strong"


def test_experience_evidence_outweighs_repeated_skill_keywords():
    honest = CandidateText(
        "honest",
        "Experience\nAnalyzed datasets using SQL and Python, built Tableau dashboards, "
        "and validated Excel reports.\nSkills\nSQL, Python, Tableau, Excel",
    )
    stuffing = CandidateText(
        "stuffing",
        "Experience\nSupported routine office operations and maintained records.\nSkills\n"
        + ("SQL Python Tableau Excel " * 100),
    )
    ranked = rank_lexically(
        ["SQL", "Python", "Tableau", "Microsoft Excel"],
        [honest, stuffing],
        timeout_seconds=2,
    )
    assert ranked[0].identity == "honest"
    assert ranked[0].score > ranked[1].score


def test_repeated_terms_have_bm25_saturation_not_linear_inflation():
    one = CandidateText("one", "Experience\nBuilt services using Python and SQL.")
    repeated = CandidateText(
        "repeated", "Experience\nBuilt services using " + "Python " * 80 + "SQL."
    )
    ranked = rank_lexically(["Python", "SQL"], [one, repeated], timeout_seconds=2)
    assert ranked[0].identity == "one"


def test_identity_and_institution_names_do_not_change_ranking_score():
    baseline = CandidateText(
        "baseline",
        "Experience\nAnalyzed datasets with SQL and Python at a software company in 2023.\n"
        "Skills\nSQL, Python",
    )
    named = CandidateText(
        "named",
        "Experience\nAnalyzed datasets with SQL and Python at Google in 2023.\n"
        "Skills\nSQL, Python\nAge: 42; gender: female; religion: sample",
    )
    baseline_score = rank_lexically(["SQL", "Python"], [baseline], timeout_seconds=2)[0].score
    named_score = rank_lexically(["SQL", "Python"], [named], timeout_seconds=2)[0].score
    assert named_score == baseline_score


def test_missing_requirements_or_nonmatching_cv_is_visible_unavailable():
    with pytest.raises(PreRankingUnavailable, match="No eligible CV terms matched"):
        rank_lexically(
            ["SQL"],
            [CandidateText("candidate", "Experience\nManaged retail schedules.")],
            timeout_seconds=2,
        )


def test_lexical_is_the_default_engine_and_a5_remains_off():
    assert Settings.model_fields["a5_prerank_engine"].default == "lexical"
    assert Settings.model_fields["a5_prerank_enabled"].default is False
    assert settings.a5_prerank_enabled is False


def test_e5_selection_without_optional_runtime_has_visible_status(monkeypatch):
    import importlib.util

    import app.services.advisory_preranking_service as service

    monkeypatch.setattr(settings, "a5_prerank_enabled", True)
    monkeypatch.setattr(importlib.util, "find_spec", lambda _name: None)
    service.configured_embedder.cache_clear()
    try:
        with pytest.raises(PreRankingUnavailable, match="Optional E5 add-on is not installed"):
            service.configured_embedder()
    finally:
        service.configured_embedder.cache_clear()
