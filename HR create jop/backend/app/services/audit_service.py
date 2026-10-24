"""Audit logging and retrieval service (HERA Prompt 9).

Provides:
- Append-only audit record creation with strict data minimization.
- Organization-scoped audit log querying with deterministic ordering.
- Independent auth failure recording without leaking credentials or account existence.
- Zero update or delete operations exposed.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import get_request_id, sanitize_log_value
from app.models.audit_log import AuditLog
from app.services.errors import ValidationError

logger = logging.getLogger("app.services.audit")

PROHIBITED_METADATA_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "password_cleartext",
        "token",
        "access_token",
        "refresh_token",
        "auth_token",
        "secret",
        "secret_key",
        "api_key",
        "authorization",
        "cookie",
        "cookies",
        "cv_text",
        "resume_text",
        "extracted_text",
        "raw_text",
        "cv_content",
        "file_bytes",
        "email",
        "email_address",
        "phone",
        "phone_number",
    }
)

SAFE_AUTH_FAILURE_CATEGORIES = frozenset(
    {
        "invalid_credentials",
        "account_inactive",
        "rate_limited",
        "account_locked",
    }
)

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 50


def sanitize_audit_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    """Sanitize and constrain metadata dictionary to prevent leaking sensitive data."""
    if not metadata:
        return None

    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        key_lower = str(key).lower().strip()
        if key_lower in PROHIBITED_METADATA_KEYS or any(
            bad in key_lower
            for bad in (
                "password",
                "token",
                "secret",
                "api_key",
                "cv_text",
                "resume_text",
                "extracted_text",
            )
        ):
            continue

        if isinstance(value, (int, float, bool)) or value is None:
            cleaned[key] = value
        elif isinstance(value, str):
            cleaned[key] = sanitize_log_value(value)
        elif isinstance(value, uuid.UUID):
            cleaned[key] = str(value)
        elif isinstance(value, (list, tuple)):
            cleaned_list = []
            for item in value:
                if isinstance(item, (int, float, bool)):
                    cleaned_list.append(item)
                elif isinstance(item, str):
                    cleaned_list.append(sanitize_log_value(item))
                elif isinstance(item, uuid.UUID):
                    cleaned_list.append(str(item))
            cleaned[key] = cleaned_list
        elif isinstance(value, dict):
            nested = sanitize_audit_metadata(value)
            if nested is not None:
                cleaned[key] = nested

    return cleaned or None


class AuditService:
    """Append-only audit trail logging and authorized organization querying."""

    def log_event(
        self,
        db: Session,
        *,
        action: str,
        entity_type: str,
        organization_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
        entity_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
        request_id: str | None = None,
        flush: bool = True,
    ) -> AuditLog:
        """Create a new append-only audit event.

        Strictly enforces data minimization: sensitive keys (passwords, tokens, CV text,
        emails) are omitted from event metadata.
        """
        correlation_id = request_id or get_request_id()
        safe_metadata = sanitize_audit_metadata(metadata)

        audit_entry = AuditLog(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=action.strip(),
            entity_type=entity_type.strip(),
            entity_id=entity_id,
            request_id=correlation_id,
            event_metadata=safe_metadata,
        )
        db.add(audit_entry)
        if flush:
            db.flush()
        return audit_entry

    def log_auth_failure(
        self,
        db: Session,
        *,
        category: str = "invalid_credentials",
        organization_id: uuid.UUID | None = None,
        request_id: str | None = None,
    ) -> AuditLog:
        """Record an authentication failure with a safe category.

        Does not record raw submitted credentials, email addresses, or user identifiers.
        Uses an isolated flush to guarantee event recording.
        """
        safe_category = category if category in SAFE_AUTH_FAILURE_CATEGORIES else "invalid_credentials"
        return self.log_event(
            db,
            action="auth.login_failed",
            entity_type="auth",
            organization_id=organization_id,
            actor_user_id=None,
            entity_id=None,
            metadata={"category": safe_category},
            request_id=request_id,
            flush=True,
        )

    def list_logs(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        """Query audit records scoped strictly to the specified organization.

        Returns (records, total_count) ordered deterministically by created_at DESC, id DESC.
        """
        if from_date and to_date and from_date > to_date:
            raise ValidationError("from_date cannot be later than to_date.")

        bounded_limit = max(1, min(limit, MAX_PAGE_SIZE))
        bounded_offset = max(0, offset)

        stmt = select(AuditLog).where(AuditLog.organization_id == organization_id)

        if action:
            stmt = stmt.where(AuditLog.action == action.strip())
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type.strip())
        if entity_id:
            stmt = stmt.where(AuditLog.entity_id == entity_id)
        if from_date:
            stmt = stmt.where(AuditLog.created_at >= from_date)
        if to_date:
            stmt = stmt.where(AuditLog.created_at <= to_date)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = db.scalar(count_stmt) or 0

        query_stmt = (
            stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(bounded_limit)
            .offset(bounded_offset)
        )
        records = list(db.scalars(query_stmt).all())
        return records, total
