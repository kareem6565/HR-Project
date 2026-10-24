"""Thread-safe in-memory overrides for server configuration.

Used to let users set a Soal API key at runtime without restarting the
server. Not persisted to disk — resets on process restart, which is the
intended behaviour for a development/demo helper.
"""

from __future__ import annotations

import threading

_lock = threading.Lock()
_soal_api_key: str | None = None


def set_api_key(key: str | None) -> None:
    """Store a runtime Soal API key override (pass ``None`` to clear)."""
    cleaned = (key or "").strip() or None
    with _lock:
        global _soal_api_key
        _soal_api_key = cleaned


def get_api_key() -> str | None:
    """Return the current runtime override, or ``None``."""
    with _lock:
        return _soal_api_key


def clear_api_key() -> None:
    """Convenience helper – equivalent to ``set_api_key(None)``."""
    set_api_key(None)
