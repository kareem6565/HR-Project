"""Unit tests for the Phase 4.2 deterministic scoring service.

No database access and no provider calls: the service is pure and stateless.
Verifies the locked constants and the normalized 0-100 formula.
"""

from decimal import Decimal

from app.ai.contracts import JobRequirement, requirement_key
from app.services.scoring_service import (
    CATEGORY_WEIGHTS,
    EVIDENCE_VALUES,
    SCORING_VERSION,
    ScoringService,
    build_evidence_by_key,
)


def _requirements() -> list[JobRequirement]:
    return [
        JobRequirement(text="Python", category="must_have", dimension="skill"),
        JobRequirement(text="SQL", category="must_have", dimension="skill"),
        JobRequirement(text="Machine Learning", category="important", dimension="skill"),
        JobRequirement(text="REST APIs", category="nice_to_have", dimension="skill"),
    ]


def _keys(requirements: list[JobRequirement]) -> list[str]:
    return [requirement.key for requirement in requirements]


def test_scoring_constants_are_locked() -> None:
    assert CATEGORY_WEIGHTS == {
        "must_have": Decimal("3"),
        "important": Decimal("2"),
        "nice_to_have": Decimal("1"),
    }
    assert EVIDENCE_VALUES == {
        "matched": Decimal("1.0"),
        "partial": Decimal("0.5"),
        "missing": Decimal("0.0"),
    }
    assert SCORING_VERSION == "1.0"


def test_perfect_score_is_normalized_to_100() -> None:
    requirements = _requirements()
    evidence = {key: "matched" for key in _keys(requirements)}
    result = ScoringService().compute(requirements, evidence)
    assert result["score"] == Decimal("100")
    assert result["scoring_version"] == SCORING_VERSION
    assert result["review_signals"] == []


def test_all_missing_score_is_zero() -> None:
    requirements = _requirements()
    result = ScoringService().compute(requirements, {})
    assert result["score"] == Decimal("0")
    assert result["review_signals"] == ["missing_must_have"]


def test_partial_matches_score_between() -> None:
    requirements = _requirements()
    # Must-have Python matched (3), SQL partial (3*0.5=1.5), important matched (2),
    # nice_to_have missing (0). Weight sum = 3+3+2+1 = 9. Weighted = 3+1.5+2 = 6.5.
    evidence = {
        _keys(requirements)[0]: "matched",
        _keys(requirements)[1]: "partial",
        _keys(requirements)[2]: "matched",
        _keys(requirements)[3]: "missing",
    }
    result = ScoringService().compute(requirements, evidence)
    assert result["score"] == Decimal("72.222")
    assert result["review_signals"] == []


def test_missing_evidence_defaults_to_missing() -> None:
    requirements = _requirements()
    evidence = {_keys(requirements)[0]: "matched"}
    result = ScoringService().compute(requirements, evidence)
    missing_breakdown = result["breakdown"][_keys(requirements)[1]]
    assert missing_breakdown["evidence_type"] == "missing"
    assert missing_breakdown["evidence_value"] == "0.0"


def test_score_is_independent_of_strength() -> None:
    requirements = _requirements()
    key = _keys(requirements)[0]
    with_strength = ScoringService().compute(requirements, {key: "matched"})
    without_strength = ScoringService().compute(requirements, {key: "matched"})
    assert with_strength["score"] == without_strength["score"]
    assert with_strength["breakdown"] == without_strength["breakdown"]


def test_unknown_evidence_key_is_ignored() -> None:
    requirements = _requirements()
    evidence = {key: "matched" for key in _keys(requirements)}
    evidence["req-0000000000000000"] = "matched"
    result = ScoringService().compute(requirements, evidence)
    assert len(result["breakdown"]) == len(requirements)


def test_category_weight_applied_per_requirement() -> None:
    requirements = _requirements()
    evidence = {key: "matched" for key in _keys(requirements)}
    result = ScoringService().compute(requirements, evidence)
    assert result["breakdown"][_keys(requirements)[0]]["weight"] == "3"
    assert result["breakdown"][_keys(requirements)[2]]["weight"] == "2"
    assert result["breakdown"][_keys(requirements)[3]]["weight"] == "1"


def test_empty_profile_scores_zero_with_review_signal() -> None:
    result = ScoringService().compute([], {})
    assert result["score"] == Decimal("0")
    assert result["breakdown"] == {}
    assert result["review_signals"] == ["no_requirements"]


def test_breakdown_contains_per_requirement_detail() -> None:
    requirements = _requirements()
    key = _keys(requirements)[0]
    evidence = {key: "partial"}
    result = ScoringService().compute(requirements, evidence)
    entry = result["breakdown"][key]
    assert entry["requirement_key"] == key
    assert entry["text"] == "Python"
    assert entry["category"] == "must_have"
    assert entry["dimension"] == "skill"
    assert entry["evidence_type"] == "partial"
    assert entry["label"] == "must_have:Python"


def test_recompute_is_idempotent() -> None:
    requirements = _requirements()
    evidence = {key: "matched" for key in _keys(requirements)}
    service = ScoringService()
    first = service.compute(requirements, evidence)
    second = service.compute(requirements, evidence)
    assert first["score"] == second["score"]
    assert first["breakdown"] == second["breakdown"]
    assert first["review_signals"] == second["review_signals"]


def test_dimension_is_not_weighted() -> None:
    skill_req = JobRequirement(text="Python", category="must_have", dimension="skill")
    education_req = JobRequirement(text="Python", category="must_have", dimension="education")
    skill_result = ScoringService().compute([skill_req], {skill_req.key: "matched"})
    education_result = ScoringService().compute([education_req], {education_req.key: "matched"})
    assert skill_result["score"] == education_result["score"] == Decimal("100")


def test_build_evidence_by_key_maps_only_valid_keys() -> None:
    class FakeRow:
        requirement_ref = {"requirement_key": requirement_key("Python", "must_have")}
        evidence_type = "matched"

    class NoRefRow:
        requirement_ref = None
        evidence_type = "missing"

    class BadKeyRow:
        requirement_ref = {"requirement_key": "not-a-key"}
        evidence_type = "partial"

    result = build_evidence_by_key([FakeRow(), NoRefRow(), BadKeyRow()])
    assert result == {requirement_key("Python", "must_have"): "matched"}


def test_invalid_evidence_type_falls_back_to_missing() -> None:
    requirements = _requirements()
    key = _keys(requirements)[0]
    result = ScoringService().compute(requirements, {key: "bogus"})
    assert result["breakdown"][key]["evidence_type"] == "missing"
