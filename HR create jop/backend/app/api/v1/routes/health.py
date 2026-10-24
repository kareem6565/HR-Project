import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

logger = logging.getLogger(__name__)

router = APIRouter()


def check_database_readiness() -> bool:
    """Perform a lightweight database connectivity check.

    Ensures connection resources are always released back to pool.
    Supports app.dependency_overrides[get_db] for hermetic testing.
    """
    from app.core.database import SessionLocal, get_db
    from app.main import app

    try:
        if get_db in app.dependency_overrides:
            gen = app.dependency_overrides[get_db]()
            db = next(gen)
            try:
                db.execute(text("SELECT 1"))
                return True
            finally:
                try:
                    next(gen, None)
                except Exception:
                    pass
        else:
            db = SessionLocal()
            try:
                db.execute(text("SELECT 1"))
                return True
            finally:
                db.close()
    except Exception as exc:
        logger.warning("Database readiness probe failed: %s", type(exc).__name__)
        return False


@router.get("/health")
def health_check() -> dict[str, str]:
    """Liveness probe: answers whether the application process can respond.

    Does not perform a database query or expose internal diagnostics.
    """
    return {"status": "ok"}


@router.get("/health/ready")
def readiness_check() -> JSONResponse:
    """Readiness probe: performs a lightweight database connectivity check.

    Returns HTTP 200 when database connectivity is healthy, or HTTP 503
    when unavailable, ensuring database resources are cleanly released.
    """
    is_ready = check_database_readiness()
    if is_ready:
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ready"})
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "unavailable", "detail": "Database unavailable."},
    )
