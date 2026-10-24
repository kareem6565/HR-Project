"""Tests for ChatService org-scoped thread and message persistence."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChatThread, Organization, User
from app.services.chat_service import ChatService
from app.services.errors import NotFoundError, ValidationError


def create_org_and_user(db_session: Session) -> tuple[Organization, User]:
    organization = Organization(name="HERA Chat Service Org")
    db_session.add(organization)
    db_session.flush()
    user = User(
        organization_id=organization.id,
        email="hera-chat@example.com",
        full_name="HERA Chat User",
    )
    db_session.add(user)
    db_session.flush()
    return organization, user


def test_create_thread_with_title(db_session: Session) -> None:
    organization, user = create_org_and_user(db_session)
    thread = ChatService().create_thread(
        db_session,
        organization_id=organization.id,
        created_by_user_id=user.id,
        title="  Welcome to HERA  ",
    )
    db_session.commit()

    assert thread.title == "Welcome to HERA"
    assert thread.status == "active"
    assert thread.organization_id == organization.id


def test_create_thread_cleans_long_title(db_session: Session) -> None:
    organization, _user = create_org_and_user(db_session)
    thread = ChatService().create_thread(
        db_session,
        organization_id=organization.id,
        title="x" * 300,
    )
    db_session.commit()
    assert len(thread.title) == 120


def test_add_message_and_bump_thread_updated_at(db_session: Session) -> None:
    organization, user = create_org_and_user(db_session)
    service = ChatService()
    thread = service.create_thread(
        db_session, organization_id=organization.id, created_by_user_id=user.id
    )
    db_session.commit()
    first_update = thread.updated_at

    message = service.add_message(
        db_session,
        thread_id=thread.id,
        organization_id=organization.id,
        role="user",
        content="How many applications?",
    )
    db_session.commit()

    assert message.role == "user"
    assert message.chat_thread_id == thread.id
    assert message.workflow_run_id is None
    assert thread.updated_at >= first_update


def test_add_assistant_message_with_tool_metadata(db_session: Session) -> None:
    organization, user = create_org_and_user(db_session)
    service = ChatService()
    thread = service.create_thread(
        db_session, organization_id=organization.id, created_by_user_id=user.id
    )
    db_session.commit()

    message = service.add_message(
        db_session,
        thread_id=thread.id,
        organization_id=organization.id,
        role="assistant",
        content="There are 3 applications.",
        tool_calls=[{"tool": "summarize_pipeline", "arguments": {}}],
        tool_results=[{"tool": "summarize_pipeline", "ok": True, "data": {"total": 3}}],
    )
    db_session.commit()

    assert message.role == "assistant"
    assert message.tool_calls == [{"tool": "summarize_pipeline", "arguments": {}}]
    assert isinstance(message.tool_results, list)
    assert message.position >= 1


def test_list_messages_returns_oldest_first(db_session: Session) -> None:
    organization, user = create_org_and_user(db_session)
    service = ChatService()
    thread = service.create_thread(
        db_session, organization_id=organization.id, created_by_user_id=user.id
    )
    db_session.commit()
    service.add_message(
        db_session,
        thread_id=thread.id,
        organization_id=organization.id,
        role="user",
        content="first",
    )
    service.add_message(
        db_session,
        thread_id=thread.id,
        organization_id=organization.id,
        role="assistant",
        content="second",
    )
    db_session.commit()

    messages = service.list_messages(
        db_session, thread_id=thread.id, organization_id=organization.id
    )
    assert [message.content for message in messages] == ["first", "second"]


def test_history_text_bounds_recent_turns(db_session: Session) -> None:
    organization, user = create_org_and_user(db_session)
    service = ChatService()
    thread = service.create_thread(
        db_session, organization_id=organization.id, created_by_user_id=user.id
    )
    db_session.commit()
    for index in range(15):
        service.add_message(
            db_session,
            thread_id=thread.id,
            organization_id=organization.id,
            role="user" if index % 2 == 0 else "assistant",
            content=f"turn-{index}",
        )
    db_session.commit()

    import json

    parsed = json.loads(
        service.history_text(db_session, thread_id=thread.id, organization_id=organization.id)
    )
    assert len(parsed) == 10
    assert parsed[-1]["content"] == "turn-14"


def test_cross_organization_thread_is_invisible(db_session: Session) -> None:
    organization, _user = create_org_and_user(db_session)
    other_organization = Organization(name="Other Chat Org")
    db_session.add(other_organization)
    db_session.flush()
    thread = ChatService().create_thread(
        db_session, organization_id=other_organization.id, title="private"
    )
    db_session.commit()

    with pytest.raises(NotFoundError, match="ChatThread was not found"):
        ChatService().get_thread(db_session, thread_id=thread.id, organization_id=organization.id)


def test_get_missing_thread_raises(db_session: Session) -> None:
    organization, _user = create_org_and_user(db_session)
    with pytest.raises(NotFoundError, match="ChatThread was not found"):
        ChatService().get_thread(
            db_session, thread_id=uuid.uuid4(), organization_id=organization.id
        )


def test_rename_thread_scoped(db_session: Session) -> None:
    organization, user = create_org_and_user(db_session)
    service = ChatService()
    thread = service.create_thread(
        db_session,
        organization_id=organization.id,
        created_by_user_id=user.id,
        title="old",
    )
    db_session.commit()
    renamed = service.rename_thread(
        db_session,
        thread_id=thread.id,
        organization_id=organization.id,
        title="  new title  ",
    )
    db_session.commit()
    assert renamed.title == "new title"


def test_rename_thread_rejects_blank(db_session: Session) -> None:
    organization, user = create_org_and_user(db_session)
    service = ChatService()
    thread = service.create_thread(
        db_session, organization_id=organization.id, created_by_user_id=user.id
    )
    db_session.commit()
    with pytest.raises(ValidationError, match="cannot be empty"):
        service.rename_thread(
            db_session,
            thread_id=thread.id,
            organization_id=organization.id,
            title="   ",
        )


def test_invalid_role_rejected(db_session: Session) -> None:
    organization, user = create_org_and_user(db_session)
    service = ChatService()
    thread = service.create_thread(
        db_session, organization_id=organization.id, created_by_user_id=user.id
    )
    db_session.commit()
    with pytest.raises(ValidationError, match="role"):
        service.add_message(
            db_session,
            thread_id=thread.id,
            organization_id=organization.id,
            role="system",
            content="nope",
        )


def test_empty_content_rejected(db_session: Session) -> None:
    organization, user = create_org_and_user(db_session)
    service = ChatService()
    thread = service.create_thread(
        db_session, organization_id=organization.id, created_by_user_id=user.id
    )
    db_session.commit()
    with pytest.raises(ValidationError, match="cannot be empty"):
        service.add_message(
            db_session,
            thread_id=thread.id,
            organization_id=organization.id,
            role="user",
            content="   ",
        )


def test_list_threads_newest_first(db_session: Session) -> None:
    organization, user = create_org_and_user(db_session)
    service = ChatService()
    first_thread = service.create_thread(
        db_session, organization_id=organization.id, created_by_user_id=user.id
    )
    second_thread = service.create_thread(
        db_session, organization_id=organization.id, created_by_user_id=user.id
    )
    db_session.commit()
    threads = service.list_threads(db_session, organization_id=organization.id)
    assert [thread.id for thread in threads] == [second_thread.id, first_thread.id]
    assert len(threads) == 2


def test_threads_are_scoped_by_organization(db_session: Session) -> None:
    organization, _user = create_org_and_user(db_session)
    other_organization = Organization(name="Second Chat Org")
    db_session.add(other_organization)
    db_session.flush()
    ChatService().create_thread(db_session, organization_id=other_organization.id)
    db_session.commit()

    threads = ChatService().list_threads(db_session, organization_id=organization.id)
    assert threads == []
    assert db_session.scalar(select(ChatThread)) is not None
