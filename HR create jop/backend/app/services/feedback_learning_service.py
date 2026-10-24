from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import HRFeedbackCorrection, Organization, User
from app.services.audit_service import AuditService
from app.services.errors import NotFoundError, ValidationError
from app.services.text_normalization import TECHNICAL_SYNONYMS, normalize_for_matching

VALID_CORRECTION_TYPES = frozenset(
    {
        "extraction_correction",
        "skill_alias_correction",
        "requirement_match_correction",
        "scoring_rule_correction",
        "recommendation_override",
        "final_decision",
        "interview_feedback_correction",
        "post_interview_decision",
    }
)


class FeedbackLearningService:
    """Structured HR correction persistence and controlled feedback learning loop (Stage K)."""

    def record_correction(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        correction_type: str,
        job_id: uuid.UUID | None = None,
        job_profile_id: uuid.UUID | None = None,
        candidate_profile_id: uuid.UUID | None = None,
        candidate_evaluation_id: uuid.UUID | None = None,
        job_application_id: uuid.UUID | None = None,
        original_ai_output: dict[str, Any] | None = None,
        hr_corrected_result: dict[str, Any] | None = None,
        reason: str | None = None,
        evidence_reference: dict[str, Any] | None = None,
        provider_info: dict[str, Any] | None = None,
    ) -> HRFeedbackCorrection:
        """Persist structured HR feedback on AI outputs."""
        if correction_type not in VALID_CORRECTION_TYPES:
            raise ValidationError(f"Invalid correction_type: {correction_type!r}.")

        org = db.get(Organization, organization_id)
        if org is None:
            raise NotFoundError("Organization was not found.")

        user = db.get(User, user_id)
        if user is None or user.organization_id != organization_id:
            raise NotFoundError("User was not found in organization.")

        correction = HRFeedbackCorrection(
            organization_id=organization_id,
            user_id=user_id,
            correction_type=correction_type,
            job_id=job_id,
            job_profile_id=job_profile_id,
            candidate_profile_id=candidate_profile_id,
            candidate_evaluation_id=candidate_evaluation_id,
            job_application_id=job_application_id,
            original_ai_output=original_ai_output,
            hr_corrected_result=hr_corrected_result,
            reason=reason,
            evidence_reference=evidence_reference,
            provider_info=provider_info,
        )
        db.add(correction)
        db.flush()

        AuditService().log_event(
            db,
            action="hr_feedback.recorded",
            entity_type="hr_feedback_correction",
            organization_id=organization_id,
            actor_user_id=user_id,
            entity_id=correction.id,
            metadata={
                "correction_type": correction_type,
                "candidate_evaluation_id": str(candidate_evaluation_id) if candidate_evaluation_id else None,
            },
            flush=False,
        )
        return correction

    def list_corrections(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        correction_type: str | None = None,
        limit: int = 50,
    ) -> list[HRFeedbackCorrection]:
        """List feedback corrections for review."""
        stmt = (
            select(HRFeedbackCorrection)
            .where(HRFeedbackCorrection.organization_id == organization_id)
            .order_by(HRFeedbackCorrection.created_at.desc())
            .limit(limit)
        )
        if correction_type is not None:
            if correction_type not in VALID_CORRECTION_TYPES:
                raise ValidationError(f"Invalid correction_type filter: {correction_type!r}.")
            stmt = stmt.where(HRFeedbackCorrection.correction_type == correction_type)

        return list(db.scalars(stmt))

    def get_analytics(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Compute actionable feedback analytics: override rates, error distributions."""
        all_corrections = self.list_corrections(db, organization_id=organization_id, limit=500)
        total = len(all_corrections)

        by_type: dict[str, int] = {}
        for c in all_corrections:
            by_type[c.correction_type] = by_type.get(c.correction_type, 0) + 1

        recommendation_overrides = by_type.get("recommendation_override", 0)
        extraction_corrections = by_type.get("extraction_correction", 0)
        match_corrections = by_type.get("requirement_match_correction", 0)

        override_rate = round(recommendation_overrides / total * 100, 2) if total > 0 else 0.0

        return {
            "total_corrections": total,
            "corrections_by_type": by_type,
            "recommendation_override_rate_pct": override_rate,
            "extraction_error_count": extraction_corrections,
            "requirement_match_correction_count": match_corrections,
        }

    def propose_skill_alias(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        alias: str,
        canonical_skill: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """From an approved correction, register an improved technical skill synonym.

        Safely integrates into the normalized dictionary in a controlled, traceable way.
        """
        norm_alias = normalize_for_matching(alias)
        norm_canonical = normalize_for_matching(canonical_skill)

        if not norm_alias or not norm_canonical:
            raise ValidationError("Both alias and canonical_skill must be non-empty strings.")

        # Record the correction row
        self.record_correction(
            db,
            organization_id=organization_id,
            user_id=user_id,
            correction_type="skill_alias_correction",
            original_ai_output={"unrecognized_term": alias},
            hr_corrected_result={"canonical_skill": canonical_skill},
            reason=reason or f"Mapped alias '{alias}' to canonical skill '{canonical_skill}'",
        )

        # Update in-memory TECHNICAL_SYNONYMS dynamically
        synonyms = TECHNICAL_SYNONYMS.setdefault(norm_canonical, [norm_canonical])
        if norm_alias not in synonyms:
            synonyms.append(norm_alias)

        return {
            "canonical_skill": norm_canonical,
            "synonyms": synonyms,
            "status": "activated",
        }

    def evaluate_rules_on_dataset(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        test_cases: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Run controlled benchmark comparison between original matching and proposed rules."""
        if not test_cases:
            raise ValidationError("test_cases list must not be empty.")

        matches = 0
        total = len(test_cases)
        results = []

        from app.services.text_normalization import has_term_match

        for case in test_cases:
            text = case.get("text", "")
            term = case.get("term", "")
            expected = case.get("expected", True)

            actual = has_term_match(normalize_for_matching(text), term)
            is_correct = actual == expected
            if is_correct:
                matches += 1

            results.append(
                {
                    "term": term,
                    "expected": expected,
                    "actual": actual,
                    "correct": is_correct,
                }
            )

        accuracy = round(matches / total * 100, 2)
        return {
            "total_evaluated": total,
            "matches": matches,
            "accuracy_pct": accuracy,
            "detailed_results": results,
            "ready_for_release": accuracy >= 80.0,
        }
