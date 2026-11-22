"""Evidence verification boundary (HERA Prompt 8).

Treats the original extracted resume text as the single source of truth for
evaluation evidence. Inspects proposed match evidence items, verifies supporting
quotes against the source text, rejects fabricated or ungrounded claims, records
source locations, and demotes unverified positive claims so ungrounded evidence
never contributes to a confident score.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.ai.contracts.job_profile import JobRequirement
from app.services.text_normalization import (
    match_quote_in_source,
    normalize_quote_for_verification,
)

logger = logging.getLogger(__name__)

EVIDENCE_ENGINE_VERSION = "2.1"


class EvidenceVerificationService:
    """Verifies proposed evidence items against source resume text."""

    def __init__(self, engine_version: str = EVIDENCE_ENGINE_VERSION) -> None:
        self.engine_version = engine_version

    def verify_evidence_items(
        self,
        *,
        resume_text: str | None,
        evidence_items: list[dict[str, Any]],
        requirements: list[JobRequirement],
        source_corpus: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Verify each evidence item against the source resume text.

        Returns an enriched, verified list of evidence items conforming to the
        contract schema while preventing unverified quotes or fabricated claims
        from producing a confident match.
        """
        verified_items: list[dict[str, Any]] = []
        corpus = source_corpus or {}
        source = str(corpus.get("content") or resume_text or "")
        profile_fields = corpus.get("derived_profile_fields") or {}
        profile_source = (
            json.dumps(profile_fields, ensure_ascii=False, sort_keys=True)
            if isinstance(profile_fields, dict | list)
            else ""
        )
        req_map = {req.key: req for req in requirements}

        for item in evidence_items:
            verified_item = dict(item)
            req_ref = item.get("requirement_ref") or {}
            req_key = req_ref.get("requirement_key")
            req = req_map.get(req_key)

            candidate_evidence = dict(item.get("candidate_evidence") or {})
            raw_quote = (
                candidate_evidence.get("quote") or candidate_evidence.get("evidence_text") or ""
            )
            evidence_type = item.get("evidence_type", "missing")
            uncertainty = candidate_evidence.get("uncertainty")

            # 1. If evidence_type is 'missing', record explicit non-absence explanation
            if evidence_type == "missing":
                candidate_evidence["quote"] = None
                candidate_evidence["quote_verified"] = False
                candidate_evidence["verification_status"] = "no_evidence_found"
                if not candidate_evidence.get("explanation"):
                    req_name = req.text if req else req_key
                    candidate_evidence["explanation"] = (
                        f"No sufficient evidence found in the resume for '{req_name}'. "
                        "This indicates absence of documented mention, not definitive proof of lack of skill."
                    )
                verified_item["candidate_evidence"] = candidate_evidence
                verified_items.append(verified_item)
                continue

            if not source.strip():
                verified_item["evidence_type"] = "missing"
                verified_item["strength"] = "none"
                candidate_evidence["quote"] = None
                candidate_evidence["quote_verified"] = False
                candidate_evidence["verification_status"] = "source_unavailable"
                candidate_evidence["verification_reason"] = "raw_resume_text_unavailable"
                candidate_evidence["uncertainty"] = (
                    "The extracted resume text is unavailable, so this claim cannot be verified."
                )
                candidate_evidence["explanation"] = (
                    "Evidence could not be verified because the source resume text is unavailable."
                )
                verified_item["candidate_evidence"] = candidate_evidence
                provenance = dict(item.get("provenance") or {})
                provenance["evidence_engine_version"] = self.engine_version
                provenance["verification"] = "EvidenceVerificationService"
                verified_item["provenance"] = provenance
                verified_items.append(verified_item)
                continue

            # 2. Positive evidence ('matched' or 'partial') requires verifiable grounding
            if not raw_quote or not str(raw_quote).strip():
                # Empty quote associated with a positive match: demote to missing
                logger.warning(
                    "Demoting ungrounded %s evidence for %s: reason=quote_not_provided",
                    evidence_type,
                    req_key,
                )
                verified_item["evidence_type"] = "missing"
                verified_item["strength"] = "none"
                candidate_evidence["quote"] = None
                candidate_evidence["quote_verified"] = False
                candidate_evidence["verification_status"] = "unverified_quote"
                candidate_evidence["verification_reason"] = "quote_not_provided"
                candidate_evidence["uncertainty"] = (
                    "No supporting text quote was provided to ground the claim."
                )
                candidate_evidence["explanation"] = (
                    "No verifiable quote provided. Sufficient evidence was not found in the resume."
                )
                verified_item["candidate_evidence"] = candidate_evidence
                verified_items.append(verified_item)
                continue

            # 3. Verify the non-empty quote against the source text
            is_verified, location, diagnostic = match_quote_in_source(
                str(raw_quote).strip(), source
            )

            if is_verified and location:
                # Retain original source quote wording and annotate verification metadata
                candidate_evidence["quote"] = raw_quote
                candidate_evidence["quote_verified"] = True
                candidate_evidence["verification_status"] = "verified"
                candidate_evidence["verification_reason"] = diagnostic["reason"]
                if diagnostic.get("similarity") is not None:
                    candidate_evidence["verification_similarity"] = diagnostic["similarity"]
                candidate_evidence["source_location"] = {
                    "start": location["start"],
                    "end": location["end"],
                    "match_type": location["match_type"],
                }
                if uncertainty:
                    candidate_evidence["uncertainty"] = uncertainty
            else:
                # Derived profile fields help the model locate evidence but are
                # not authoritative source quotes and never independently score.
                normalized_quote = normalize_quote_for_verification(str(raw_quote))
                profile_only = bool(
                    normalized_quote
                    and normalized_quote in normalize_quote_for_verification(profile_source)
                )
                mismatch_reason = "profile_context_only" if profile_only else diagnostic["reason"]
                logger.warning(
                    "Rejecting unverifiable evidence for requirement %s: reason=%s "
                    "best_similarity=%s profile_context_match=%s",
                    req_key,
                    mismatch_reason,
                    diagnostic.get("similarity"),
                    profile_only,
                )
                candidate_evidence["quote"] = raw_quote
                candidate_evidence["quote_verified"] = False
                candidate_evidence["verification_status"] = (
                    "profile_context_only" if profile_only else "fabricated_quote"
                )
                candidate_evidence["verification_reason"] = mismatch_reason
                if diagnostic.get("similarity") is not None:
                    candidate_evidence["verification_similarity"] = diagnostic["similarity"]
                candidate_evidence["source_location"] = None
                if profile_only:
                    candidate_evidence["uncertainty"] = (
                        "The quote appears only in AI-derived profile context and could not be "
                        "verified in the extracted CV text."
                    )
                    candidate_evidence["explanation"] = (
                        "Profile context can guide review but is not source evidence. This item "
                        "was not scored because its quote could not be verified in the CV."
                    )
                else:
                    candidate_evidence["uncertainty"] = (
                        "The proposed supporting quote was not found in the candidate's CV text."
                    )
                    candidate_evidence["explanation"] = (
                        "Evidence rejected: quote could not be verified in the source resume. "
                        "Demoted to prevent ungrounded scoring."
                    )
                # Demote claim: fabricated/unverified quotes cannot produce a matched state
                verified_item["evidence_type"] = "missing"
                verified_item["strength"] = "none"

            # Annotate provenance with evidence engine version
            provenance = dict(item.get("provenance") or {})
            provenance["evidence_engine_version"] = self.engine_version
            provenance["verification"] = "EvidenceVerificationService"
            verified_item["provenance"] = provenance

            verified_item["candidate_evidence"] = candidate_evidence
            verified_items.append(verified_item)

        return verified_items
