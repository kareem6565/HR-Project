from __future__ import annotations

import calendar
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Candidate, Organization, TalentPoolConsent
from app.services.audit_service import AuditService
from app.services.errors import InvalidStateError, NotFoundError

CONSENT_VERSION = "talent-pool-2026-10-v1"


def _consent_text(organization_name: str) -> str:
    return (
        f"I agree that {organization_name} may use the profile and skills derived from my "
        "application to identify future job opportunities within this organization for 12 "
        "months from acceptance. This does not change the decision about my original job "
        "application or authorize sharing with another organization. I may withdraw this "
        "consent by contacting the organization. This consent does not authorize indefinite "
        "retention of my CV or evaluation evidence."
    )
LINK_LIFETIME = timedelta(days=7)


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


class TalentPoolConsentService:
    def create_link(
        self,
        db: Session,
        *,
        candidate_id: uuid.UUID,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID,
    ) -> tuple[str, datetime]:
        candidate = db.get(Candidate, candidate_id)
        if candidate is None or candidate.organization_id != organization_id:
            raise NotFoundError("Candidate was not found.")

        now = datetime.now(UTC)
        token = secrets.token_urlsafe(32)
        expires_at = now + LINK_LIFETIME
        organization = db.get(Organization, organization_id)
        record = TalentPoolConsent(
            organization_id=organization_id,
            candidate_id=candidate_id,
            created_by_user_id=actor_user_id,
            token_hash=self._hash(token),
            link_expires_at=expires_at,
            consent_text=_consent_text(organization.name if organization else "HERA"),
            consent_version=CONSENT_VERSION,
        )
        db.add(record)
        AuditService().log_event(
            db,
            action="talent_pool.consent_link_created",
            entity_type="candidate",
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            entity_id=candidate_id,
            metadata={"link_expires_at": expires_at.isoformat()},
        )
        db.flush()
        return token, expires_at

    def preview(self, db: Session, *, token: str) -> dict:
        record = self._get_usable_link(db, token)
        organization = db.get(Organization, record.organization_id)
        return {
            "organization_name": organization.name if organization else "HERA organization",
            "consent_text": record.consent_text,
            "consent_version": record.consent_version,
            "link_expires_at": record.link_expires_at,
        }

    def respond(self, db: Session, *, token: str, decision: str) -> datetime | None:
        if decision not in {"accepted", "declined"}:
            raise InvalidStateError("The consent response is invalid.")
        record = self._get_usable_link(db, token, lock=True)
        now = datetime.now(UTC)
        record.link_used_at = now
        record.responded_at = now
        record.response = decision
        consent_expires_at = None
        if decision == "accepted":
            record.granted_at = now
            record.consent_expires_at = _add_months(now, 12)
            consent_expires_at = record.consent_expires_at

        AuditService().log_event(
            db,
            action=f"talent_pool.consent_{decision}",
            entity_type="candidate",
            organization_id=record.organization_id,
            entity_id=record.candidate_id,
            metadata={"consent_version": CONSENT_VERSION},
        )
        db.flush()
        return consent_expires_at

    def withdraw(
        self,
        db: Session,
        *,
        candidate_id: uuid.UUID,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID,
    ) -> bool:
        now = datetime.now(UTC)
        active_records = list(
            db.scalars(
                select(TalentPoolConsent)
                .where(
                    TalentPoolConsent.candidate_id == candidate_id,
                    TalentPoolConsent.organization_id == organization_id,
                    TalentPoolConsent.response == "accepted",
                    TalentPoolConsent.consent_expires_at > now,
                    TalentPoolConsent.revoked_at.is_(None),
                )
                .with_for_update()
            ).all()
        )
        if not active_records:
            return False
        for record in active_records:
            record.revoked_at = now
        AuditService().log_event(
            db,
            action="talent_pool.consent_withdrawn",
            entity_type="candidate",
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            entity_id=candidate_id,
            metadata={"records_revoked": len(active_records)},
        )
        db.flush()
        return True

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _get_usable_link(self, db: Session, token: str, *, lock: bool = False) -> TalentPoolConsent:
        statement = select(TalentPoolConsent).where(
            TalentPoolConsent.token_hash == self._hash(token)
        )
        if lock:
            statement = statement.with_for_update()
        record = db.scalar(statement)
        now = datetime.now(UTC)
        if record is None or record.link_used_at is not None:
            raise NotFoundError("This consent link is invalid, expired, or already used.")
        expires_at = record.link_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= now:
            raise NotFoundError("This consent link is invalid, expired, or already used.")
        return record
