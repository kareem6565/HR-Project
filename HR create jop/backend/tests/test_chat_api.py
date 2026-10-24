"""API integration tests for the HERA assistant chat endpoints."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import app
from app.models import Candidate, Job, JobApplication, Organization, Resume, User


@pytest.fixture()
def client(db_session: Session) -> Generator[httpx.Client, None, None]:
    connection = db_session.connection()
    db_session.bind = connection

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.pop(get_db, None)


def auth_headers(org_id: str, user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id, "X-Organization-Id": org_id}


def seed_org_user(db_session: Session) -> tuple[Organization, User]:
    organization = Organization(name="HERA Chat API Org")
    db_session.add(organization)
    db_session.flush()
    user = User(
        organization_id=organization.id,
        email="hera-chat-api@example.com",
        full_name="HERA Chat API User",
    )
    db_session.add(user)
    db_session.commit()
    return organization, user


def seed_application(
    db_session: Session,
) -> tuple[Organization, User, JobApplication]:
    organization, user = seed_org_user(db_session)
    candidate = Candidate(
        organization_id=organization.id,
        full_name="Sara Seed",
        email="sara.seed@example.com",
    )
    db_session.add(candidate)
    db_session.flush()
    job = Job(
        organization_id=organization.id,
        created_by_user_id=user.id,
        title="Backend Engineer",
        status="active",
    )
    resume = Resume(candidate_id=candidate.id, file_uri="local://resumes/hera.pdf")
    db_session.add_all([job, resume])
    db_session.flush()
    application = JobApplication(
        organization_id=organization.id,
        job_id=job.id,
        candidate_id=candidate.id,
        resume_id=resume.id,
    )
    db_session.add(application)
    db_session.commit()
    return organization, user, application


def create_thread(client: httpx.Client, headers: dict[str, str], title: str | None = None) -> dict:
    body = {"title": title} if title is not None else {}
    resp = client.post("/api/v1/chat/threads", headers=headers, json=body)
    assert resp.status_code == 201
    return resp.json()


def test_create_list_get_and_rename_thread(client: httpx.Client, db_session: Session) -> None:
    organization, user = seed_org_user(db_session)
    headers = auth_headers(str(organization.id), str(user.id))

    created = create_thread(client, headers, title="Initial")
    assert created["title"] == "Initial"
    assert created["status"] == "active"

    listed = client.get("/api/v1/chat/threads", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["threads"][0]["id"] == created["id"]

    detail = client.get(f"/api/v1/chat/threads/{created['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["thread"]["id"] == created["id"]
    assert detail.json()["messages"] == []

    renamed = client.patch(
        f"/api/v1/chat/threads/{created['id']}",
        headers=headers,
        json={"title": "  Renamed  "},
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Renamed"


def test_send_pipeline_question_returns_grounded_reply(
    client: httpx.Client, db_session: Session
) -> None:
    organization, user = seed_org_user(db_session)
    headers = auth_headers(str(organization.id), str(user.id))
    thread = create_thread(client, headers)

    resp = client.post(
        f"/api/v1/chat/threads/{thread['id']}/messages",
        headers=headers,
        json={"content": "How many applications are in the pipeline?"},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["message"]["role"] == "assistant"
    assert body["message"]["content"]
    assert body["message"]["tool_calls"][0]["tool"] == "summarize_pipeline"
    assert body["message"]["tool_results"][0]["ok"] is True
    assert body["message"]["workflow_run_id"]
    assert body["thread"]["title"] == "How many applications are in the pipeline?"


def test_send_question_touches_real_rows_not_fabricated(
    client: httpx.Client, db_session: Session
) -> None:
    organization, user = seed_org_user(db_session)
    headers = auth_headers(str(organization.id), str(user.id))
    thread = create_thread(client, headers)

    resp = client.post(
        f"/api/v1/chat/threads/{thread['id']}/messages",
        headers=headers,
        json={"content": "How many applications are in the pipeline?"},
    )
    body = resp.json()
    assert "Sara" not in body["message"]["content"]


def test_reference_seeded_application_returns_details_and_link(
    client: httpx.Client, db_session: Session
) -> None:
    organization, user, application = seed_application(db_session)
    headers = auth_headers(str(organization.id), str(user.id))
    thread = create_thread(client, headers)

    resp = client.post(
        f"/api/v1/chat/threads/{thread['id']}/messages",
        headers=headers,
        json={"content": f"Show me details for application {application.id}, please."},
    )
    assert resp.status_code == 200
    body = resp.json()

    assistant = body["message"]
    assert assistant["tool_calls"][0]["tool"] == "get_application_details"
    assert assistant["tool_results"][0]["ok"] is True
    assert "Sara Seed" in assistant["content"]
    assert "Backend Engineer" in assistant["content"]


def test_fake_application_uuid_fails_gracefully_in_reply(
    client: httpx.Client, db_session: Session
) -> None:
    organization, user = seed_org_user(db_session)
    headers = auth_headers(str(organization.id), str(user.id))
    thread = create_thread(client, headers)

    resp = client.post(
        f"/api/v1/chat/threads/{thread['id']}/messages",
        headers=headers,
        json={"content": f"What about application {uuid.uuid4()}?"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"]["tool_calls"][0]["tool"] == "get_application_details"
    assert body["message"]["tool_results"][0]["ok"] is False
    assert body["message"]["content"]


def test_greeting_does_not_run_tools(client: httpx.Client, db_session: Session) -> None:
    organization, user = seed_org_user(db_session)
    headers = auth_headers(str(organization.id), str(user.id))
    thread = create_thread(client, headers)

    resp = client.post(
        f"/api/v1/chat/threads/{thread['id']}/messages",
        headers=headers,
        json={"content": "hello there"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"]["tool_calls"] is None
    assert "HERA" in body["message"]["content"]


def test_conversation_history_is_persisted_in_both_roles(
    client: httpx.Client, db_session: Session
) -> None:
    organization, user = seed_org_user(db_session)
    headers = auth_headers(str(organization.id), str(user.id))
    thread = create_thread(client, headers)

    for content in ("hello there", "How many applications are in the pipeline?"):
        resp = client.post(
            f"/api/v1/chat/threads/{thread['id']}/messages",
            headers=headers,
            json={"content": content},
        )
        assert resp.status_code == 200

    detail = client.get(f"/api/v1/chat/threads/{thread['id']}", headers=headers)
    messages = detail.json()["messages"]
    roles = [message["role"] for message in messages]
    assert roles == ["user", "assistant", "user", "assistant"]
    assert messages[0]["content"] == "hello there"


def test_cross_organization_thread_returns_422(client: httpx.Client, db_session: Session) -> None:
    organization, user = seed_org_user(db_session)
    headers = auth_headers(str(organization.id), str(user.id))
    thread = create_thread(client, headers)

    other_organization, other_user = seed_org_user(db_session)
    other_headers = auth_headers(str(other_organization.id), str(other_user.id))

    detail = client.get(f"/api/v1/chat/threads/{thread['id']}", headers=other_headers)
    assert detail.status_code in (404, 422)


def test_empty_message_rejected(client: httpx.Client, db_session: Session) -> None:
    organization, user = seed_org_user(db_session)
    headers = auth_headers(str(organization.id), str(user.id))
    thread = create_thread(client, headers)

    resp = client.post(
        f"/api/v1/chat/threads/{thread['id']}/messages",
        headers=headers,
        json={"content": ""},
    )
    assert resp.status_code == 422


def test_chat_requires_identity_headers(client: httpx.Client, db_session: Session) -> None:
    resp = client.post("/api/v1/chat/threads", json={"title": "x"})
    assert resp.status_code in (401, 422)
