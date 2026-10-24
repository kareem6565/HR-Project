"""Deterministic candidate scoring against locked job-profile requirements.

Phase 4.2. This is a pure, stateless service: it never persists and never calls
any provider. It consumes the normalized (canonical v1.1) job requirements and
their match evidence and produces a score plus an explainable breakdown.

Locked decisions:
- One ``MatchEvidence`` row per requirement (A1); evidence keys the requirement
  it concerns via ``requirement_key`` (B1).
- ``strength`` is excluded from scoring (C1); only ``evidence_type`` contributes.
- Weights are Python constants (D1), not config.
- Category weights: ``must_have=3``, ``important=2``, ``nice_to_have=1``.
- Evidence values: ``matched=1.0``, ``partial=0.5``, ``missing=0.0``.
- Score = [sum(weight x evidence_value)] / [sum(weights of ALL requirements in
  the approved profile)] x 100, normalized to 0-100.
- A missing must-have is a review signal only: no penalty, no auto-reject.
- ``dimension`` is not weighted. The AI never produces a score; HR remains the
  final decision maker. ``candidate_evaluations.recommendation`` stays unused.
"""

from __future__ import annotations

from decimal import Decimal

from app.ai.contracts.job_profile import JobRequirement

CATEGORY_WEIGHTS: dict[str, Decimal] = {
    "must_have": Decimal("3"),
    "important": Decimal("2"),
    "nice_to_have": Decimal("1"),
}

EVIDENCE_VALUES: dict[str, Decimal] = {
    "matched": Decimal("1.0"),
    "partial": Decimal("0.5"),
    "missing": Decimal("0.0"),
}

SCORING_VERSION = "1.0"


class ScoringService:
    """Pure computation of a candidate score from requirements and evidence."""

    def __init__(self) -> None:
        self._category_weights = CATEGORY_WEIGHTS
        self._evidence_values = EVIDENCE_VALUES

    def compute(
        self,
        requirements: list[JobRequirement],
        evidence_by_key: dict[str, str],
    ) -> dict:
        """Return the score and a breakdown keyed by requirement key.

        ``evidence_by_key`` maps each requirement key to an evidence_type
        (``matched``/``partial``/``missing``). Keys present in the approved
        requirements but absent from ``evidence_by_key`` are treated as
        ``missing`` (evidence value 0.0). Unknown evidence keys are ignored.

        Returns:
        - ``score``: Decimal in ``0..100``.
        - ``scoring_version``: the locked `SCORING_VERSION`.
        - ``breakdown``: per-requirement detail (weight, evidence_value,
          evidence_type, contribution, label).
        - ``review_signals``: non-penalizing observations for HR review
          (``missing_must_have`` for any must-have requirement scored as
          ``missing``; ``no_requirements`` when the approved profile has no
          requirements and the score is ``0``).
        """
        if not requirements:
            return {
                "score": Decimal("0"),
                "scoring_version": SCORING_VERSION,
                "breakdown": {},
                "review_signals": ["no_requirements"],
            }

        breakdown: dict[str, dict] = {}
        weight_sum = Decimal("0")
        weighted_sum = Decimal("0")
        missing_must_have: list[str] = []

        for requirement in requirements:
            weight = self._category_weights[requirement.category]
            evidence_type = evidence_by_key.get(requirement.key, "missing")
            if evidence_type not in self._evidence_values:
                evidence_type = "missing"
            evidence_value = self._evidence_values[evidence_type]
            weight_sum += weight
            weighted_sum += weight * evidence_value
            breakdown[requirement.key] = {
                "requirement_key": requirement.key,
                "text": requirement.text,
                "category": requirement.category,
                "dimension": requirement.dimension,
                "weight": str(weight),
                "evidence_type": evidence_type,
                "evidence_value": str(evidence_value),
                "contribution": str(weight * evidence_value),
                "label": f"{requirement.category}:{requirement.text}",
            }
            if requirement.category == "must_have" and evidence_type == "missing":
                missing_must_have.append(requirement.key)

        score = Decimal("0")
        if weight_sum > 0:
            score = (weighted_sum / weight_sum) * Decimal("100")
            score = score.quantize(Decimal("1.000"))

        review_signals: list[str] = []
        if missing_must_have:
            review_signals.append("missing_must_have")

        return {
            "score": score,
            "scoring_version": SCORING_VERSION,
            "breakdown": breakdown,
            "review_signals": review_signals,
        }


def build_evidence_by_key(
    evidence_items: list,
) -> dict[str, str]:
    """Map each persisted ``MatchEvidence`` row to its evidence_type by key.

    Only rows whose ``requirement_ref`` carries a valid ``requirement_key`` are
    included; other rows contribute nothing to the score.
    """
    from app.ai.contracts.match_evidence import is_requirement_key

    result: dict[str, str] = {}
    for item in evidence_items:
        ref = getattr(item, "requirement_ref", None)
        if not isinstance(ref, dict):
            continue
        key = ref.get("requirement_key")
        if is_requirement_key(key):
            result[key] = getattr(item, "evidence_type", "missing")
    return result
