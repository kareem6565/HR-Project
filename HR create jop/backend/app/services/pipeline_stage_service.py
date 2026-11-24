from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import JobApplication, PipelineStageTransition, User
from app.services.audit_service import AuditService
from app.services.errors import (
    ConflictError,
    InvalidStateError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)

PIPELINE_STAGES = (
    "screening",
    "review",
    "interview",
    "offer",
    "hired",
    "rejected",
    "withdrawn",
    "archived",
)
APPLICATION_STATUSES = (
    "created",
    "analysis_pending",
    "analyzing",
    "analysis_failed",
    "ready_for_review",
    "hold",
    "advanced",
    "rejected",
    "archived",
)
ACTIVE_STAGES = frozenset({"screening", "review", "interview", "offer", "hired", "withdrawn"})

# Rejection is recorded through DecisionService so the HR decision history remains authoritative.
ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "screening": ("review", "withdrawn", "archived"),
    "review": ("screening", "interview", "withdrawn", "archived"),
    "interview": ("review", "offer", "withdrawn", "archived"),
    "offer": ("interview", "hired", "withdrawn", "archived"),
    "hired": (),
    "rejected": ("archived",),
    "withdrawn": ("archived",),
    "archived": (),
}
STAGE_ORDER = {"screening": 0, "review": 1, "interview": 2, "offer": 3, "hired": 4}


def validate_status_stage(status: str, stage: str) -> None:
    """Enforce the persisted status/stage compatibility matrix."""
    if status == "rejected":
        valid = stage == "rejected"
    elif status == "archived":
        valid = stage == "archived"
    else:
        valid = status in APPLICATION_STATUSES and status not in {"rejected", "archived"}
        valid = valid and stage in ACTIVE_STAGES
    if not valid:
        raise InvalidStateError(
            f"Application status {status!r} cannot use pipeline stage {stage!r}."
        )


def authorize_pipeline_action(
    db: Session,
    *,
    application: JobApplication,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    admin_only: bool = False,
) -> User:
    """Central permission check; future H4 roles extend this one policy function."""
    if application.organization_id != organization_id:
        raise NotFoundError("JobApplication was not found.")
    actor = db.scalar(
        select(User).where(
            User.id == actor_user_id,
            User.organization_id == organization_id,
            User.status == "active",
            User.is_active.is_(True),
        )
    )
    if actor is None:
        raise NotFoundError("User was not found.")
    roles = set(actor.effective_roles)
    allowed = {"admin"} if admin_only else {"admin", "recruiter"}
    if not roles.intersection(allowed):
        raise PermissionDeniedError("A same-organization HR role is required for this action.")
    return actor


class PipelineStageService:
    """Human-controlled pipeline transitions and read state."""

    def _application(
        self,
        db: Session,
        *,
        application_id: uuid.UUID,
        organization_id: uuid.UUID,
        for_update: bool = False,
    ) -> JobApplication:
        statement = select(JobApplication).where(
            JobApplication.id == application_id,
            JobApplication.organization_id == organization_id,
        )
        if for_update:
            statement = statement.with_for_update()
        application = db.scalar(statement)
        if application is None:
            raise NotFoundError("JobApplication was not found.")
        return application

    def state(
        self,
        db: Session,
        *,
        application_id: uuid.UUID,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID,
    ) -> dict:
        application = self._application(
            db, application_id=application_id, organization_id=organization_id
        )
        actor = authorize_pipeline_action(
            db,
            application=application,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
        )
        validate_status_stage(application.status, application.pipeline_stage)
        transitions = list(
            db.scalars(
                select(PipelineStageTransition)
                .where(
                    PipelineStageTransition.organization_id == organization_id,
                    PipelineStageTransition.job_application_id == application.id,
                )
                .order_by(
                    PipelineStageTransition.created_at.desc(), PipelineStageTransition.id.desc()
                )
                .limit(50)
            )
        )
        return {
            "application_id": application.id,
            "status": application.status,
            "pipeline_stage": application.pipeline_stage,
            "allowed_next_stages": list(ALLOWED_TRANSITIONS[application.pipeline_stage]),
            "allowed_correction_stages": (
                ["screening", "review", "interview", "offer", "withdrawn"]
                if application.pipeline_stage == "hired" and "admin" in actor.effective_roles
                else []
            ),
            "reason_required_stages": [
                target
                for target in ALLOWED_TRANSITIONS[application.pipeline_stage]
                if target == "withdrawn"
                or (
                    application.pipeline_stage in STAGE_ORDER
                    and target in STAGE_ORDER
                    and STAGE_ORDER[target] < STAGE_ORDER[application.pipeline_stage]
                )
            ],
            "is_admin": "admin" in actor.effective_roles,
            "transitions": transitions,
        }

    def transition(
        self,
        db: Session,
        *,
        application_id: uuid.UUID,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        expected_stage: str,
        to_stage: str,
        idempotency_key: uuid.UUID,
        reason_code: str | None = None,
        note: str | None = None,
    ) -> tuple[JobApplication, PipelineStageTransition, bool]:
        application = self._application(
            db,
            application_id=application_id,
            organization_id=organization_id,
            for_update=True,
        )
        actor = authorize_pipeline_action(
            db,
            application=application,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
        )
        existing = db.scalar(
            select(PipelineStageTransition).where(
                PipelineStageTransition.organization_id == organization_id,
                PipelineStageTransition.job_application_id == application.id,
                PipelineStageTransition.actor_user_id == actor.id,
                PipelineStageTransition.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if (
                existing.from_stage != expected_stage
                or existing.to_stage != to_stage
                or existing.reason_code != reason_code
                or existing.note != note
            ):
                raise ConflictError(
                    "This idempotency key was already used for a different transition."
                )
            return application, existing, True

        validate_status_stage(application.status, application.pipeline_stage)
        if application.pipeline_stage != expected_stage:
            raise ConflictError("The application stage changed. Reload the latest pipeline state.")
        if to_stage not in ALLOWED_TRANSITIONS.get(expected_stage, ()):
            raise InvalidStateError("This pipeline stage transition is not allowed.")
        if to_stage == "withdrawn" and not reason_code:
            raise ValidationError(
                "A reason code is required when marking an application withdrawn."
            )
        is_backward = (
            expected_stage in STAGE_ORDER
            and to_stage in STAGE_ORDER
            and STAGE_ORDER[to_stage] < STAGE_ORDER[expected_stage]
        )
        if is_backward and not reason_code:
            raise ValidationError("A reason code is required for a backward stage transition.")
        validate_status_stage(
            "archived" if to_stage == "archived" else application.status, to_stage
        )

        new_status = "archived" if to_stage == "archived" else application.status
        values = {"pipeline_stage": to_stage, "status": new_status, "updated_at": datetime.now(UTC)}
        if to_stage == "archived":
            values["archived_at"] = datetime.now(UTC)
        result = db.execute(
            update(JobApplication)
            .where(
                JobApplication.id == application.id,
                JobApplication.organization_id == organization_id,
                JobApplication.pipeline_stage == expected_stage,
                JobApplication.status == application.status,
            )
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise ConflictError("The application stage changed. Reload the latest pipeline state.")
        application.pipeline_stage = to_stage
        application.status = new_status
        if to_stage == "archived":
            application.archived_at = values["archived_at"]

        transition = PipelineStageTransition(
            organization_id=organization_id,
            job_application_id=application.id,
            actor_user_id=actor.id,
            from_stage=expected_stage,
            to_stage=to_stage,
            reason_code=reason_code,
            note=note,
            source="hr",
            idempotency_key=idempotency_key,
        )
        db.add(transition)
        AuditService().log_event(
            db,
            action="pipeline_stage.changed",
            entity_type="job_application",
            organization_id=organization_id,
            actor_user_id=actor.id,
            entity_id=application.id,
            metadata={"from_stage": expected_stage, "to_stage": to_stage},
            flush=False,
        )
        db.flush()
        return application, transition, False

    def correct_hired_stage(
        self,
        db: Session,
        *,
        application_id: uuid.UUID,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        expected_stage: str,
        to_stage: str,
        idempotency_key: uuid.UUID,
        reason_code: str,
        reason: str,
    ) -> tuple[JobApplication, PipelineStageTransition, bool]:
        application = self._application(
            db,
            application_id=application_id,
            organization_id=organization_id,
            for_update=True,
        )
        actor = authorize_pipeline_action(
            db,
            application=application,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            admin_only=True,
        )
        existing = db.scalar(
            select(PipelineStageTransition).where(
                PipelineStageTransition.organization_id == organization_id,
                PipelineStageTransition.job_application_id == application.id,
                PipelineStageTransition.actor_user_id == actor.id,
                PipelineStageTransition.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if (
                existing.from_stage != expected_stage
                or existing.to_stage != to_stage
                or existing.reason_code != reason_code
                or existing.note != reason
            ):
                raise ConflictError(
                    "This idempotency key was already used for a different correction."
                )
            return application, existing, True
        validate_status_stage(application.status, application.pipeline_stage)
        if application.pipeline_stage != "hired" or expected_stage != "hired":
            raise ConflictError("Corrective transitions are available only from the hired stage.")
        if to_stage not in {"screening", "review", "interview", "offer", "withdrawn"}:
            raise InvalidStateError("This corrective stage is not allowed.")
        validate_status_stage(application.status, to_stage)
        result = db.execute(
            update(JobApplication)
            .where(
                JobApplication.id == application.id,
                JobApplication.organization_id == organization_id,
                JobApplication.pipeline_stage == expected_stage,
                JobApplication.status == application.status,
            )
            .values(pipeline_stage=to_stage, updated_at=datetime.now(UTC))
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise ConflictError("The application stage changed. Reload the latest pipeline state.")
        application.pipeline_stage = to_stage
        transition = PipelineStageTransition(
            organization_id=organization_id,
            job_application_id=application.id,
            actor_user_id=actor.id,
            from_stage="hired",
            to_stage=to_stage,
            reason_code=reason_code,
            note=reason,
            source="admin_correction",
            idempotency_key=idempotency_key,
        )
        db.add(transition)
        AuditService().log_event(
            db,
            action="pipeline_stage.corrected",
            entity_type="job_application",
            organization_id=organization_id,
            actor_user_id=actor.id,
            entity_id=application.id,
            metadata={"from_stage": "hired", "to_stage": to_stage},
            flush=False,
        )
        db.flush()
        return application, transition, False

    def record_hr_rejection(
        self,
        db: Session,
        *,
        application: JobApplication,
        actor_user_id: uuid.UUID,
        reason: str | None,
    ) -> PipelineStageTransition | None:
        """Mirror an explicit HR rejection into stage history in the same transaction."""
        if application.pipeline_stage == "hired":
            raise InvalidStateError("A hired application cannot be rejected in the normal flow.")
        if application.pipeline_stage in {"rejected", "archived"}:
            if application.pipeline_stage == "rejected":
                return None
            raise InvalidStateError("An archived application cannot be rejected.")
        old_stage = application.pipeline_stage
        application.pipeline_stage = "rejected"
        transition = PipelineStageTransition(
            organization_id=application.organization_id,
            job_application_id=application.id,
            actor_user_id=actor_user_id,
            from_stage=old_stage,
            to_stage="rejected",
            note=reason,
            source="hr_decision",
        )
        db.add(transition)
        return transition
