"""Org-scoped persistence for HERA assistant chat threads and messages.

Pure persistence + read-model helpers. It never calls the AI: the agent turn is
orchestrated by ``HERAAssistantWorkflow`` and the assistant reply is persisted
back here by the route that owns the transaction.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ChatMessage, ChatThread
from app.services.errors import NotFoundError, ValidationError

VALID_ROLES = frozenset({"user", "assistant"})
HISTORY_LIMIT = 10
HISTORY_CONTENT_CAP = 500


class ChatService:
    """Org-scoped chat thread + message persistence."""

    def create_thread(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        created_by_user_id: uuid.UUID | None = None,
        title: str | None = None,
    ) -> ChatThread:
        thread = ChatThread(
            organization_id=organization_id,
            created_by_user_id=created_by_user_id,
            title=_clean_title(title),
            status="active",
        )
        db.add(thread)
        db.flush()
        return thread

    def get_thread(
        self,
        db: Session,
        *,
        thread_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> ChatThread:
        thread = db.get(ChatThread, thread_id)
        if thread is None or thread.organization_id != organization_id:
            raise NotFoundError("ChatThread was not found.")
        return thread

    def list_threads(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
    ) -> list[ChatThread]:
        statement = (
            select(ChatThread)
            .where(ChatThread.organization_id == organization_id)
            .order_by(ChatThread.updated_at.desc())
        )
        return list(db.scalars(statement))

    def rename_thread(
        self,
        db: Session,
        *,
        thread_id: uuid.UUID,
        organization_id: uuid.UUID,
        title: str,
    ) -> ChatThread:
        thread = self.get_thread(db, thread_id=thread_id, organization_id=organization_id)
        cleaned = _clean_title(title)
        if cleaned is None:
            raise ValidationError("ChatThread title cannot be empty.")
        thread.title = cleaned
        thread.updated_at = datetime.now(UTC)
        db.flush()
        return thread

    def add_message(
        self,
        db: Session,
        *,
        thread_id: uuid.UUID,
        organization_id: uuid.UUID,
        role: str,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_results: list[dict[str, Any]] | None = None,
        workflow_run_id: uuid.UUID | None = None,
    ) -> ChatMessage:
        thread = self.get_thread(db, thread_id=thread_id, organization_id=organization_id)
        normalized_role = (role or "").strip().lower()
        if normalized_role not in VALID_ROLES:
            raise ValidationError("Chat message role must be 'user' or 'assistant'.")
        content = (content or "").strip()
        if not content:
            raise ValidationError("Chat message content cannot be empty.")
        max_pos = db.scalar(
            select(func.max(ChatMessage.position)).where(ChatMessage.chat_thread_id == thread.id)
        )
        position = (max_pos or 0) + 1
        message = ChatMessage(
            chat_thread_id=thread.id,
            position=position,
            role=normalized_role,
            content=content,
            tool_calls=tool_calls,
            tool_results=tool_results,
            workflow_run_id=workflow_run_id,
        )
        db.add(message)
        thread.updated_at = datetime.now(UTC)
        db.flush()
        return message

    def list_messages(
        self,
        db: Session,
        *,
        thread_id: uuid.UUID,
        organization_id: uuid.UUID,
        limit: int = 100,
    ) -> list[ChatMessage]:
        """Return the most recent ``limit`` messages, oldest first.

        Ordered by the monotonic ``position`` (created_at is transaction-stable
        in PostgreSQL, so it cannot reliably order messages written in the same
        transaction, e.g. a user turn + its assistant reply).
        """
        self.get_thread(db, thread_id=thread_id, organization_id=organization_id)
        statement = (
            select(ChatMessage)
            .where(ChatMessage.chat_thread_id == thread_id)
            .order_by(ChatMessage.position.desc())
            .limit(limit)
        )
        return list(reversed(list(db.scalars(statement))))

    def history_text(
        self,
        db: Session,
        *,
        thread_id: uuid.UUID,
        organization_id: uuid.UUID,
        limit: int = HISTORY_LIMIT,
    ) -> str:
        """Serialize a bounded conversation history for the AI context."""
        messages = self.list_messages(
            db, thread_id=thread_id, organization_id=organization_id, limit=limit
        )
        return json.dumps(
            [
                {"role": message.role, "content": message.content[:HISTORY_CONTENT_CAP]}
                for message in messages
            ],
            ensure_ascii=False,
            default=str,
        )


def _clean_title(title: str | None) -> str | None:
    if title is None:
        return None
    cleaned = " ".join(title.split())
    if not cleaned:
        return None
    return cleaned[:120]
