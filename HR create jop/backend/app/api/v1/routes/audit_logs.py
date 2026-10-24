from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, require_roles
from app.api.v1.schemas.audit_logs import AuditLogListResponse
from app.core.database import get_db
from app.services.audit_service import AuditService
from app.services.errors import ValidationError

router = APIRouter()


@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    status_code=status.HTTP_200_OK,
)
def list_audit_logs(
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx: RequestContext = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    """List audit trail records scoped to the administrator's organization."""
    if from_date and to_date and from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="from_date cannot be later than to_date.",
        )

    try:
        records, total = AuditService().list_logs(
            db,
            organization_id=ctx.organization_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            offset=offset,
        )
    except ValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(err),
        ) from err

    # Audit the administrator accessing audit history with safe parameters
    AuditService().log_event(
        db,
        action="audit_log.accessed",
        entity_type="audit_log",
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
        metadata={
            "limit": limit,
            "offset": offset,
            "action_filter": action,
            "entity_type_filter": entity_type,
        },
        flush=False,
    )

    return AuditLogListResponse(
        items=records,
        total=total,
        limit=limit,
        offset=offset,
    )
