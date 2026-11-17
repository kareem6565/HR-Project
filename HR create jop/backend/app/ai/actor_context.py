"""Authenticated actor context for request-level AI usage metering."""

from contextvars import ContextVar
from uuid import UUID

ai_actor_context: ContextVar[tuple[UUID, UUID] | None] = ContextVar(
    "ai_actor_context", default=None
)
