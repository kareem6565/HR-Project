"""Structured logging, request context correlation, and data redaction (HERA Prompt 6).

Provides:
- Async-safe Request ID ContextVar tracking.
- Redaction of sensitive tokens, passwords, emails, phone numbers, CV markers, and credentials.
- Sanitization against log injection (CR/LF, control characters).
- Structured JSON and human-readable text log formatting.
- Clean logging setup without duplicate root handlers.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from datetime import UTC, datetime
import json
import logging
import re
import sys
from typing import Any

# ContextVar storing the server-generated request ID for the current async task / thread.
request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    """Return the active server-generated request ID, or None if outside a request context."""
    return request_id_context.get()


def set_request_id(request_id: str | None) -> Token:
    """Set the active server-generated request ID and return the context token."""
    return request_id_context.set(request_id)


# Precompiled regex patterns for redacting sensitive values from logs
_BEARER_TOKEN_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]+", re.IGNORECASE)
_JWT_PATTERN = re.compile(r"\bey[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]+\b")
_KEY_VALUE_SECRET_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|secret(?:_key)?|password|auth_token|access_token)\b\s*[:=]\s*['\"]?([^\s,'\"&]+)['\"]?"
)
_EMAIL_PATTERN = re.compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b")
_PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
_DB_URL_PATTERN = re.compile(
    r"(?i)\b(postgres(?:ql)?(?:\+[a-z0-9]+)?://[^:]+:)([^@]+)(@)",
)
_CONTROL_CHAR_PATTERN = re.compile(r"[\r\n\t\x00-\x1f\x7f]")


def sanitize_log_value(value: Any) -> Any:
    """Redact sensitive patterns and sanitize against control-character log injection."""
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    text = value

    # Redact credentials and sensitive data
    text = _BEARER_TOKEN_PATTERN.sub("Bearer [REDACTED]", text)
    text = _JWT_PATTERN.sub("[TOKEN_REDACTED]", text)
    text = _KEY_VALUE_SECRET_PATTERN.sub(r"\1=[REDACTED]", text)
    text = _DB_URL_PATTERN.sub(r"\1[REDACTED]\3", text)
    text = _EMAIL_PATTERN.sub("[EMAIL_REDACTED]", text)
    text = _PHONE_PATTERN.sub("[PHONE_REDACTED]", text)

    # Sanitize multiline and control characters to prevent log forging
    text = _CONTROL_CHAR_PATTERN.sub(" ", text)
    return text.strip()


class RedactingFilter(logging.Filter):
    """Logging filter that redacts sensitive information from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = sanitize_log_value(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: (sanitize_log_value(v) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(
                    sanitize_log_value(v) if isinstance(v, str) else v for v in record.args
                )

        return True


class StructuredJsonFormatter(logging.Formatter):
    """JSON formatter emitting standardized, structured log records."""

    def format(self, record: logging.LogRecord) -> str:
        req_id = getattr(record, "request_id", None) or get_request_id()
        sanitized_msg = sanitize_log_value(record.getMessage())

        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitized_msg,
            "request_id": req_id,
        }

        context_keys = (
            "method",
            "route",
            "status_code",
            "duration_ms",
            "error_type",
            "workflow_id",
            "job_id",
            "candidate_id",
            "error_code",
        )
        for key in context_keys:
            if hasattr(record, key):
                val = getattr(record, key)
                log_data[key] = sanitize_log_value(val) if isinstance(val, str) else val

        if record.exc_info and record.exc_info[0]:
            log_data["exception_class"] = record.exc_info[0].__name__

        return json.dumps(log_data, default=str)


class TextLogFormatter(logging.Formatter):
    """Human-readable text formatter including request ID correlation."""

    def format(self, record: logging.LogRecord) -> str:
        req_id = getattr(record, "request_id", None) or get_request_id() or "-"
        ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        sanitized_msg = sanitize_log_value(record.getMessage())
        base = f"[{ts}] [{record.levelname:<5}] [req:{req_id}] {record.name}: {sanitized_msg}"

        if hasattr(record, "method") and hasattr(record, "route"):
            route = getattr(record, "route", "-")
            status = getattr(record, "status_code", "-")
            duration = getattr(record, "duration_ms", "-")
            base += f" ({record.method} {route} -> {status} in {duration}ms)"

        return base


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
) -> None:
    """Configure structured logging on stdout without duplicate handlers."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    if log_format.lower() == "text":
        formatter: logging.Formatter = TextLogFormatter()
    else:
        formatter = StructuredJsonFormatter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(formatter)
    handler.addFilter(RedactingFilter())

    # Configure application logger hierarchy
    app_logger = logging.getLogger("app")
    app_logger.setLevel(level)
    app_logger.handlers.clear()
    app_logger.addHandler(handler)
    app_logger.propagate = False
