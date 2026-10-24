from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Candidate,
    CandidateProfile,
    CandidateEvaluation,
    HRDecision,
    Job,
    JobApplication,
    MatchEvidence,
    Resume,
)
from app.services.candidate_pool_service import (
    VALID_APPLICATION_STATUSES,
    assign_group,
)
from app.services.errors import ValidationError
from app.services.evaluation_service import EvaluationService
from app.services.job_application_service import JobApplicationService

TALENT_POOL_STATUSES = frozenset({"hold", "advanced"})


@dataclass(frozen=True)
class EvidenceSummaryItem:
    """One compact evidence line for an application summary row.

    ``evidence_type`` is the persisted match classification (matched /
    partial / missing); ``requirement_key`` identifies the job requirement;
    ``text`` is the resolved, human-readable requirement label (from the
    persisted ``requirement_ref`` text/skill, falling back to the current
    evaluation's ``score_breakdown`` requirement label, then the key).
    """

    evidence_type: str
    requirement_key: str | None = None
    text: str = ""


@dataclass(frozen=True)
class ApplicationSummaryRow:
    """One org-wide application row (application + candidate + job + score)."""

    application: JobApplication
    candidate: Candidate
    job: Job
    current_evaluation: CandidateEvaluation | None
    group: str
    evidence: list[EvidenceSummaryItem]


@dataclass(frozen=True)
class TalentPoolRow:
    """One hold/advanced candidate with application context."""

    application: JobApplication
    candidate: Candidate
    job: Job
    current_evaluation: CandidateEvaluation | None
    latest_decision: HRDecision | None
    group: str
    skills: list[str]


def _requirement_topic(requirement_ref: dict[str, Any] | None) -> str:
    """Extract a natural-language requirement label from a requirement_ref.

    Prefers the human-readable fields the AI stores (``skill``/``text``/
    ``requirement``) and returns ``""`` when none are present — callers then
    fall back to the evaluation's ``score_breakdown`` label and finally the
    system ``requirement_key``. Mirrors the extraction used by the interview
    question flow.
    """
    if not isinstance(requirement_ref, dict):
        return ""
    for key in ("skill", "text", "requirement"):
        value = requirement_ref.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


@dataclass(frozen=True)
class ReviewBundle:
    """Everything the review screen needs for one application."""

    application: JobApplication
    candidate: Candidate
    job: Job
    evaluations: list[CandidateEvaluation]
    current_evaluation: CandidateEvaluation | None
    evidence: list[MatchEvidence]
    latest_decision: HRDecision | None
    group: str


class ReviewService:
    """Read-only aggregation service backing the review and pipeline screens.

    Composes existing persisted data (applications, candidates, jobs, current
    evaluations, evidence, HR decisions) into the read models the API contract
    exposes. Never recomputes scores and never touches the AI or scoring
    services.
    """

    @staticmethod
    def _as_decimal(score: object) -> Decimal | None:
        """Normalize an evaluation score to Decimal (DB rows may expose str)."""
        if score is None:
            return None
        if isinstance(score, Decimal):
            return score
        return Decimal(str(score))

    @staticmethod
    def _latest_decision_id_subquery():
        return (
            select(HRDecision.id)
            .where(HRDecision.job_application_id == JobApplication.id)
            .order_by(HRDecision.created_at.desc())
            .limit(1)
            .correlate(JobApplication)
            .scalar_subquery()
        )

    def list_application_summaries(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        status: str | None = None,
        candidate_id: uuid.UUID | None = None,
    ) -> list[ApplicationSummaryRow]:
        """Return org-wide application summaries, newest first.

        Organization scope is enforced directly; only each application's
        current evaluation is considered (``is_current=True``), avoiding any
        load of version history. Requirement evidence for every current
        evaluation is loaded in a single batched query (one ``IN`` clause on
        the current evaluation ids), and each row carries the deterministic
        grouping band — so list views get real evidence and groups without
        any per-row request (no N+1). Scores and groups are never recomputed.
        An optional ``candidate_id`` narrows the list to one candidate's
        applications (used by application-aware entry points).
        """
        if status is not None and status not in VALID_APPLICATION_STATUSES:
            raise ValidationError(f"Invalid application status filter: {status!r}.")

        query = (
            select(JobApplication, Candidate, Job, CandidateEvaluation)
            .join(Candidate, Candidate.id == JobApplication.candidate_id)
            .join(Job, Job.id == JobApplication.job_id)
            .outerjoin(
                CandidateEvaluation,
                (CandidateEvaluation.job_application_id == JobApplication.id)
                & CandidateEvaluation.is_current.is_(True),
            )
            .where(JobApplication.organization_id == organization_id)
            .order_by(JobApplication.created_at.desc())
        )
        if status is not None:
            query = query.where(JobApplication.status == status)
        if candidate_id is not None:
            query = query.where(JobApplication.candidate_id == candidate_id)

        rows = db.execute(query).all()
        evaluations = [evaluation for _a, _c, _j, evaluation in rows if evaluation is not None]

        evidence_by_evaluation: dict[uuid.UUID, list[tuple[str, dict[str, Any] | None]]] = {}
        if evaluations:
            evidence_rows = db.execute(
                select(
                    MatchEvidence.candidate_evaluation_id,
                    MatchEvidence.evidence_type,
                    MatchEvidence.requirement_ref,
                )
                .where(MatchEvidence.candidate_evaluation_id.in_([e.id for e in evaluations]))
                .order_by(MatchEvidence.created_at, MatchEvidence.id)
            ).all()
            for evaluation_id, evidence_type, requirement_ref in evidence_rows:
                evidence_by_evaluation.setdefault(evaluation_id, []).append(
                    (evidence_type, requirement_ref)
                )

        # Resolve each requirement label once per evaluation from the persisted
        # score_breakdown (key -> {text, ...}), mirroring the review screen's
        # fallback: requirement_ref text/skill first, then the breakdown's
        # requirement text, then the system key. The breakdown is already on
        # the loaded evaluation objects, so no extra query is needed.
        breakdown_labels_by_evaluation: dict[uuid.UUID, dict[str, str]] = {}
        for evaluation in evaluations:
            breakdown = evaluation.score_breakdown or {}
            labels = {
                str(key): str(entry.get("text") or "")
                for key, entry in breakdown.items()
                if isinstance(entry, dict) and entry.get("text")
            }
            if labels:
                breakdown_labels_by_evaluation[evaluation.id] = labels

        summaries = []
        for application, candidate, job, evaluation in rows:
            raw_evidence = (
                evidence_by_evaluation.get(evaluation.id, []) if evaluation is not None else []
            )
            labels = (
                breakdown_labels_by_evaluation.get(evaluation.id, {})
                if evaluation is not None
                else {}
            )
            evidence = []
            for evidence_type, requirement_ref in raw_evidence:
                requirement_key = (
                    (requirement_ref or {}).get("requirement_key")
                    if isinstance(requirement_ref, dict)
                    else None
                )
                evidence.append(
                    EvidenceSummaryItem(
                        evidence_type=evidence_type,
                        requirement_key=requirement_key,
                        text=(
                            _requirement_topic(requirement_ref)
                            or (labels.get(requirement_key) if requirement_key else "")
                            or requirement_key
                            or ""
                        ),
                    )
                )
            summaries.append(
                ApplicationSummaryRow(
                    application=application,
                    candidate=candidate,
                    job=job,
                    current_evaluation=evaluation,
                    group=assign_group(
                        self._as_decimal(evaluation.score if evaluation is not None else None)
                    ),
                    evidence=evidence,
                )
            )
        return summaries

    def list_talent_pool(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
    ) -> list[TalentPoolRow]:
        """Return org-wide hold/advanced candidates ranked by current score.

        Rows carry application context, the persisted current evaluation score,
        the deterministic grouping band, and the latest HR decision. Decisions
        are left-joined so candidates without a decision are never hidden.
        """
        latest_decision_id = self._latest_decision_id_subquery()

        query = (
            select(JobApplication, Candidate, Job, CandidateEvaluation, HRDecision)
            .join(Candidate, Candidate.id == JobApplication.candidate_id)
            .join(Job, Job.id == JobApplication.job_id)
            .outerjoin(
                CandidateEvaluation,
                (CandidateEvaluation.job_application_id == JobApplication.id)
                & CandidateEvaluation.is_current.is_(True),
            )
            .outerjoin(HRDecision, HRDecision.id == latest_decision_id)
            .where(JobApplication.organization_id == organization_id)
            .where(JobApplication.status.in_(TALENT_POOL_STATUSES))
        )

        rows = db.execute(query).all()

        skills_by_application: dict[uuid.UUID, list[str]] = {}
        if rows:
            application_ids = [application.id for application, *_rest in rows]
            profile_rows = db.execute(
                select(JobApplication.id, CandidateProfile.profile_data)
                .join(Resume, Resume.id == JobApplication.resume_id)
                .join(CandidateProfile, CandidateProfile.resume_id == Resume.id)
                .where(
                    JobApplication.id.in_(application_ids),
                    CandidateProfile.is_current.is_(True),
                )
            ).all()
            for application_id, profile_data in profile_rows:
                raw_skills = profile_data.get("skills", []) if isinstance(profile_data, dict) else []
                if isinstance(raw_skills, list):
                    skills_by_application[application_id] = [
                        skill.strip()
                        for skill in raw_skills
                        if isinstance(skill, str) and skill.strip()
                    ][:12]

        entries = [
            TalentPoolRow(
                application=application,
                candidate=candidate,
                job=job,
                current_evaluation=evaluation,
                latest_decision=decision,
                group=assign_group(self._as_decimal(evaluation.score if evaluation else None)),
                skills=skills_by_application.get(application.id, []),
            )
            for application, candidate, job, evaluation, decision in rows
        ]

        entries.sort(
            key=lambda entry: (
                entry.current_evaluation is None
                or self._as_decimal(entry.current_evaluation.score) is None,
                -(self._as_decimal(entry.current_evaluation.score) or Decimal(0))
                if entry.current_evaluation
                else 0,
            )
        )
        return entries

    def get_review_bundle(
        self,
        db: Session,
        *,
        application_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> ReviewBundle:
        """Return the complete read-only review bundle for one application."""
        application = JobApplicationService().get(
            db, application_id=application_id, organization_id=organization_id
        )
        candidate = db.get(Candidate, application.candidate_id)
        job = db.get(Job, application.job_id)

        evaluations = EvaluationService().list_versions(
            db,
            job_application_id=application.id,
            organization_id=organization_id,
        )
        current = next((v for v in evaluations if v.is_current), None)

        evidence: list[MatchEvidence] = []
        if current is not None:
            evidence = list(
                db.scalars(
                    select(MatchEvidence)
                    .where(MatchEvidence.candidate_evaluation_id == current.id)
                    .order_by(MatchEvidence.created_at)
                )
            )

        latest_decision = db.scalar(
            select(HRDecision)
            .where(HRDecision.job_application_id == application.id)
            .order_by(HRDecision.created_at.desc())
            .limit(1)
        )

        score = self._as_decimal(current.score if current is not None else None)
        return ReviewBundle(
            application=application,
            candidate=candidate,
            job=job,
            evaluations=evaluations,
            current_evaluation=current,
            evidence=evidence,
            latest_decision=latest_decision,
            group=assign_group(score),
        )
