import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, require_roles
from app.api.v1.schemas.users import UserCreate, UserResponse, UserRoleUpdate, UserStatusUpdate
from app.core.database import get_db
from app.services.audit_service import AuditService
from app.services.user_service import UserService

router = APIRouter()


@router.post(
    "/organizations/{org_id}/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_organization_user(
    org_id: str,
    body: UserCreate,
    ctx: RequestContext = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Create a user in the specified organization.

    Restricted to authenticated administrators of their own organization.
    A tenant administrator cannot create users in another organization.
    """
    try:
        organization_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="org_id must be a valid UUID.") from None

    if organization_uuid != ctx.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot provision users for another organization.",
        )

    if body.organization_id and body.organization_id != ctx.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot provision users for another organization.",
        )

    user = UserService().create(
        db,
        organization_id=organization_uuid,
        email=body.email,
        full_name=body.full_name,
        password=body.password,
        role=body.role,
    )
    AuditService().log_event(
        db,
        action="user.created",
        entity_type="user",
        organization_id=organization_uuid,
        actor_user_id=ctx.user_id,
        entity_id=user.id,
        metadata={"role": user.role, "status": user.status},
        flush=False,
    )
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    body: UserCreate,
    ctx: RequestContext = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Create a user in the caller's organization.

    Restricted to authenticated administrators.
    """
    if body.organization_id and body.organization_id != ctx.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot provision users for another organization.",
        )

    user = UserService().create(
        db,
        organization_id=ctx.organization_id,
        email=body.email,
        full_name=body.full_name,
        password=body.password,
        role=body.role,
    )
    AuditService().log_event(
        db,
        action="user.created",
        entity_type="user",
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
        entity_id=user.id,
        metadata={"role": user.role, "status": user.status},
        flush=False,
    )
    db.commit()
    db.refresh(user)
    return user


@router.get(
    "/organizations/{org_id}/users",
    response_model=list[UserResponse],
)
def list_organization_users(
    org_id: str,
    ctx: RequestContext = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """List users in the specified organization for administrators."""
    try:
        organization_uuid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="org_id must be a valid UUID.") from None

    if organization_uuid != ctx.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access users of another organization.",
        )

    return UserService().list_org_users(db, organization_id=organization_uuid)


@router.patch(
    "/users/{user_id}/role",
    response_model=UserResponse,
)
def update_user_role(
    user_id: str,
    body: UserRoleUpdate,
    ctx: RequestContext = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Update role for a user in the caller's organization."""
    try:
        target_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="user_id must be a valid UUID.") from None

    user, old_role, new_role = UserService().update_role(
        db,
        user_id=target_uuid,
        new_role=body.role,
        organization_id=ctx.organization_id,
    )
    AuditService().log_event(
        db,
        action="user.role_updated",
        entity_type="user",
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
        entity_id=user.id,
        metadata={"old_role": old_role, "new_role": new_role},
        flush=False,
    )
    db.commit()
    db.refresh(user)
    return user


@router.patch(
    "/users/{user_id}/status",
    response_model=UserResponse,
)
def update_user_status(
    user_id: str,
    body: UserStatusUpdate,
    ctx: RequestContext = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Update active/inactive status for a user in the caller's organization."""
    try:
        target_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="user_id must be a valid UUID.") from None

    user, old_status, new_status = UserService().update_status(
        db,
        user_id=target_uuid,
        new_status=body.status,
        organization_id=ctx.organization_id,
    )
    action_name = "user.deactivated" if new_status != "active" else "user.reactivated"
    AuditService().log_event(
        db,
        action=action_name,
        entity_type="user",
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user_id,
        entity_id=user.id,
        metadata={"old_status": old_status, "new_status": new_status},
        flush=False,
    )
    db.commit()
    db.refresh(user)
    return user
