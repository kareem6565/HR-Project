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
_DIAGNOSTIC_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_DIAGNOSTIC_ERROR_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_DIAGNOSTIC_FILE_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,119}$")
_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_SCREENING_STAGES = {
    "load_job_context",
    "storage_read",
    "cv_text_extraction",
    "candidate_creation",
    "resume_storage",
    "candidate_profile_extraction",
    "application_creation",
    "candidate_evaluation",
    "batch_finalize",
}
_SAFE_VALIDATION_FIELDS = {
    "schema_version",
    "full_name",
    "summary",
    "skills",
    "experience",
    "email",
    "phone",
    "location",
    "linkedin_url",
    "github_url",
    "portfolio_url",
    "education",
    "languages",
    "certifications",
    "evidence_items",
    "evidence_type",
    "requirement_ref",
    "requirement_key",
    "candidate_evidence",
    "strength",
    "provenance",
    "quote",
    "source_quote",
    "text",
    "points",
    "score",
    "requirements",
    "category",
    "dimension",
    "key",
}


def _safe_diagnostic_context(key: str, value: Any) -> Any:
    """Allow only bounded, non-payload diagnostic values into structured logs."""
    if key in {"batch_id", "item_id"}:
        text = str(value)
        return text if _UUID_PATTERN.fullmatch(text) else "[REDACTED]"
    if key == "attempt_number":
        valid_attempt = (
            isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 1000
        )
        return value if valid_attempt else None
    if key == "processing_stage":
        return value if isinstance(value, str) and value in _SCREENING_STAGES else "[REDACTED]"
    if key == "exception_class":
        valid_name = isinstance(value, str) and _DIAGNOSTIC_NAME_PATTERN.fullmatch(value)
        return value if valid_name else "[REDACTED]"
    if key == "validation_errors":
        if not isinstance(value, list):
            return []
        safe_errors = []
        for error in value[:20]:
            if not isinstance(error, dict):
                continue
            location = error.get("location", [])
            if not isinstance(location, list):
                location = []
            safe_location = []
            for part in location[:12]:
                if isinstance(part, int) and not isinstance(part, bool) and 0 <= part <= 10000:
                    safe_location.append(part)
                elif isinstance(part, str) and part in _SAFE_VALIDATION_FIELDS:
                    safe_location.append(part)
                else:
                    safe_location.append("[REDACTED]")
            error_type = error.get("type")
            safe_type = (
                error_type
                if isinstance(error_type, str)
                and _DIAGNOSTIC_ERROR_TYPE_PATTERN.fullmatch(error_type)
                else "[REDACTED]"
            )
            safe_errors.append({"location": safe_location, "type": safe_type})
        return safe_errors
    if key == "exception_frames":
        if not isinstance(value, list):
            return []
        safe_frames = []
        for frame in value[:30]:
            if not isinstance(frame, dict):
                continue
            file_name = frame.get("file")
            function = frame.get("function")
            line = frame.get("line")
            safe_frames.append(
                {
                    "file": file_name
                    if isinstance(file_name, str) and _DIAGNOSTIC_FILE_PATTERN.fullmatch(file_name)
                    else "[REDACTED]",
                    "function": function
                    if isinstance(function, str) and _DIAGNOSTIC_NAME_PATTERN.fullmatch(function)
                    else "[REDACTED]",
                    "line": line
                    if isinstance(line, int) and not isinstance(line, bool) and 0 <= line <= 100000
                    else None,
                }
            )
        return safe_frames
    return sanitize_log_value(value) if isinstance(value, str) else value


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
            "batch_id",
            "item_id",
            "attempt_number",
            "processing_stage",
            "exception_class",
            "validation_errors",
            "exception_frames",
        )
        for key in context_keys:
            if hasattr(record, key):
                val = getattr(record, key)
                log_data[key] = _safe_diagnostic_context(key, val)

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
