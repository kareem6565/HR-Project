"""Small helpers for privacy-conscious AI result cache identities."""

from __future__ import annotations

import hashlib
import json
import unicodedata
import uuid
from typing import Any


def normalized_resume_hash(resume_text: str) -> str:
    """Hash normalized resume text without retaining the text itself."""
    normalized = " ".join(unicodedata.normalize("NFKC", resume_text).split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def provider_identity(provider: Any) -> tuple[str, str] | None:
    """Return stable provider/model identifiers, or disable caching if unknown."""
    provider_name = getattr(provider, "provider_name", None) or getattr(provider, "_provider", None)
    model_name = getattr(provider, "model_name", None) or getattr(provider, "_model", None)
    if not provider_name or not model_name:
        return None
    return str(provider_name), str(model_name)


def cache_key(identity: dict[str, Any]) -> str:
    """Hash cache identity metadata into a fixed-size, non-PII key."""
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def cached_trace_ids(provenance: dict[str, Any] | None) -> dict[str, str] | None:
    """Read persisted trace IDs only when all expected values are valid UUIDs."""
    if not provenance:
        return None
    raw = provenance.get("cache_trace_ids")
    if not isinstance(raw, dict):
        return None
    required = {"workflow_run_id", "workflow_step_trace_id"}
    if not required.issubset(raw):
        return None
    try:
        return {key: str(uuid.UUID(str(value))) for key, value in raw.items()}
    except (ValueError, TypeError, AttributeError):
        return None
