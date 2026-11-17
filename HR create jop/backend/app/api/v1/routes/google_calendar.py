from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.v1.deps import RequestContext, get_request_context
from app.core.config import settings
from app.core.database import get_db
from app.services.email_outbox_service import EmailOutboxService
from app.services.google_oauth_service import GoogleOAuthService

# Protected HR routes (registered under authenticated recruitment router).
router = APIRouter()
# Public Google redirect callback (registered without HERA bearer auth; validated via one-time state).
public_router = APIRouter()


@router.get("/hr/google/status")
def google_connection_status(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    conn = GoogleOAuthService().get_connection(
        db, organization_id=ctx.organization_id, user_id=ctx.user_id
    )
    return GoogleOAuthService().status_payload(conn)


@router.get("/hr/google/connect")
def google_connect_start(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    service = GoogleOAuthService()
    state = service.create_state(
        db, organization_id=ctx.organization_id, user_id=ctx.user_id
    )
    url = service.build_authorize_url(state=state)
    db.commit()
    return {"authorize_url": url}


@public_router.get("/hr/google/callback")
def google_connect_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    redirect_base = (
        settings.google_oauth_post_login_redirect_uri
        or f"{settings.frontend_base_url.rstrip('/')}/interviews/availability"
    )
    params: dict[str, str] = {}
    try:
        if error:
            raise ValueError("oauth_error")
        if not code or not state:
            raise ValueError("missing_oauth_params")
        service = GoogleOAuthService()
        # Consume and authenticate via validated, persisted, one-time state only.
        # Consumption is committed atomically and never reusable, even if later steps fail.
        organization_id, user_id = service.consume_state(db, state)
        token_payload = service.exchange_code(code)
        service.upsert_connection(
            db,
            organization_id=organization_id,
            user_id=user_id,
            token_payload=token_payload,
        )
        db.commit()
        params["google"] = "connected"
    except Exception:
        db.rollback()
        params["google"] = "error"
    sep = "&" if "?" in redirect_base else "?"
    return RedirectResponse(url=f"{redirect_base}{sep}{urlencode(params)}", status_code=302)


@router.delete("/hr/google/disconnect")
def google_disconnect(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    GoogleOAuthService().disconnect(db, organization_id=ctx.organization_id, user_id=ctx.user_id)
    db.commit()
    return {"status": "disconnected"}


@router.post("/hr/email-outbox/process")
def process_email_outbox(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    # Authenticated HR action to drain console outbox (failure recovery / ops helper)
    count = EmailOutboxService().process_pending(db, limit=50)
    db.commit()
    return {"processed": count}
