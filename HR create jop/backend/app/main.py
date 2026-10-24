import logging
import threading
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.ai.providers.errors import (
    ProviderError,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.api.v1.router import api_router
from app.api.v1.routes.health import router as health_router
from app.core.config import settings
from app.core.logging import get_request_id, setup_logging
from app.core.middleware import RequestCorrelationMiddleware
from app.services.errors import (
    ConflictError,
    InvalidStateError,
    NotFoundError,
    ValidationError,
    VersionConflictError,
)

logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the screening worker thread on startup and stop it on shutdown."""
    if not settings.enable_screening_worker:
        yield
        return

    from app.worker import ScreeningWorker

    worker = ScreeningWorker()
    worker_thread = threading.Thread(
        target=worker.run_loop,
        kwargs={"poll_interval_seconds": 2.0},
        daemon=True,
        name="screening-worker",
    )
    worker_thread.start()
    logger.info("Screening worker thread started.")
    try:
        yield
    finally:
        worker.request_shutdown()
        worker_thread.join(timeout=2.0)
        logger.info("Screening worker thread stopped.")


def create_app() -> FastAPI:
    # Initialize structured logging based on settings
    setup_logging(log_level=settings.log_level, log_format=settings.log_format)

    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

    # Correlation middleware wraps request handling to generate X-Request-ID
    app.add_middleware(RequestCorrelationMiddleware)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=settings.cors_allow_methods,
        allow_headers=["*"],
    )

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
        msg = str(exc).lower()
        if "different organization" in msg or "another organization" in msg or "same organization" in msg:
            return JSONResponse(status_code=404, content={"detail": "Resource was not found."})
        content = {"detail": str(exc)}
        if hasattr(exc, "code") and exc.code:
            content["code"] = exc.code
        return JSONResponse(status_code=422, content=content)

    @app.exception_handler(InvalidStateError)
    async def invalid_state_handler(request: Request, exc: InvalidStateError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(VersionConflictError)
    async def version_conflict_handler(request: Request, exc: VersionConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ProviderRateLimitError)
    async def provider_rate_limit_handler(
        request: Request, exc: ProviderRateLimitError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={
                "detail": "AI provider rate limit reached. Try again later.",
                "error_type": "rate_limit",
            },
        )

    @app.exception_handler(ProviderError)
    async def provider_error_handler(request: Request, exc: ProviderError) -> JSONResponse:
        if isinstance(exc, ProviderTimeoutError):
            message = "AI provider timed out. Try again."
            error_type = "timeout"
        elif isinstance(exc, ProviderInvalidRequestError):
            message = "AI provider rejected the request."
            error_type = "invalid_request"
        else:
            message = "AI provider is currently unavailable. Try again."
            error_type = "unavailable"
        return JSONResponse(
            status_code=503,
            content={
                "detail": message,
                "error_type": error_type,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = (
            getattr(request.state, "request_id", None) or get_request_id() or str(uuid.uuid4())
        )
        route_path = (
            request.scope.get("route").path
            if request.scope.get("route") and hasattr(request.scope.get("route"), "path")
            else request.url.path
        )
        logger.error(
            "Unhandled server exception: %s",
            type(exc).__name__,
            extra={
                "request_id": request_id,
                "error_type": type(exc).__name__,
                "route": route_path,
                "method": request.method,
            },
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error.",
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
        )

    # Health routes available at both root and under api_v1_prefix
    app.include_router(health_router, tags=["health"])
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
