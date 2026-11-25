import logging
import re
import threading
import traceback
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.ai.providers.errors import (
    ProviderBudgetExceededError,
    ProviderError,
    ProviderInsufficientCreditsError,
    ProviderInvalidRequestError,
    ProviderInvalidResponseError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from app.ai.providers.factory import resolve_ai_config
from app.api.v1.router import api_router
from app.api.v1.routes.health import router as health_router
from app.core.config import settings
from app.core.logging import get_request_id, setup_logging
from app.core.middleware import RequestCorrelationMiddleware
from app.services.errors import (
    ConflictError,
    InvalidStateError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
    VersionConflictError,
)

logger = logging.getLogger("app.main")


def _provider_error_response(request: Request, exc: ProviderError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or get_request_id()
    route = (
        request.scope.get("route").path
        if request.scope.get("route") and hasattr(request.scope.get("route"), "path")
        else request.url.path
    )
    if isinstance(exc, ProviderBudgetExceededError):
        status_code = 429
    elif isinstance(exc, ProviderRateLimitError):
        status_code = 429
    elif isinstance(exc, ProviderInsufficientCreditsError):
        status_code = 402
    elif isinstance(exc, ProviderTimeoutError):
        status_code = 504
    elif isinstance(exc, ProviderInvalidResponseError):
        status_code = 502
    elif isinstance(exc, ProviderInvalidRequestError):
        status_code = 502
    else:
        status_code = 503

    logger.log(
        logging.WARNING if status_code < 500 else logging.ERROR,
        "AI request failed during %s (%s)",
        exc.stage,
        exc.error_code,
        extra={
            "request_id": request_id,
            "method": request.method,
            "route": route,
            "status_code": status_code,
            "error_type": type(exc).__name__,
            "error_code": exc.error_code,
            "processing_stage": exc.stage,
            "provider_status": exc.provider_status,
            "provider_request_id": exc.provider_request_id,
            "retryable": exc.retryable,
        },
    )
    legacy_error_type = {
        "provider_timeout": "timeout",
        "provider_rate_limit": "rate_limit",
        "provider_credits_exhausted": "insufficient_credits",
    }.get(exc.error_code, exc.error_code)
    response_body = {
        "detail": exc.safe_message,
        "error_type": legacy_error_type,
        "error_code": exc.error_code,
        "request_id": request_id,
        "retryable": exc.retryable,
    }
    return JSONResponse(
        status_code=status_code,
        content=response_body,
        headers={"X-Request-ID": request_id} if request_id else None,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background workers and stop them cleanly during shutdown."""
    ai_config = resolve_ai_config(settings)
    logger.info(
        "Effective AI provider configured: provider=%s model=%s demo=%s",
        ai_config["provider"],
        ai_config["model"] or "none",
        ai_config["is_fake"],
    )
    workers: list[object] = []
    worker_threads: list[threading.Thread] = []

    if settings.enable_outbox_worker:
        try:
            from app.services.outbox_worker import OutboxWorker

            outbox_worker = OutboxWorker()
            outbox_thread = threading.Thread(
                target=outbox_worker.run_loop,
                kwargs={"poll_interval_seconds": 2.0},
                daemon=True,
                name="outbox-worker",
            )
            outbox_thread.start()
            workers.append(outbox_worker)
            worker_threads.append(outbox_thread)
            logger.info("Outbox worker thread started.")
        except Exception:
            logger.exception("Failed to start outbox worker.")

    if settings.enable_screening_worker:
        from app.worker import ScreeningWorker

        screening_worker = ScreeningWorker()
        screening_thread = threading.Thread(
            target=screening_worker.run_loop,
            kwargs={"poll_interval_seconds": 2.0},
            daemon=True,
            name="screening-worker",
        )
        screening_thread.start()
        workers.append(screening_worker)
        worker_threads.append(screening_thread)
        logger.info("Screening worker thread started.")

    try:
        yield
    finally:
        for worker in workers:
            try:
                worker.request_shutdown()
            except Exception:
                logger.exception("Failed to stop background worker.")
        for worker_thread in worker_threads:
            worker_thread.join(timeout=2.0)
        logger.info("Background workers stopped.")


def create_app() -> FastAPI:
    # Initialize structured logging based on settings
    setup_logging(log_level=settings.log_level, log_format=settings.log_format)

    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

    # Correlation middleware wraps request handling to generate X-Request-ID
    app.add_middleware(RequestCorrelationMiddleware)

    @app.middleware("http")
    async def limit_public_application_request_size(request: Request, call_next):
        if re.fullmatch(
            rf"{re.escape(settings.api_v1_prefix)}/public/jobs/[^/]+/applications",
            request.url.path,
        ):
            content_length = request.headers.get("content-length")
            if content_length and content_length.isdigit():
                max_request_bytes = settings.max_upload_bytes + 128 * 1024
                if int(content_length) > max_request_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Application upload exceeds the request size limit."},
                    )
        return await call_next(request)

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

    @app.exception_handler(PermissionDeniedError)
    async def permission_denied_handler(
        request: Request, exc: PermissionDeniedError
    ) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
        msg = str(exc).lower()
        if (
            "different organization" in msg
            or "another organization" in msg
            or "same organization" in msg
        ):
            return JSONResponse(status_code=404, content={"detail": "Resource was not found."})
        content = {"detail": str(exc)}
        if hasattr(exc, "code") and exc.code:
            content["code"] = exc.code
            if exc.code == "invalid_ai_output":
                content["error_code"] = "invalid_ai_output"
                content["request_id"] = (
                    getattr(request.state, "request_id", None) or get_request_id()
                )
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
        return _provider_error_response(request, exc)

    @app.exception_handler(ProviderError)
    async def provider_error_handler(request: Request, exc: ProviderError) -> JSONResponse:
        return _provider_error_response(request, exc)

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
                "exception_frames": [
                    {
                        "file": Path(frame.filename).name,
                        "function": frame.name,
                        "line": frame.lineno,
                    }
                    for frame in traceback.extract_tb(exc.__traceback__)[-8:]
                ],
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
