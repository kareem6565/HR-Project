from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models import Organization
from app.services.errors import NotFoundError


class OrganizationService:
    """Minimal organization operations for MVP bootstrap."""

    def create(self, db: Session, *, name: str) -> Organization:
        """Create a new organization."""
        organization = Organization(name=name)
        db.add(organization)
        db.flush()
        return organization

    def get(self, db: Session, *, organization_id: uuid.UUID) -> Organization:
        """Return one organization by id."""
        organization = db.get(Organization, organization_id)
        if organization is None:
            raise NotFoundError("Organization was not found.")
        return organization
