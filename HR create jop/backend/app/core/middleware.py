"""Request correlation and tracing middleware (HERA Prompt 6).

Provides:
- Server-generated UUID4 request IDs for end-to-end request tracing.
- X-Request-ID response header propagation.
- Matched route template resolution (preventing raw parameter leakage in logs).
- Request duration calculation in milliseconds.
- Exactly one structured completion log per request.
- Safe handling of client errors (401/403/422) without noisy server error logs.
- Controlled HTTP 500 error response without exposing internal traces or server paths.
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.logging import request_id_context, sanitize_log_value, set_request_id

logger = logging.getLogger("app.request")


def _resolve_route_template(request: Request) -> str:
    """Resolve the matched route template when available, or clean request path.

    Prevents raw UUIDs, query strings, or sensitive route parameters from
    becoming part of the primary route identifier.
    """
    route = request.scope.get("route")
    if route and hasattr(route, "path"):
        return str(route.path)

    # Fallback to sanitized URL path without query params
    return sanitize_log_value(request.url.path)


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """Middleware that injects a server-generated request ID and emits request logs."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Always generate a fresh server-side request ID; do not trust client input
        request_id = str(uuid.uuid4())

        # Set in request state and async context
        request.state.request_id = request_id
        token = set_request_id(request_id)
        start_time = time.perf_counter()

        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            route = _resolve_route_template(request)
            logger.error(
                "Request failed with unhandled exception: %s",
                type(exc).__name__,
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "route": route,
                    "status_code": 500,
                    "duration_ms": duration_ms,
                    "error_type": type(exc).__name__,
                },
            )
            # Return controlled JSON 500 response without leaking server paths or tracebacks
            response = JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error.",
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id},
            )
            return response
        finally:
            if response is not None:
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                route = _resolve_route_template(request)
                status_code = response.status_code

                # Ensure X-Request-ID header is attached to response
                response.headers["X-Request-ID"] = request_id

                # Emit single structured completion log
                extra_data = {
                    "request_id": request_id,
                    "method": request.method,
                    "route": route,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }

                if status_code >= 500:
                    logger.error("Request completed with server error", extra=extra_data)
                elif status_code >= 400:
                    # Expected client error (401, 403, 404, 422) - logged as info without noisy 500 alert
                    logger.info("Request completed with client status", extra=extra_data)
                else:
                    logger.info("Request completed successfully", extra=extra_data)

            request_id_context.reset(token)
