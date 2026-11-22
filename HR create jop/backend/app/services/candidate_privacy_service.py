from __future__ import annotations

import calendar
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    AuditLog,
    Candidate,
    CandidateEvaluation,
    CandidateProfile,
    GitHubEvidenceAnalysis,
    HRDecision,
    HRFeedbackCorrection,
    Interview,
    InterviewQuestionSet,
    JobApplication,
    MatchEvidence,
    Organization,
    Resume,
    ScreeningBatch,
    ScreeningBatchItem,
    TalentPoolConsent,
    WorkflowRun,
)
from app.models.candidate_invitation import CandidateInvitation
from app.services.audit_service import AuditService
from app.services.errors import InvalidStateError, NotFoundError
from app.services.storage_service import LocalFileSystemStorage, StorageProvider


@dataclass(frozen=True)
class RetentionCandidate:
    candidate_id: uuid.UUID
    organization_id: uuid.UUID
    eligible_at: datetime


class CandidatePrivacyService:
    """Organization-scoped, idempotent candidate erasure and retention selection."""

    def erase_candidate(
        self,
        db: Session,
        *,
        candidate_id: uuid.UUID,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None = None,
        storage: StorageProvider | None = None,
        dry_run: bool = False,
        audit: bool = True,
    ) -> dict[str, int | bool]:
        candidate = db.scalar(
            select(Candidate)
            .where(Candidate.id == candidate_id, Candidate.organization_id == organization_id)
            .with_for_update()
        )
        if candidate is None:
            raise NotFoundError("Candidate was not found.")
        if candidate.legal_hold:
            raise InvalidStateError("Candidate is under legal hold.")
        if candidate.anonymized_at is not None:
            return {"already_anonymized": True, "candidates": 0}

        applications = list(
            db.scalars(
                select(JobApplication).where(
                    JobApplication.candidate_id == candidate_id,
                    JobApplication.organization_id == organization_id,
                )
            )
        )
        application_ids = [application.id for application in applications]
        resumes = list(db.scalars(select(Resume).where(Resume.candidate_id == candidate_id)))
        resume_ids = [resume.id for resume in resumes]
        evaluation_ids = list(
            db.scalars(
                select(CandidateEvaluation.id).where(
                    CandidateEvaluation.job_application_id.in_(application_ids)
                    if application_ids
                    else False
                )
            )
        )
        profile_ids = list(
            db.scalars(
                select(CandidateProfile.id).where(
                    CandidateProfile.resume_id.in_(resume_ids) if resume_ids else False
                )
            )
        )
        count_specs = {
            "resumes": len(resumes),
            "applications": len(applications),
            "candidates": 1,
            "evaluations": len(evaluation_ids),
            "profiles": len(profile_ids),
            "evidence": _count_ids(
                db, MatchEvidence, MatchEvidence.candidate_evaluation_id, evaluation_ids
            ),
            "github_evidence": _count_ids(
                db, GitHubEvidenceAnalysis, GitHubEvidenceAnalysis.application_id, application_ids
            ),
            "interview_question_sets": _count_ids(
                db,
                InterviewQuestionSet,
                InterviewQuestionSet.job_application_id,
                application_ids,
            ),
            "feedback_corrections": _count_ids(
                db,
                HRFeedbackCorrection,
                HRFeedbackCorrection.id,
                list(
                    db.scalars(
                        select(HRFeedbackCorrection.id).where(
                            HRFeedbackCorrection.organization_id == organization_id,
                            (
                                HRFeedbackCorrection.job_application_id.in_(application_ids)
                                if application_ids
                                else False
                            )
                            | (
                                HRFeedbackCorrection.candidate_profile_id.in_(profile_ids)
                                if profile_ids
                                else False
                            )
                            | (
                                HRFeedbackCorrection.candidate_evaluation_id.in_(evaluation_ids)
                                if evaluation_ids
                                else False
                            ),
                        )
                    )
                ),
            ),
            "batch_items": db.scalar(
                select(func.count())
                .select_from(ScreeningBatchItem)
                .join(ScreeningBatch, ScreeningBatchItem.batch_id == ScreeningBatch.id)
                .where(
                    ScreeningBatch.organization_id == organization_id,
                    ScreeningBatchItem.candidate_id == candidate_id,
                )
            )
            or 0,
            "workflow_runs": _count_workflow_runs(
                db,
                organization_id,
                candidate_id,
                resume_ids,
                application_ids,
                profile_ids,
                evaluation_ids,
            ),
            "interview_records_kept": 0,
            "hr_decisions_kept": 0,
            "audit_records_kept": 0,
            "files": len(resumes)
            + (
                db.scalar(
                    select(func.count())
                    .select_from(ScreeningBatchItem)
                    .join(ScreeningBatch, ScreeningBatchItem.batch_id == ScreeningBatch.id)
                    .where(
                        ScreeningBatch.organization_id == organization_id,
                        ScreeningBatchItem.candidate_id == candidate_id,
                    )
                )
                or 0
            ),
        }
        batch_items = list(
            db.scalars(
                select(ScreeningBatchItem)
                .join(ScreeningBatch, ScreeningBatchItem.batch_id == ScreeningBatch.id)
                .where(
                    ScreeningBatch.organization_id == organization_id,
                    ScreeningBatchItem.candidate_id == candidate_id,
                )
            )
        )
        if application_ids:
            count_specs["interview_records_kept"] = (
                db.scalar(
                    select(func.count())
                    .select_from(Interview)
                    .where(Interview.job_application_id.in_(application_ids))
                )
                or 0
            )
            count_specs["hr_decisions_kept"] = (
                db.scalar(
                    select(func.count())
                    .select_from(HRDecision)
                    .where(HRDecision.job_application_id.in_(application_ids))
                )
                or 0
            )
        count_specs["audit_records_kept"] = (
            db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.organization_id == organization_id,
                    AuditLog.entity_type == "candidate",
                    AuditLog.entity_id == candidate_id,
                )
            )
            or 0
        )
        if dry_run:
            return {"already_anonymized": False, **count_specs}

        if storage is None:
            storage = LocalFileSystemStorage(settings.storage_root_dir)
        for resume in resumes:
            if not resume.file_uri.startswith("deleted://"):
                storage.delete(file_uri=resume.file_uri)
        for item in batch_items:
            if item.storage_key and not item.storage_key.startswith("deleted://"):
                storage.delete(file_uri=item.storage_key)

        # Preserve HR decisions and their application links while removing evaluation links.
        if evaluation_ids:
            db.execute(
                update(HRDecision)
                .where(HRDecision.candidate_evaluation_id.in_(evaluation_ids))
                .values(candidate_evaluation_id=None)
            )
            db.execute(
                delete(MatchEvidence).where(
                    MatchEvidence.candidate_evaluation_id.in_(evaluation_ids)
                )
            )
            db.execute(
                delete(CandidateEvaluation).where(CandidateEvaluation.id.in_(evaluation_ids))
            )
        if profile_ids:
            db.execute(delete(CandidateProfile).where(CandidateProfile.id.in_(profile_ids)))
        if application_ids:
            db.execute(
                delete(GitHubEvidenceAnalysis).where(
                    GitHubEvidenceAnalysis.organization_id == organization_id,
                    GitHubEvidenceAnalysis.application_id.in_(application_ids),
                )
            )
            db.execute(
                delete(InterviewQuestionSet).where(
                    InterviewQuestionSet.organization_id == organization_id,
                    InterviewQuestionSet.job_application_id.in_(application_ids),
                )
            )
            db.execute(
                update(CandidateInvitation)
                .where(
                    CandidateInvitation.organization_id == organization_id,
                    CandidateInvitation.job_application_id.in_(application_ids),
                )
                .values(status="cancelled", notes=None)
            )
            db.execute(
                update(JobApplication)
                .where(
                    JobApplication.organization_id == organization_id,
                    JobApplication.id.in_(application_ids),
                )
                .values(
                    linkedin_url=None,
                    github_url=None,
                    portfolio_url=None,
                    public_contact_email=None,
                    privacy_notice_text=None,
                    source=None,
                    source_medium=None,
                    source_campaign=None,
                    idempotency_key_hash=None,
                )
            )
        feedback_filter = []
        if application_ids:
            feedback_filter.append(HRFeedbackCorrection.job_application_id.in_(application_ids))
        if profile_ids:
            feedback_filter.append(HRFeedbackCorrection.candidate_profile_id.in_(profile_ids))
        if evaluation_ids:
            feedback_filter.append(HRFeedbackCorrection.candidate_evaluation_id.in_(evaluation_ids))
        if feedback_filter:
            from sqlalchemy import or_

            db.execute(
                delete(HRFeedbackCorrection).where(
                    HRFeedbackCorrection.organization_id == organization_id,
                    or_(*feedback_filter),
                )
            )
        db.execute(
            update(ScreeningBatchItem)
            .where(ScreeningBatchItem.id.in_([item.id for item in batch_items]))
            .values(
                candidate_id=None,
                resume_id=None,
                application_id=None,
                evaluation_id=None,
                filename="deleted",
                storage_key="deleted://",
                sha256="0" * 64,
                error_message=None,
            )
        )
        _delete_workflow_runs(
            db,
            organization_id,
            candidate_id,
            resume_ids,
            application_ids,
            profile_ids,
            evaluation_ids,
        )
        for resume in resumes:
            resume.file_uri = f"deleted://{resume.id}"
            resume.original_filename = None
            resume.content_type = None
            resume.file_size_bytes = None
            resume.checksum = None
            resume.extracted_text = None
            resume.status = "archived"
            resume.archived_at = datetime.now(UTC)
        candidate.full_name = f"Deleted candidate {candidate.id}"
        candidate.email = None
        candidate.phone = None
        candidate.status = "archived"
        candidate.archived_at = datetime.now(UTC)
        candidate.anonymized_at = candidate.archived_at
        if audit:
            AuditService().log_event(
                db,
                action="candidate.data_erased",
                entity_type="candidate",
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                entity_id=candidate_id,
                metadata={"counts": count_specs},
            )
        return {"already_anonymized": False, **count_specs}

    def eligible_candidates(
        self, db: Session, *, now: datetime | None = None
    ) -> list[RetentionCandidate]:
        now = now or datetime.now(UTC)
        organizations = list(db.scalars(select(Organization)))
        eligible: list[RetentionCandidate] = []
        for organization in organizations:
            candidates = list(
                db.scalars(
                    select(Candidate).where(
                        Candidate.organization_id == organization.id,
                        Candidate.anonymized_at.is_(None),
                        Candidate.legal_hold.is_(False),
                    )
                )
            )
            for candidate in candidates:
                apps = list(
                    db.scalars(
                        select(JobApplication).where(
                            JobApplication.organization_id == organization.id,
                            JobApplication.candidate_id == candidate.id,
                        )
                    )
                )
                if not apps:
                    continue
                app_ids = [application.id for application in apps]
                decisions = list(
                    db.execute(
                        select(
                            HRDecision.job_application_id,
                            HRDecision.decision,
                            HRDecision.created_at,
                        )
                        .where(HRDecision.job_application_id.in_(app_ids))
                        .order_by(HRDecision.created_at.desc())
                    )
                )
                latest: dict[uuid.UUID, tuple[str, datetime]] = {}
                for application_id, decision, created_at in decisions:
                    latest.setdefault(application_id, (decision, created_at))
                if len(latest) != len(app_ids) or any(
                    value[0] != "reject" for value in latest.values()
                ):
                    continue
                rejected_at = max(_ensure_utc(value[1]) for value in latest.values())
                consent = db.scalar(
                    select(TalentPoolConsent)
                    .where(
                        TalentPoolConsent.organization_id == organization.id,
                        TalentPoolConsent.candidate_id == candidate.id,
                        TalentPoolConsent.response == "accepted",
                    )
                    .order_by(TalentPoolConsent.granted_at.desc())
                    .limit(1)
                )
                if consent and consent.revoked_at is None and consent.granted_at:
                    eligible_at = _add_months(
                        _ensure_utc(consent.granted_at), organization.talent_pool_retention_months
                    )
                else:
                    eligible_at = _add_months(rejected_at, organization.rejected_retention_months)
                if eligible_at <= now:
                    eligible.append(RetentionCandidate(candidate.id, organization.id, eligible_at))
        return sorted(eligible, key=lambda item: (item.eligible_at, str(item.candidate_id)))

    def run_retention(
        self,
        db: Session,
        *,
        dry_run: bool,
        max_deletions: int | None = None,
        storage: StorageProvider | None = None,
    ) -> dict[str, int | bool]:
        if not settings.retention_enabled and not dry_run:
            return {"enabled": False, "dry_run": False, "eligible": 0, "deleted": 0}
        eligible = self.eligible_candidates(db)
        cap = settings.retention_max_deletions_per_run if max_deletions is None else max_deletions
        if not 1 <= cap <= settings.retention_max_deletions_per_run:
            raise ValueError("Retention deletion cap is outside the configured per-run limit.")
        selected = eligible[:cap]
        result = {
            "enabled": settings.retention_enabled,
            "dry_run": dry_run,
            "eligible": len(eligible),
            "selected": len(selected),
            "deleted": 0,
        }
        totals: Counter[str] = Counter()
        for item in selected:
            counts = self.erase_candidate(
                db,
                candidate_id=item.candidate_id,
                organization_id=item.organization_id,
                storage=storage,
                dry_run=dry_run,
                audit=not dry_run,
            )
            for key, count in counts.items():
                if key != "already_anonymized" and isinstance(count, int):
                    totals[key] += count
        result.update(
            {
                "deleted": 0 if dry_run else len(selected),
                **{f"{key}_count": value for key, value in totals.items()},
            }
        )
        return result


def _count_ids(db: Session, model, column, ids: list[uuid.UUID]) -> int:
    if not ids:
        return 0
    return db.scalar(select(func.count()).select_from(model).where(column.in_(ids))) or 0


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _ensure_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _workflow_filter(
    org_id, candidate_id, resume_ids, application_ids, profile_ids, evaluation_ids
):
    from sqlalchemy import and_, or_

    conditions = [
        and_(
            WorkflowRun.related_entity_type == "candidate",
            WorkflowRun.related_entity_id == candidate_id,
        )
    ]
    for kind, ids in (
        ("resume", resume_ids),
        ("job_application", application_ids),
        ("candidate_profile", profile_ids),
        ("candidate_evaluation", evaluation_ids),
    ):
        if ids:
            conditions.append(
                and_(
                    WorkflowRun.related_entity_type == kind, WorkflowRun.related_entity_id.in_(ids)
                )
            )
    return and_(WorkflowRun.organization_id == org_id, or_(*conditions))


def _count_workflow_runs(
    db, org_id, candidate_id, resume_ids, app_ids, profile_ids, evaluation_ids
):
    return (
        db.scalar(
            select(func.count())
            .select_from(WorkflowRun)
            .where(
                _workflow_filter(
                    org_id, candidate_id, resume_ids, app_ids, profile_ids, evaluation_ids
                )
            )
        )
        or 0
    )


def _delete_workflow_runs(
    db, org_id, candidate_id, resume_ids, app_ids, profile_ids, evaluation_ids
):
    db.execute(
        delete(WorkflowRun).where(
            _workflow_filter(org_id, candidate_id, resume_ids, app_ids, profile_ids, evaluation_ids)
        )
    )
