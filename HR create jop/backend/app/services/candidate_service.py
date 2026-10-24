from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Candidate
from app.services.errors import NotFoundError, ValidationError

VALID_STATUSES = frozenset({"active", "archived"})


class CandidateService:
    """Minimal candidate CRUD operations."""

    def create(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        full_name: str,
        email: str | None = None,
        phone: str | None = None,
    ) -> Candidate:
        """Create a new candidate."""
        candidate = Candidate(
            organization_id=organization_id,
            full_name=full_name,
            email=email,
            phone=phone,
        )
        db.add(candidate)
        db.flush()
        return candidate

    def get(
        self,
        db: Session,
        *,
        candidate_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Candidate:
        """Return one candidate by id, enforcing organization scope."""
        candidate = db.get(Candidate, candidate_id)
        if candidate is None or candidate.organization_id != organization_id:
            raise NotFoundError("Candidate was not found.")
        return candidate

    def list(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        search: str | None = None,
        status: str | None = None,
    ) -> list[Candidate]:
        """Return org-scoped candidates with optional search + status filters.

        ``search`` matches full name or email (case-insensitive). ``status``
        must be ``active`` or ``archived``. Results are ordered by creation
        (newest first).
        """
        if status is not None and status not in VALID_STATUSES:
            raise ValidationError(f"Invalid candidate status filter: {status!r}.")

        query = select(Candidate).where(Candidate.organization_id == organization_id)
        if status is not None:
            query = query.where(Candidate.status == status)
        if search:
            like = f"%{self._escape_like(search)}%"
            query = query.where(
                or_(
                    Candidate.full_name.ilike(like),
                    Candidate.email.ilike(like),
                )
            )
        query = query.order_by(Candidate.created_at.desc())
        return list(db.execute(query).scalars().all())

    def update(
        self,
        db: Session,
        *,
        candidate_id: uuid.UUID,
        organization_id: uuid.UUID,
        email: str | None = None,
        phone: str | None = None,
    ) -> Candidate:
        """Update a candidate's contact fields, enforcing organization scope."""
        candidate = self.get(db, candidate_id=candidate_id, organization_id=organization_id)
        if email is not None:
            candidate.email = email
        if phone is not None:
            candidate.phone = phone
        db.flush()
        return candidate

    @staticmethod
    def _escape_like(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
