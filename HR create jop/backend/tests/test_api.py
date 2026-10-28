"""API integration tests for Phase 4.3 HTTP endpoints."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.core.database import get_db
from app.main import app


@pytest.fixture()
def client(db_session: Session) -> Generator[httpx.Client, None, None]:
    """Provide a synchronous test client sharing the test db_session.

    The ``get_db`` dependency is overridden so endpoints share the same
    session (and connection) as the test. Nested transactions let the test
    read data the endpoint writes, then the outer transaction is rolled back
    to clean up after the test.
    """
    connection = db_session.connection()
    db_session.bind = connection

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(autouse=True)
def _isolated_storage_root(tmp_path) -> None:
    """Point resume uploads at a temporary directory so tests don't write to
    the real ``./storage`` directory under the backend."""
    from app.core.config import settings

    original = settings.storage_root_dir
    settings.storage_root_dir = str(tmp_path / "storage")
    yield
    settings.storage_root_dir = original


def auth_headers(org_id: str, user_id: str) -> dict[str, str]:
    """Return standard MVP auth headers."""
    return {"X-User-Id": user_id, "X-Organization-Id": org_id}


def create_org(client: httpx.Client, name: str = "Test Org") -> dict:
    """Create a bootstrap organization via internal service."""
    from app.services.organization_service import OrganizationService

    db = next(client.app.dependency_overrides[get_db]())
    org = OrganizationService().create(db, name=name)
    return {"id": str(org.id), "name": org.name, "status": org.status}


def create_user(
    client: httpx.Client,
    org_id: str,
    email: str = "hr@test.com",
    role: str = "recruiter",
) -> dict:
    """Create a bootstrap user in an organization via internal service."""
    from app.services.user_service import UserService

    db = next(client.app.dependency_overrides[get_db]())
    user = UserService().create(
        db,
        organization_id=uuid.UUID(org_id),
        email=email,
        full_name="HR User",
        role=role,
    )
    return {
        "id": str(user.id),
        "organization_id": str(user.organization_id),
        "email": user.email,
        "full_name": user.full_name,
        "status": user.status,
    }


def bootstrap(client: httpx.Client) -> tuple[dict, dict]:
    """Create an org and user via internal services, return both as dicts."""
    org = create_org(client)
    user = create_user(client, org["id"])
    return org, user


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_check(self, client: httpx.Client) -> None:
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestAIActivityAuthorization:
    def test_ai_activity_is_admin_only_for_reads_and_retry(self, client: httpx.Client) -> None:
        org = create_org(client)
        recruiter = create_user(client, org["id"], "recruiter@test.com")
        admin = create_user(client, org["id"], "admin@test.com", role="admin")
        recruiter_headers = auth_headers(org["id"], recruiter["id"])
        admin_headers = auth_headers(org["id"], admin["id"])

        assert client.get("/api/v1/ai-activity/runs", headers=recruiter_headers).status_code == 403
        assert client.get("/api/v1/ai-activity/stats", headers=recruiter_headers).status_code == 403
        assert (
            client.post(
                f"/api/v1/ai-activity/runs/{uuid.uuid4()}/retry",
                headers=recruiter_headers,
            ).status_code
            == 403
        )

        assert client.get("/api/v1/ai-activity/runs", headers=admin_headers).status_code == 200
        assert client.get("/api/v1/ai-activity/stats", headers=admin_headers).status_code == 200


# ---------------------------------------------------------------------------
# Provisioning Containment (Prompt 1)
# ---------------------------------------------------------------------------


class TestBootstrap:
    def test_create_organization_endpoint_is_closed(self, client: httpx.Client) -> None:
        resp = client.post("/api/v1/organizations", json={"name": "Acme"})
        assert resp.status_code == 404

    def test_create_user_endpoint_is_closed(self, client: httpx.Client) -> None:
        fake_id = str(uuid.uuid4())
        resp = client.post(
            f"/api/v1/organizations/{fake_id}/users",
            json={"email": "u@test.com", "full_name": "Test User"},
        )
        assert resp.status_code in (401, 404, 422)


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------


class TestHeaders:
    def test_missing_headers_returns_422(self, client: httpx.Client) -> None:
        resp = client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000")
        assert resp.status_code in (401, 422)

    def test_invalid_uuid_returns_422(self, client: httpx.Client) -> None:
        resp = client.get(
            "/api/v1/jobs/00000000-0000-0000-0000-000000000000",
            headers={"X-User-Id": "not-a-uuid", "X-Organization-Id": "also-not"},
        )
        assert resp.status_code == 422

    def test_nonexistent_user_returns_404(self, client: httpx.Client) -> None:
        org = create_org(client)
        fake_user = str(uuid.uuid4())
        resp = client.get(
            "/api/v1/jobs/00000000-0000-0000-0000-000000000000",
            headers=auth_headers(org["id"], fake_user),
        )
        assert resp.status_code == 404

    def test_org_mismatch_returns_403(self, client: httpx.Client) -> None:
        org1 = create_org(client, name="Org1")
        org2 = create_org(client, name="Org2")
        user1 = create_user(client, org1["id"], "u1@test.com")
        resp = client.get(
            "/api/v1/jobs/00000000-0000-0000-0000-000000000000",
            headers=auth_headers(org2["id"], user1["id"]),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


class TestJobs:
    def test_create_and_get_job(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        resp = client.post("/api/v1/jobs", json={"title": "Engineer"}, headers=h)
        assert resp.status_code == 201
        job = resp.json()
        assert job["title"] == "Engineer"
        assert job["organization_id"] == org["id"]
        assert job["status"] == "draft"

        resp = client.get(f"/api/v1/jobs/{job['id']}", headers=h)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Engineer"

    def test_list_jobs(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        client.post("/api/v1/jobs", json={"title": "Job A"}, headers=h)
        client.post("/api/v1/jobs", json={"title": "Job B"}, headers=h)

        resp = client.get("/api/v1/jobs", headers=h)
        assert resp.status_code == 200
        titles = [j["title"] for j in resp.json()]
        assert {"Job A", "Job B"}.issubset(titles)

        other_org, other_user = bootstrap(client)
        other_h = auth_headers(other_org["id"], other_user["id"])
        resp = client.get("/api/v1/jobs", headers=other_h)
        assert resp.status_code == 200
        assert all(j["title"] not in ("Job A", "Job B") for j in resp.json())

    def test_delete_job(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        resp = client.post("/api/v1/jobs", json={"title": "To Delete"}, headers=h)
        job_id = resp.json()["id"]

        resp = client.delete(f"/api/v1/jobs/{job_id}", headers=h)
        assert resp.status_code == 204

        resp = client.get(f"/api/v1/jobs/{job_id}", headers=h)
        assert resp.status_code == 404

        resp = client.get("/api/v1/jobs", headers=h)
        assert resp.status_code == 200
        assert all(j["id"] != job_id for j in resp.json())

    def test_delete_job_in_use_rejected(self, client: httpx.Client, db_session: Session) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        job = client.post("/api/v1/jobs", json={"title": "In Use"}, headers=h).json()
        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        candidate = models.Candidate(
            organization_id=organization.id, full_name="Candi", email="candi@test.com"
        )
        db_session.add(candidate)
        db_session.flush()
        resume = models.Resume(candidate_id=candidate.id, file_uri="local://r.pdf")
        db_session.add(resume)
        db_session.flush()
        application = models.JobApplication(
            organization_id=organization.id,
            job_id=uuid.UUID(job["id"]),
            candidate_id=candidate.id,
            resume_id=resume.id,
        )
        db_session.add(application)
        db_session.flush()

        resp = client.delete(f"/api/v1/jobs/{job['id']}", headers=h)
        assert resp.status_code == 409

        resp = client.get(f"/api/v1/jobs/{job['id']}", headers=h)
        assert resp.status_code == 200

    def test_update_job(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        resp = client.post("/api/v1/jobs", json={"title": "Old"}, headers=h)
        job = resp.json()

        resp = client.patch(f"/api/v1/jobs/{job['id']}", json={"title": "New"}, headers=h)
        assert resp.status_code == 200
        assert resp.json()["title"] == "New"

    def test_job_not_found(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        fake = str(uuid.uuid4())
        resp = client.get(f"/api/v1/jobs/{fake}", headers=h)
        assert resp.status_code == 404

    def test_job_cross_org_isolation(self, client: httpx.Client) -> None:
        org1, user1 = bootstrap(client)
        org2, user2 = bootstrap(client)
        h1 = auth_headers(org1["id"], user1["id"])
        h2 = auth_headers(org2["id"], user2["id"])

        resp = client.post("/api/v1/jobs", json={"title": "J1"}, headers=h1)
        job = resp.json()

        resp = client.get(f"/api/v1/jobs/{job['id']}", headers=h2)
        assert resp.status_code in (404, 422)


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------


class TestCandidates:
    def test_create_and_get_candidate(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        resp = client.post(
            "/api/v1/candidates",
            json={"full_name": "Alice"},
            headers=h,
        )
        assert resp.status_code == 201
        cand = resp.json()
        assert cand["full_name"] == "Alice"

        resp = client.get(f"/api/v1/candidates/{cand['id']}", headers=h)
        assert resp.status_code == 200

    def test_archive_candidate_preserves_record_and_is_idempotent(
        self, client: httpx.Client
    ) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        cand = client.post(
            "/api/v1/candidates", json={"full_name": "Archive Me"}, headers=h
        ).json()
        from app.services.resume_service import ResumeService

        db = next(client.app.dependency_overrides[get_db]())
        ResumeService().create(
            db,
            candidate_id=uuid.UUID(cand["id"]),
            organization_id=uuid.UUID(org["id"]),
            file_uri="resumes/archive-me.pdf",
            original_filename="archive-me.pdf",
        )

        response = client.post(f"/api/v1/candidates/{cand['id']}/archive", headers=h)

        assert response.status_code == 200
        assert response.json()["id"] == cand["id"]
        assert response.json()["status"] == "archived"
        assert response.json()["full_name"] == "Archive Me"
        assert response.json()["updated_at"]

        archived_list = client.get("/api/v1/candidates", params={"status": "archived"}, headers=h)
        active_list = client.get("/api/v1/candidates", params={"status": "active"}, headers=h)
        assert [row["id"] for row in archived_list.json()] == [cand["id"]]
        assert active_list.json() == []
        resumes = client.get(f"/api/v1/candidates/{cand['id']}/resumes", headers=h)
        assert resumes.status_code == 200
        assert [resume["original_filename"] for resume in resumes.json()] == ["archive-me.pdf"]

        again = client.post(f"/api/v1/candidates/{cand['id']}/archive", headers=h)
        assert again.status_code == 200
        assert again.json()["status"] == "archived"

    def test_archive_candidate_is_organization_scoped(self, client: httpx.Client) -> None:
        org1, user1 = bootstrap(client)
        org2, user2 = bootstrap(client)
        h1 = auth_headers(org1["id"], user1["id"])
        h2 = auth_headers(org2["id"], user2["id"])
        cand = client.post(
            "/api/v1/candidates", json={"full_name": "Tenant Candidate"}, headers=h1
        ).json()

        response = client.post(f"/api/v1/candidates/{cand['id']}/archive", headers=h2)

        assert response.status_code == 404
        still_active = client.get(
            f"/api/v1/candidates/{cand['id']}", headers=h1
        )
        assert still_active.status_code == 200
        assert still_active.json()["status"] == "active"

    def test_archive_candidate_not_found(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        response = client.post(f"/api/v1/candidates/{uuid.uuid4()}/archive", headers=h)

        assert response.status_code == 404

    def test_candidate_cross_org_isolation(self, client: httpx.Client) -> None:
        org1, user1 = bootstrap(client)
        org2, user2 = bootstrap(client)
        h1 = auth_headers(org1["id"], user1["id"])
        h2 = auth_headers(org2["id"], user2["id"])

        resp = client.post("/api/v1/candidates", json={"full_name": "Bob"}, headers=h1)
        cand = resp.json()

        resp = client.get(f"/api/v1/candidates/{cand['id']}", headers=h2)
        assert resp.status_code in (404, 422)

    def test_list_candidates_returns_only_org_candidates(self, client: httpx.Client) -> None:
        org1, user1 = bootstrap(client)
        org2, user2 = bootstrap(client)
        h1 = auth_headers(org1["id"], user1["id"])
        h2 = auth_headers(org2["id"], user2["id"])

        for name in ("Alice", "Bob"):
            resp = client.post("/api/v1/candidates", json={"full_name": name}, headers=h1)
            assert resp.status_code == 201
        client.post("/api/v1/candidates", json={"full_name": "Carol"}, headers=h2)

        resp = client.get("/api/v1/candidates", headers=h1)
        assert resp.status_code == 200
        names = {c["full_name"] for c in resp.json()}
        assert names == {"Alice", "Bob"}

    def test_list_candidates_search(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        client.post(
            "/api/v1/candidates",
            json={"full_name": "Alice Wong", "email": "alice@test.com"},
            headers=h,
        )
        client.post(
            "/api/v1/candidates",
            json={"full_name": "Bob Smith", "email": "bob@test.com"},
            headers=h,
        )

        resp = client.get("/api/v1/candidates", params={"search": "alice"}, headers=h)
        assert resp.status_code == 200
        assert [c["full_name"] for c in resp.json()] == ["Alice Wong"]

        resp = client.get("/api/v1/candidates", params={"search": "bob@test.com"}, headers=h)
        assert resp.status_code == 200
        assert [c["full_name"] for c in resp.json()] == ["Bob Smith"]

        resp = client.get("/api/v1/candidates", params={"search": "zzz"}, headers=h)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_candidate_resumes(self, client: httpx.Client) -> None:
        from app.services.resume_service import ResumeService

        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        cand = client.post("/api/v1/candidates", json={"full_name": "Fay"}, headers=h).json()
        db = next(client.app.dependency_overrides[get_db]())
        ResumeService().create(
            db,
            candidate_id=uuid.UUID(cand["id"]),
            organization_id=uuid.UUID(org["id"]),
            file_uri="resumes/one.pdf",
            original_filename="one.pdf",
        )
        ResumeService().create(
            db,
            candidate_id=uuid.UUID(cand["id"]),
            organization_id=uuid.UUID(org["id"]),
            file_uri="resumes/two.pdf",
            original_filename="two.pdf",
        )

        resp = client.get(f"/api/v1/candidates/{cand['id']}/resumes", headers=h)
        assert resp.status_code == 200
        names = {r["original_filename"] for r in resp.json()}
        assert names == {"one.pdf", "two.pdf"}

    def test_list_candidate_resumes_cross_org(self, client: httpx.Client) -> None:
        from app.services.resume_service import ResumeService

        org1, user1 = bootstrap(client)
        org2, user2 = bootstrap(client)
        h1 = auth_headers(org1["id"], user1["id"])
        h2 = auth_headers(org2["id"], user2["id"])

        cand = client.post("/api/v1/candidates", json={"full_name": "Gia"}, headers=h1).json()
        db = next(client.app.dependency_overrides[get_db]())
        ResumeService().create(
            db,
            candidate_id=uuid.UUID(cand["id"]),
            organization_id=uuid.UUID(org1["id"]),
            file_uri="resumes/one.pdf",
            original_filename="one.pdf",
        )

        resp = client.get(f"/api/v1/candidates/{cand['id']}/resumes", headers=h2)
        assert resp.status_code in (404, 422)

    def test_list_candidate_resumes_not_found(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        resp = client.get(f"/api/v1/candidates/{uuid.uuid4()}/resumes", headers=h)
        assert resp.status_code == 404

    def test_list_candidates_invalid_status_filter(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        resp = client.get("/api/v1/candidates", params={"status": "bogus"}, headers=h)
        assert resp.status_code == 422

    def test_update_candidate(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        resp = client.post(
            "/api/v1/candidates",
            json={"full_name": "Dana", "email": "dana@test.com"},
            headers=h,
        )
        cand = resp.json()

        resp = client.patch(
            f"/api/v1/candidates/{cand['id']}",
            json={"phone": "555-0100"},
            headers=h,
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["email"] == "dana@test.com"
        assert updated["phone"] == "555-0100"

        resp = client.patch(
            f"/api/v1/candidates/{cand['id']}",
            json={"email": "new@test.com"},
            headers=h,
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "new@test.com"

    def test_update_candidate_not_found(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        resp = client.patch(
            f"/api/v1/candidates/{uuid.uuid4()}",
            json={"email": "x@test.com"},
            headers=h,
        )
        assert resp.status_code == 404

    def test_update_candidate_cross_org_isolation(self, client: httpx.Client) -> None:
        org1, user1 = bootstrap(client)
        org2, user2 = bootstrap(client)
        h1 = auth_headers(org1["id"], user1["id"])
        h2 = auth_headers(org2["id"], user2["id"])

        resp = client.post("/api/v1/candidates", json={"full_name": "Eve"}, headers=h1)
        cand = resp.json()

        resp = client.patch(
            f"/api/v1/candidates/{cand['id']}",
            json={"email": "eve@other.com"},
            headers=h2,
        )
        assert resp.status_code in (404, 422)


# ---------------------------------------------------------------------------
# Resumes
# ---------------------------------------------------------------------------


class TestResumes:
    def test_create_and_get_resume(self, client: httpx.Client) -> None:
        from app.services.resume_service import ResumeService

        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        resp = client.post(
            "/api/v1/candidates",
            json={"full_name": "Cand"},
            headers=h,
        )
        cand = resp.json()

        # Reject public creation with client-controlled raw file_uri
        resp = client.post(
            f"/api/v1/candidates/{cand['id']}/resumes",
            json={"file_uri": "local://test.pdf"},
            headers=h,
        )
        assert resp.status_code in (404, 405)

        db = next(client.app.dependency_overrides[get_db]())
        resume = ResumeService().create(
            db,
            candidate_id=uuid.UUID(cand["id"]),
            organization_id=uuid.UUID(org["id"]),
            file_uri="resumes/test.pdf",
            original_filename="test.pdf",
        )

        resp = client.get(f"/api/v1/resumes/{resume.id}", headers=h)
        assert resp.status_code == 200
        assert resp.json()["file_uri"] == "resumes/test.pdf"


# ---------------------------------------------------------------------------
# Resume Upload (Phase 4.4)
# ---------------------------------------------------------------------------


class TestResumeUpload:
    def _upload(
        self,
        client: httpx.Client,
        h: dict,
        cand_id: str,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> httpx.Response:
        return client.post(
            f"/api/v1/candidates/{cand_id}/resumes/upload",
            headers=h,
            files={
                "file": (
                    filename,
                    content,
                    content_type,
                )
            },
        )

    def test_upload_pdf(self, client: httpx.Client) -> None:
        from tests.resume_upload_fixtures import make_pdf_bytes

        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        cand = client.post("/api/v1/candidates", json={"full_name": "C"}, headers=h).json()

        resp = self._upload(
            client,
            h,
            cand["id"],
            "resume.pdf",
            make_pdf_bytes(),
            "application/pdf",
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "text_extracted"
        assert data["original_filename"] == "resume.pdf"
        assert data["content_type"] == "application/pdf"
        assert "extracted_text" not in data

    def test_upload_docx(self, client: httpx.Client) -> None:
        from tests.resume_upload_fixtures import make_docx_bytes

        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        cand = client.post("/api/v1/candidates", json={"full_name": "C"}, headers=h).json()

        resp = self._upload(
            client,
            h,
            cand["id"],
            "resume.docx",
            make_docx_bytes(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "text_extracted"
        assert "extracted_text" not in resp.json()

    def test_upload_rejects_wrong_extension(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        cand = client.post("/api/v1/candidates", json={"full_name": "C"}, headers=h).json()

        resp = self._upload(client, h, cand["id"], "resume.txt", b"hello", "text/plain")
        assert resp.status_code == 422

    def test_upload_rejects_content_type_mismatch(self, client: httpx.Client) -> None:
        from tests.resume_upload_fixtures import make_pdf_bytes

        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        cand = client.post("/api/v1/candidates", json={"full_name": "C"}, headers=h).json()

        resp = self._upload(
            client,
            h,
            cand["id"],
            "resume.pdf",
            make_pdf_bytes(),
            "text/plain",
        )
        assert resp.status_code == 422

    def test_upload_rejects_empty_text(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        cand = client.post("/api/v1/candidates", json={"full_name": "C"}, headers=h).json()

        resp = self._upload(
            client,
            h,
            cand["id"],
            "resume.pdf",
            b"%PDF-1.4\nnot a real pdf",
            "application/pdf",
        )
        assert resp.status_code == 422

    def test_upload_cross_org_isolation(self, client: httpx.Client) -> None:
        from tests.resume_upload_fixtures import make_pdf_bytes

        org1, user1 = bootstrap(client)
        org2, user2 = bootstrap(client)
        h1 = auth_headers(org1["id"], user1["id"])
        h2 = auth_headers(org2["id"], user2["id"])

        cand = client.post("/api/v1/candidates", json={"full_name": "C"}, headers=h1).json()

        resp = self._upload(
            client,
            h2,
            cand["id"],
            "resume.pdf",
            make_pdf_bytes(),
            "application/pdf",
        )
        assert resp.status_code in (404, 422)


# ---------------------------------------------------------------------------
# Job Applications
# ---------------------------------------------------------------------------


class TestJobApplications:
    def _setup_entities(self, client: httpx.Client, h: dict) -> tuple[dict, dict, dict]:
        resp = client.post("/api/v1/jobs", json={"title": "J"}, headers=h)
        job = resp.json()
        resp = client.post("/api/v1/candidates", json={"full_name": "C"}, headers=h)
        cand = resp.json()
        db = next(client.app.dependency_overrides[get_db]())
        from app.services.resume_service import ResumeService

        r = ResumeService().create(
            db,
            candidate_id=uuid.UUID(cand["id"]),
            organization_id=uuid.UUID(h["X-Organization-Id"]),
            file_uri="resumes/r.pdf",
            original_filename="r.pdf",
        )
        resume = {"id": str(r.id), "file_uri": r.file_uri}
        return job, cand, resume

    def test_create_and_get_application(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        job, cand, resume = self._setup_entities(client, h)

        resp = client.post(
            "/api/v1/job-applications",
            json={
                "job_id": job["id"],
                "candidate_id": cand["id"],
                "resume_id": resume["id"],
            },
            headers=h,
        )
        assert resp.status_code == 201
        app_data = resp.json()
        assert app_data["job_id"] == job["id"]

        resp = client.get(f"/api/v1/job-applications/{app_data['id']}", headers=h)
        assert resp.status_code == 200

    def test_list_applications_by_job(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        job, cand, resume = self._setup_entities(client, h)

        client.post(
            "/api/v1/job-applications",
            json={
                "job_id": job["id"],
                "candidate_id": cand["id"],
                "resume_id": resume["id"],
            },
            headers=h,
        )

        resp = client.get(f"/api/v1/jobs/{job['id']}/applications", headers=h)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


# ---------------------------------------------------------------------------
# Job Profiles
# ---------------------------------------------------------------------------


class TestJobProfiles:
    def test_create_list_get_profile(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        resp = client.post("/api/v1/jobs", json={"title": "J"}, headers=h)
        job = resp.json()

        resp = client.post(
            f"/api/v1/jobs/{job['id']}/profiles",
            json={
                "status": "draft",
                "source": "hr_created",
                "profile_data": {"title": "J", "requirements": []},
            },
            headers=h,
        )
        assert resp.status_code == 201
        profile = resp.json()
        assert profile["version_number"] == 1

        resp = client.get(f"/api/v1/job-profiles/{profile['id']}", headers=h)
        assert resp.status_code == 200

        resp = client.get(f"/api/v1/jobs/{job['id']}/profiles", headers=h)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_approve_profile(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        resp = client.post("/api/v1/jobs", json={"title": "J"}, headers=h)
        job = resp.json()

        resp = client.post(
            f"/api/v1/jobs/{job['id']}/profiles",
            json={
                "status": "draft",
                "source": "hr_created",
                "profile_data": {"title": "J"},
            },
            headers=h,
        )
        profile = resp.json()

        resp = client.post(f"/api/v1/job-profiles/{profile['id']}/approve", headers=h)
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"


# ---------------------------------------------------------------------------
# Candidate Profiles
# ---------------------------------------------------------------------------


class TestCandidateProfiles:
    def test_create_list_get_profile(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        resp = client.post("/api/v1/candidates", json={"full_name": "C"}, headers=h)
        cand = resp.json()
        db = next(client.app.dependency_overrides[get_db]())
        from app.services.resume_service import ResumeService

        r = ResumeService().create(
            db,
            candidate_id=uuid.UUID(cand["id"]),
            organization_id=uuid.UUID(org["id"]),
            file_uri="resumes/r.pdf",
            original_filename="r.pdf",
        )
        resume = {"id": str(r.id), "file_uri": r.file_uri}

        resp = client.post(
            f"/api/v1/resumes/{resume['id']}/profiles",
            json={
                "status": "extracted",
                "source": "ai_extracted",
                "profile_data": {"skills": ["Python"]},
            },
            headers=h,
        )
        assert resp.status_code == 201
        profile = resp.json()
        assert profile["version_number"] == 1

        resp = client.get(f"/api/v1/candidate-profiles/{profile['id']}", headers=h)
        assert resp.status_code == 200

        resp = client.get(f"/api/v1/resumes/{resume['id']}/profiles", headers=h)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


# ---------------------------------------------------------------------------
# Candidate Profile Extraction (Phase 4.4 optional resume_text path)
# ---------------------------------------------------------------------------


class TestCandidateProfileExtraction:
    def _upload_pdf(self, client: httpx.Client, h: dict, cand_id: str) -> dict:
        from tests.resume_upload_fixtures import make_pdf_bytes

        resp = client.post(
            f"/api/v1/candidates/{cand_id}/resumes/upload",
            headers=h,
            files={
                "file": (
                    "resume.pdf",
                    make_pdf_bytes(),
                    "application/pdf",
                )
            },
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "text_extracted"
        return resp.json()

    def test_extract_using_stored_text_when_resume_text_omitted(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        cand = client.post("/api/v1/candidates", json={"full_name": "C"}, headers=h).json()
        resume = self._upload_pdf(client, h, cand["id"])

        resp = client.post(
            f"/api/v1/resumes/{resume['id']}/extract-profile",
            json={},
            headers=h,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["profile_id"] is not None
        assert data["workflow_run_id"] is not None
        assert data["version_number"] == 1

    def test_extract_with_explicit_resume_text(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        cand = client.post("/api/v1/candidates", json={"full_name": "C"}, headers=h).json()

        # Create a resume with no text via internal service, then pass resume_text explicitly.
        db = next(client.app.dependency_overrides[get_db]())
        from app.services.resume_service import ResumeService

        r = ResumeService().create(
            db,
            candidate_id=uuid.UUID(cand["id"]),
            organization_id=uuid.UUID(org["id"]),
            file_uri="resumes/r.pdf",
            original_filename="r.pdf",
        )
        resume = {"id": str(r.id), "file_uri": r.file_uri}

        resp = client.post(
            f"/api/v1/resumes/{resume['id']}/extract-profile",
            json={"resume_text": "Ada loves Python and mathematics."},
            headers=h,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["version_number"] == 1

    def test_extract_without_text_fails_when_no_stored_text(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        cand = client.post("/api/v1/candidates", json={"full_name": "C"}, headers=h).json()
        db = next(client.app.dependency_overrides[get_db]())
        from app.services.resume_service import ResumeService

        r = ResumeService().create(
            db,
            candidate_id=uuid.UUID(cand["id"]),
            organization_id=uuid.UUID(org["id"]),
            file_uri="resumes/r.pdf",
            original_filename="r.pdf",
        )
        resume = {"id": str(r.id), "file_uri": r.file_uri}

        resp = client.post(
            f"/api/v1/resumes/{resume['id']}/extract-profile",
            json={},
            headers=h,
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Evaluations (read-only)
# ---------------------------------------------------------------------------


class TestEvaluations:
    def test_list_and_get_evaluations(self, client: httpx.Client, db_session: Session) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        from datetime import UTC, datetime

        from app.models import (
            CandidateEvaluation,
            CandidateProfile,
            JobProfile,
            MatchEvidence,
        )

        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))

        job = models.Job(
            organization_id=organization.id,
            created_by_user_id=user_obj.id,
            title="Test Job",
        )
        db_session.add(job)
        db_session.flush()

        candidate = models.Candidate(organization_id=organization.id, full_name="Test Cand")
        db_session.add(candidate)
        db_session.flush()

        resume = models.Resume(candidate_id=candidate.id, file_uri="local://test.pdf")
        db_session.add(resume)
        db_session.flush()

        application = models.JobApplication(
            organization_id=organization.id,
            job_id=job.id,
            candidate_id=candidate.id,
            resume_id=resume.id,
        )
        db_session.add(application)
        db_session.flush()

        job_profile = JobProfile(
            job_id=job.id,
            version_number=1,
            status="approved",
            source="hr_created",
            profile_data={"title": "Test Job", "requirements": []},
            approved_by_user_id=user_obj.id,
            approved_at=datetime.now(UTC),
            is_current=True,
        )
        db_session.add(job_profile)
        db_session.flush()

        candidate_profile = CandidateProfile(
            resume_id=resume.id,
            version_number=1,
            status="current",
            source="system_extracted",
            profile_data={"skills": ["Python"]},
            is_current=True,
        )
        db_session.add(candidate_profile)
        db_session.flush()

        evaluation = CandidateEvaluation(
            job_application_id=application.id,
            job_profile_id=job_profile.id,
            candidate_profile_id=candidate_profile.id,
            version_number=1,
            status="completed",
            score="85.000",
            scoring_version="1.0",
            score_breakdown={"test": "data"},
            is_current=True,
        )
        db_session.add(evaluation)
        db_session.flush()

        evidence = MatchEvidence(
            candidate_evaluation_id=evaluation.id,
            evidence_type="matched",
            requirement_ref={"requirement_key": "req-test1234567890"},
        )
        db_session.add(evidence)
        db_session.flush()

        resp = client.get(f"/api/v1/job-applications/{application.id}/evaluations", headers=h)
        assert resp.status_code == 200
        evals = resp.json()
        assert len(evals) >= 1
        assert evals[0]["score"] == "85.000"

        resp = client.get(f"/api/v1/evaluations/{evaluation.id}", headers=h)
        assert resp.status_code == 200
        assert resp.json()["score"] == "85.000"
        assert resp.json()["score_breakdown"] == {"test": "data"}

        resp = client.get(f"/api/v1/evaluations/{evaluation.id}/evidence", headers=h)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


# ---------------------------------------------------------------------------
# HR Decisions
# ---------------------------------------------------------------------------


class TestHRDecisions:
    def test_create_decision(self, client: httpx.Client, db_session: Session) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))

        job = models.Job(
            organization_id=organization.id,
            created_by_user_id=user_obj.id,
            title="J",
        )
        db_session.add(job)
        db_session.flush()

        candidate = models.Candidate(organization_id=organization.id, full_name="C")
        db_session.add(candidate)
        db_session.flush()

        resume = models.Resume(candidate_id=candidate.id, file_uri="local://r.pdf")
        db_session.add(resume)
        db_session.flush()

        application = models.JobApplication(
            organization_id=organization.id,
            job_id=job.id,
            candidate_id=candidate.id,
            resume_id=resume.id,
        )
        db_session.add(application)
        db_session.flush()

        resp = client.post(
            f"/api/v1/job-applications/{application.id}/decisions",
            json={"decision": "advance", "reason": "Good fit"},
            headers=h,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["decision"] == "advance"
        assert data["reason"] == "Good fit"
        assert data["user_id"] == user["id"]

    def test_create_decision_with_evaluation_reference(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))

        job = models.Job(
            organization_id=organization.id,
            created_by_user_id=user_obj.id,
            title="J",
        )
        db_session.add(job)
        db_session.flush()

        candidate = models.Candidate(organization_id=organization.id, full_name="C")
        db_session.add(candidate)
        db_session.flush()

        resume = models.Resume(candidate_id=candidate.id, file_uri="local://r.pdf")
        db_session.add(resume)
        db_session.flush()

        application = models.JobApplication(
            organization_id=organization.id,
            job_id=job.id,
            candidate_id=candidate.id,
            resume_id=resume.id,
        )
        db_session.add(application)
        db_session.flush()

        job_profile = models.JobProfile(
            job_id=job.id,
            version_number=1,
            status="approved",
            source="hr_created",
            profile_data={"title": "J", "skills": ["Python"]},
            approved_by_user_id=user_obj.id,
            approved_at=datetime.now(UTC),
            is_current=True,
        )
        db_session.add(job_profile)
        db_session.flush()

        candidate_profile = models.CandidateProfile(
            resume_id=resume.id,
            version_number=1,
            status="current",
            source="system_extracted",
            profile_data={"skills": ["Python"]},
            is_current=True,
        )
        db_session.add(candidate_profile)
        db_session.flush()

        evaluation = models.CandidateEvaluation(
            job_application_id=application.id,
            job_profile_id=job_profile.id,
            candidate_profile_id=candidate_profile.id,
            version_number=1,
            status="completed",
            recommendation="advance",
            explanation={"summary": "Strong match."},
            is_current=True,
        )
        db_session.add(evaluation)
        db_session.flush()

        resp = client.post(
            f"/api/v1/job-applications/{application.id}/decisions",
            json={
                "decision": "advance",
                "reason": "Good fit.",
                "candidate_evaluation_id": str(evaluation.id),
            },
            headers=h,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["decision"] == "advance"
        assert data["candidate_evaluation_id"] == str(evaluation.id)

    def test_invalid_decision_rejected(self, client: httpx.Client, db_session: Session) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))

        job = models.Job(
            organization_id=organization.id,
            created_by_user_id=user_obj.id,
            title="J",
        )
        db_session.add(job)
        db_session.flush()

        candidate = models.Candidate(organization_id=organization.id, full_name="C")
        db_session.add(candidate)
        db_session.flush()

        resume = models.Resume(candidate_id=candidate.id, file_uri="local://r.pdf")
        db_session.add(resume)
        db_session.flush()

        application = models.JobApplication(
            organization_id=organization.id,
            job_id=job.id,
            candidate_id=candidate.id,
            resume_id=resume.id,
        )
        db_session.add(application)
        db_session.flush()

        resp = client.post(
            f"/api/v1/job-applications/{application.id}/decisions",
            json={"decision": "invalid_decision"},
            headers=h,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# No POST MatchEvidence endpoint
# ---------------------------------------------------------------------------


class TestNoMatchEvidencePost:
    def test_no_post_evidence_endpoint(self, client: httpx.Client) -> None:
        resp = client.post(
            "/api/v1/evaluations/00000000-0000-0000-0000-000000000000/evidence",
            json={},
        )
        assert resp.status_code == 405


# ---------------------------------------------------------------------------
# No evaluation CRUD creation endpoint
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Candidate Pool (job-scoped ranking)
# ---------------------------------------------------------------------------


class TestCandidatePool:
    def _seed(
        self,
        client: httpx.Client,
        db_session: Session,
        org: dict,
        user: dict,
    ) -> tuple[models.Job, dict]:
        from datetime import UTC, datetime
        from decimal import Decimal

        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))

        h = auth_headers(org["id"], user["id"])
        resp = client.post("/api/v1/jobs", json={"title": "Pool Job"}, headers=h)
        job = resp.json()
        job_obj = db_session.get(models.Job, uuid.UUID(job["id"]))

        job_profile = models.JobProfile(
            job_id=job_obj.id,
            version_number=1,
            status="approved",
            source="hr_created",
            profile_data={"title": "Pool Job", "requirements": []},
            approved_by_user_id=user_obj.id,
            approved_at=datetime.now(UTC),
            is_current=True,
        )
        db_session.add(job_profile)
        db_session.flush()

        def add_candidate(full_name, email, score=None, decision=None):
            candidate = models.Candidate(
                organization_id=organization.id, full_name=full_name, email=email
            )
            db_session.add(candidate)
            db_session.flush()
            resume = models.Resume(candidate_id=candidate.id, file_uri="local://pool.pdf")
            db_session.add(resume)
            db_session.flush()
            application = models.JobApplication(
                organization_id=organization.id,
                job_id=job_obj.id,
                candidate_id=candidate.id,
                resume_id=resume.id,
            )
            db_session.add(application)
            db_session.flush()
            candidate_profile = models.CandidateProfile(
                resume_id=resume.id,
                version_number=1,
                status="current",
                source="system_extracted",
                profile_data={"skills": []},
                is_current=True,
            )
            db_session.add(candidate_profile)
            db_session.flush()
            if score is not None:
                evaluation = models.CandidateEvaluation(
                    job_application_id=application.id,
                    job_profile_id=job_profile.id,
                    candidate_profile_id=candidate_profile.id,
                    version_number=1,
                    status="completed",
                    score=Decimal(score),
                    recommendation="advance",
                    is_current=True,
                    completed_at=datetime.now(UTC),
                )
                db_session.add(evaluation)
                db_session.flush()
            if decision is not None:
                hr_decision = models.HRDecision(
                    job_application_id=application.id,
                    user_id=user_obj.id,
                    decision=decision,
                    reason="Reviewer decision.",
                )
                db_session.add(hr_decision)
                db_session.flush()
            return candidate, application

        add_candidate("Ada Top", "ada@example.com", score=88, decision="advance")
        add_candidate("Ben Mid", "ben@example.com", score=55, decision="hold")
        add_candidate("Cid Low", "cid@example.com", score=20)
        no_eval, no_eval_app = add_candidate("Dee None", "dee@example.com")
        db_session.commit()
        return job_obj, {"no_eval_candidate": no_eval, "no_eval_app": no_eval_app}

    def test_list_ranked_candidates(self, client: httpx.Client, db_session: Session) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        job, _ = self._seed(client, db_session, org, user)

        resp = client.get(f"/api/v1/jobs/{job.id}/candidates", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4

        names = [row["full_name"] for row in data]
        assert names == ["Ada Top", "Ben Mid", "Cid Low", "Dee None"]
        assert data[0]["group"] == "must_review"
        assert data[1]["group"] == "consider"
        assert data[2]["group"] == "lower_priority"
        assert data[3]["group"] == "lower_priority"
        assert data[0]["decision"] == "advance"
        assert data[1]["decision"] == "hold"
        assert data[2]["decision"] is None
        assert data[3]["score"] is None
        assert data[0]["score"] == "88"
        for row in data:
            assert "extracted_text" not in row
            assert "candidate_id" in row
            assert "application_id" in row

    def test_group_and_search_filters(self, client: httpx.Client, db_session: Session) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        job, _ = self._seed(client, db_session, org, user)

        resp = client.get(f"/api/v1/jobs/{job.id}/candidates?group=consider", headers=h)
        assert resp.status_code == 200
        assert [row["full_name"] for row in resp.json()] == ["Ben Mid"]

        resp = client.get(f"/api/v1/jobs/{job.id}/candidates?search=dee@example", headers=h)
        assert resp.status_code == 200
        assert [row["full_name"] for row in resp.json()] == ["Dee None"]

        resp = client.get(f"/api/v1/jobs/{job.id}/candidates?decision=hold", headers=h)
        assert resp.status_code == 200
        assert [row["full_name"] for row in resp.json()] == ["Ben Mid"]

        resp = client.get(f"/api/v1/jobs/{job.id}/candidates?min_score=40", headers=h)
        assert resp.status_code == 200
        assert [row["full_name"] for row in resp.json()] == ["Ada Top", "Ben Mid"]

    def test_cross_org_job_returns_422(self, client: httpx.Client, db_session: Session) -> None:
        org_a, user_a = bootstrap(client)
        job, _ = self._seed(client, db_session, org_a, user_a)

        org_b, user_b = bootstrap(client)
        h = auth_headers(org_b["id"], user_b["id"])
        resp = client.get(f"/api/v1/jobs/{job.id}/candidates", headers=h)
        assert resp.status_code in (404, 422)

    def test_nonexistent_job_returns_404(self, client: httpx.Client, db_session: Session) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        resp = client.get(f"/api/v1/jobs/{uuid.uuid4()}/candidates", headers=h)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Job screening (Phase 4.5 batch CV screening endpoint)
# ---------------------------------------------------------------------------


class TestJobScreening:
    def _pdf(self, filename: str = "ada-lovelace.pdf") -> tuple[str, bytes, str]:
        from tests.resume_upload_fixtures import make_pdf_bytes

        return filename, make_pdf_bytes(), "application/pdf"

    def test_screen_batch_creates_candidates_applications_evaluations(
        self, client: httpx.Client
    ) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        job = client.post(
            "/api/v1/jobs",
            json={
                "title": "Screening Test Job",
                "status": "active",
                "raw_description": "Build and maintain backend services.",
            },
            headers=h,
        ).json()
        _approve_job_profile(client, h, job["id"])

        resp = client.post(
            f"/api/v1/jobs/{job['id']}/screen",
            headers=h,
            files=[
                ("files", self._pdf("ada-lovelace.pdf")),
                ("files", self._pdf("grace-hopper-cv.pdf")),
            ],
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["job_id"] == job["id"]
        assert data["job_title"] == "Screening Test Job"
        assert len(data["screened"]) == 2

        for row in data["screened"]:
            assert row["candidate_id"] is not None
            assert row["resume_id"] is not None
            assert row["application_id"] is not None
            assert row["evaluation_id"] is not None

            apps = client.get(
                f"/api/v1/job-applications/{row['application_id']}",
                headers=h,
            )
            assert apps.status_code == 200

            evals = client.get(
                f"/api/v1/job-applications/{row['application_id']}/evaluations",
                headers=h,
            )
            assert evals.status_code == 200
            assert len(evals.json()) >= 1

        resp = client.get(f"/api/v1/jobs/{job['id']}/applications", headers=h)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_screen_extracts_real_details_and_downloads_cv(self, client: httpx.Client) -> None:
        import io
        from decimal import Decimal

        from docx import Document

        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        resume_lines = [
            "Ada Lovelace",
            "London, United Kingdom",
            "ada.lovelace@example.com",
            "+44 20 7946 0958",
            "linkedin.com/in/ada-lovelace",
            "github.com/adalovelace",
            "portfolio: ada.dev/engineering",
            "EXPERIENCE",
            "Data Analyst, 2018 - 2021",
            "Senior Data Engineer, 2021 - present",
            "EDUCATION",
            "BSc Computer Science",
            "MSc Data Science",
            "CERTIFICATIONS",
            "AWS Certified Solutions Architect",
            "SKILLS",
            "Python, TypeScript, React, Postgres, Docker, Kubernetes, Machine Learning",
            "Languages: English (native), French",
        ]
        document = Document()
        for line in resume_lines:
            document.add_paragraph(line)
        buffer = io.BytesIO()
        document.save(buffer)

        job = client.post(
            "/api/v1/jobs",
            json={
                "title": "Screening Details Job",
                "status": "active",
                "raw_description": "Hiring an engineer with backend experience.",
                "required_skills": ["Python", "Data Engineering", "Postgres"],
                "requirements": ["Machine Learning"],
            },
            headers=h,
        ).json()
        _approve_job_profile(client, h, job["id"])

        resp = client.post(
            f"/api/v1/jobs/{job['id']}/screen",
            headers=h,
            files=[
                (
                    "files",
                    (
                        "ada-lovelace-cv.docx",
                        buffer.getvalue(),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ),
                )
            ],
        )
        assert resp.status_code == 201
        row = resp.json()["screened"][0]
        score = Decimal(row["score"])
        assert score > 0

        profiles = client.get(f"/api/v1/resumes/{row['resume_id']}/profiles", headers=h)
        assert profiles.status_code == 200
        profile_data = profiles.json()[0]["profile_data"]
        assert profile_data["email"] == "ada.lovelace@example.com"
        assert profile_data["phone"] == "+44 20 7946 0958"
        assert "linkedin.com/in/ada-lovelace" in profile_data["linkedin_url"]
        assert any((s or "").strip().lower() == "python" for s in (profile_data["skills"] or []))
        assert len(profile_data["education"]) >= 2

        evaluations = client.get(
            f"/api/v1/job-applications/{row['application_id']}/evaluations",
            headers=h,
        )
        assert evaluations.status_code == 200
        evaluation = evaluations.json()[0]
        assert Decimal(evaluation["score"]) == score
        assert evaluation["explanation"]["summary"]

        evidence = client.get(
            f"/api/v1/evaluations/{row['evaluation_id']}/evidence",
            headers=h,
        )
        assert evidence.status_code == 200
        assert len(evidence.json()) >= 1
        assert {"matched", "missing", "partial"} & {
            item["evidence_type"] for item in evidence.json()
        }

        download = client.get(f"/api/v1/resumes/{row['resume_id']}/download", headers=h)
        assert download.status_code == 200
        assert download.content[:2] == b"PK"  # docx zip signature

    def test_screen_rejects_empty_file(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        job = client.post(
            "/api/v1/jobs",
            json={
                "title": "Screening Empty Job",
                "status": "active",
                "raw_description": "A job description.",
            },
            headers=h,
        ).json()
        _approve_job_profile(client, h, job["id"])

        resp = client.post(
            f"/api/v1/jobs/{job['id']}/screen",
            headers=h,
            files=[("files", ("empty.pdf", b"", "application/pdf"))],
        )
        assert resp.status_code == 422

    def test_screen_nonexistent_job_returns_404(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])

        resp = client.post(
            f"/api/v1/jobs/{uuid.uuid4()}/screen",
            headers=h,
            files=[("files", self._pdf("ada-lovelace.pdf"))],
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Phase 4 Application / Review / Talent Pool read models
# ---------------------------------------------------------------------------


def _seed_application_records(
    db_session: Session,
    organization: models.Organization,
    user: models.User,
) -> tuple[models.JobApplication, models.Job, models.Candidate, models.Resume]:
    """Insert application parent records (job, candidate, resume, app, profiles)."""
    job = models.Job(
        organization_id=organization.id,
        created_by_user_id=user.id,
        title="Read Model Job",
    )
    candidate = models.Candidate(
        organization_id=organization.id,
        full_name="Read Model Candidate",
        email="read-model@example.com",
    )
    db_session.add_all([job, candidate])
    db_session.flush()

    resume = models.Resume(candidate_id=candidate.id, file_uri="local://read-model.pdf")
    db_session.add(resume)
    db_session.flush()

    application = models.JobApplication(
        organization_id=organization.id,
        job_id=job.id,
        candidate_id=candidate.id,
        resume_id=resume.id,
    )
    db_session.add(application)
    db_session.flush()

    job_profile = models.JobProfile(
        job_id=job.id,
        version_number=1,
        status="approved",
        source="hr_created",
        profile_data={"title": "Read Model Job", "requirements": [], "skills": ["Python"]},
        approved_by_user_id=user.id,
        approved_at=datetime.now(UTC),
        is_current=True,
    )
    candidate_profile = models.CandidateProfile(
        resume_id=resume.id,
        version_number=1,
        status="current",
        source="system_extracted",
        profile_data={"skills": ["Python"]},
        is_current=True,
    )
    db_session.add_all([job_profile, candidate_profile])
    db_session.flush()

    return application, job, candidate, resume


def _seed_evaluation(
    db_session: Session,
    application: models.JobApplication,
    *,
    score: str = "95.000",
    recommendation: str | None = None,
) -> models.CandidateEvaluation:
    """Insert a completed current evaluation for an application."""
    job_profile = db_session.scalar(
        select(models.JobProfile)
        .where(models.JobProfile.job_id == application.job_id)
        .order_by(models.JobProfile.version_number)
    )
    resume = db_session.get(models.Resume, application.resume_id)
    candidate_profile = db_session.scalar(
        select(models.CandidateProfile)
        .where(models.CandidateProfile.resume_id == resume.id)
        .order_by(models.CandidateProfile.version_number)
    )
    evaluation = models.CandidateEvaluation(
        job_application_id=application.id,
        job_profile_id=job_profile.id,
        candidate_profile_id=candidate_profile.id,
        version_number=1,
        status="completed",
        score=score,
        recommendation=recommendation,
        explanation={"summary": "Strong match."},
        scoring_version="1.0",
        is_current=True,
        completed_at=datetime.now(UTC),
    )
    db_session.add(evaluation)
    db_session.flush()
    return evaluation


def _approve_job_profile(client: httpx.Client, headers: dict, job_id: str) -> str:
    """Extract a JobProfile draft for a job and approve it via the HR endpoint."""
    extract = client.post(f"/api/v1/jobs/{job_id}/extract-profile", headers=headers)
    assert extract.status_code == 201, extract.text
    profile_id = extract.json()["profile_id"]
    approve = client.post(f"/api/v1/job-profiles/{profile_id}/approve", headers=headers)
    assert approve.status_code == 200, approve.text
    return profile_id


class TestApplicationList:
    def test_list_applications_org_scoped_with_summary_fields(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))
        application, job, candidate, _resume = _seed_application_records(
            db_session, organization, user_obj
        )
        _seed_evaluation(db_session, application, score="92.000")

        other_org, other_user = bootstrap(client)
        other_organization = db_session.get(models.Organization, uuid.UUID(other_org["id"]))
        other_user_obj = db_session.get(models.User, uuid.UUID(other_user["id"]))
        _seed_application_records(db_session, other_organization, other_user_obj)

        resp = client.get("/api/v1/job-applications", headers=h)
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == str(application.id)
        assert row["candidate_id"] == str(candidate.id)
        assert row["candidate_name"] == "Read Model Candidate"
        assert row["job_id"] == str(job.id)
        assert row["job_title"] == "Read Model Job"
        assert float(row["score"]) == 92.0
        assert row["status"] == "created"
        assert row["group"] == "must_review"
        assert row["evidence"] == []

    def test_list_applications_includes_group_and_evidence(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))
        application, _job, _candidate, _resume = _seed_application_records(
            db_session, organization, user_obj
        )
        evaluation = _seed_evaluation(db_session, application, score="55.000")
        evaluation.score_breakdown = {
            "req-0000000000000004": {"text": "Scala", "category": "must_have"},
        }
        db_session.add_all(
            [
                models.MatchEvidence(
                    candidate_evaluation_id=evaluation.id,
                    evidence_type="matched",
                    requirement_ref={"requirement_key": "req-0000000000000001", "text": "Python"},
                    strength="strong",
                ),
                models.MatchEvidence(
                    candidate_evaluation_id=evaluation.id,
                    evidence_type="partial",
                    requirement_ref={
                        "requirement_key": "req-0000000000000002",
                        "skill": "Airflow",
                    },
                    strength="moderate",
                ),
                models.MatchEvidence(
                    candidate_evaluation_id=evaluation.id,
                    evidence_type="missing",
                    requirement_ref={
                        "requirement_key": "req-0000000000000003",
                        "text": "Kubernetes",
                    },
                    strength="weak",
                ),
                models.MatchEvidence(
                    candidate_evaluation_id=evaluation.id,
                    evidence_type="matched",
                    requirement_ref={"requirement_key": "req-0000000000000004"},
                ),
            ]
        )
        db_session.flush()

        resp = client.get("/api/v1/job-applications", headers=h)
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 1
        row = rows[0]
        assert row["group"] == "consider"
        assert sorted(row["evidence"], key=lambda item: item["requirement_key"]) == [
            {
                "requirement_key": "req-0000000000000001",
                "evidence_type": "matched",
                "text": "Python",
            },
            {
                "requirement_key": "req-0000000000000002",
                "evidence_type": "partial",
                "text": "Airflow",
            },
            {
                "requirement_key": "req-0000000000000003",
                "evidence_type": "missing",
                "text": "Kubernetes",
            },
            {
                "requirement_key": "req-0000000000000004",
                "evidence_type": "matched",
                "text": "Scala",
            },
        ]

    def test_list_applications_two_apps_order_and_evidence_scoping(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))
        app_a, _job_a, _candidate_a, _resume_a = _seed_application_records(
            db_session, organization, user_obj
        )
        job_b = models.Job(
            organization_id=organization.id,
            created_by_user_id=user_obj.id,
            title="Read Model Job B",
        )
        candidate_b = models.Candidate(
            organization_id=organization.id,
            full_name="Second Candidate",
            email="second-candidate@example.com",
        )
        db_session.add_all([job_b, candidate_b])
        db_session.flush()
        resume_b = models.Resume(candidate_id=candidate_b.id, file_uri="local://read-model-b.pdf")
        db_session.add(resume_b)
        db_session.flush()
        app_b = models.JobApplication(
            organization_id=organization.id,
            job_id=job_b.id,
            candidate_id=candidate_b.id,
            resume_id=resume_b.id,
            status="hold",
        )
        db_session.add(app_b)
        db_session.flush()
        eval_a = _seed_evaluation(db_session, app_a, score="92.000")
        db_session.add(
            models.MatchEvidence(
                candidate_evaluation_id=eval_a.id,
                evidence_type="matched",
                requirement_ref={"requirement_key": "req-0000000000000001", "text": "Python"},
            )
        )
        db_session.flush()

        resp = client.get("/api/v1/job-applications", headers=h)
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 2
        by_id = {row["id"]: row for row in rows}
        assert by_id[str(app_a.id)]["evidence"] == [
            {
                "requirement_key": "req-0000000000000001",
                "evidence_type": "matched",
                "text": "Python",
            }
        ]
        assert by_id[str(app_b.id)]["evidence"] == []
        assert by_id[str(app_a.id)]["group"] == "must_review"
        assert by_id[str(app_b.id)]["group"] == "lower_priority"

    def test_list_applications_status_filter(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))
        application, _job, _candidate, _resume = _seed_application_records(
            db_session, organization, user_obj
        )
        application.status = "hold"
        db_session.flush()

        resp = client.get("/api/v1/job-applications", params={"status": "hold"}, headers=h)
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 1
        assert rows[0]["status"] == "hold"

        resp = client.get(
            "/api/v1/job-applications", params={"status": "ready_for_review"}, headers=h
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_applications_invalid_status_returns_422(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        resp = client.get("/api/v1/job-applications", params={"status": "bogus"}, headers=h)
        assert resp.status_code == 422

    def test_list_applications_candidate_filter(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))
        application, _job, candidate, _resume = _seed_application_records(
            db_session, organization, user_obj
        )
        job_b = models.Job(
            organization_id=organization.id,
            created_by_user_id=user_obj.id,
            title="Read Model Job B",
        )
        db_session.add(job_b)
        db_session.flush()
        resume_b = models.Resume(candidate_id=candidate.id, file_uri="local://read-model-b.pdf")
        db_session.add(resume_b)
        db_session.flush()
        app_b = models.JobApplication(
            organization_id=organization.id,
            job_id=job_b.id,
            candidate_id=candidate.id,
            resume_id=resume_b.id,
            status="hold",
        )
        db_session.add(app_b)
        db_session.flush()

        other_org, other_user = bootstrap(client)
        other_organization = db_session.get(models.Organization, uuid.UUID(other_org["id"]))
        other_user_obj = db_session.get(models.User, uuid.UUID(other_user["id"]))
        _other_app, _other_job, other_candidate, _other_resume = _seed_application_records(
            db_session, other_organization, other_user_obj
        )

        resp = client.get(
            "/api/v1/job-applications",
            params={"candidate_id": str(candidate.id)},
            headers=h,
        )
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 2
        assert {row["id"] for row in rows} == {str(application.id), str(app_b.id)}
        assert all(row["candidate_id"] == str(candidate.id) for row in rows)

        resp = client.get(
            "/api/v1/job-applications",
            params={"candidate_id": str(other_candidate.id)},
            headers=h,
        )
        assert resp.status_code == 200
        assert resp.json() == []

        resp = client.get(
            "/api/v1/job-applications",
            params={"candidate_id": str(uuid.uuid4())},
            headers=h,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_applications_missing_headers_returns_422(self, client: httpx.Client) -> None:
        resp = client.get("/api/v1/job-applications")
        assert resp.status_code in (401, 422)


class TestInterviewQuestionSetCreate:
    def test_create_question_set_creates_generated_draft(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))
        application, _job, _candidate, _resume = _seed_application_records(
            db_session, organization, user_obj
        )

        payload = {
            "questions": [
                {
                    "category": "technical",
                    "text": "Walk me through a REST API you designed.",
                    "topic": "API design",
                    "requirement_key": "req-0000000000000001",
                },
                {
                    "category": "behavioral",
                    "text": "Tell me about a failure you learned from.",
                    "topic": None,
                    "requirement_key": None,
                },
            ]
        }
        resp = client.post(
            f"/api/v1/job-applications/{application.id}/question-sets",
            json=payload,
            headers=h,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["job_application_id"] == str(application.id)
        assert body["organization_id"] == str(organization.id)
        assert body["status"] == "generated"
        assert body["generated_by"] == "hr"
        assert body["is_current"] is False
        assert body["version_number"] == 1
        assert body["provenance"] == {"source": "interview_prep"}
        assert [question["position"] for question in body["questions"]] == [0, 1]
        assert [question["text"] for question in body["questions"]] == [
            "Walk me through a REST API you designed.",
            "Tell me about a failure you learned from.",
        ]

        listed = client.get(f"/api/v1/job-applications/{application.id}/question-sets", headers=h)
        assert listed.status_code == 200
        assert listed.json()["total"] == 1
        assert listed.json()["question_sets"][0]["id"] == body["id"]

    def test_create_question_set_unknown_application_returns_404(
        self, client: httpx.Client
    ) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        resp = client.post(
            f"/api/v1/job-applications/{uuid.uuid4()}/question-sets",
            json={
                "questions": [
                    {
                        "category": "technical",
                        "text": "Explain optimistic locking.",
                        "topic": None,
                        "requirement_key": None,
                    }
                ]
            },
            headers=h,
        )
        assert resp.status_code == 404

    def test_create_question_set_other_org_application_returns_422(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        other_org, other_user = bootstrap(client)
        other_organization = db_session.get(models.Organization, uuid.UUID(other_org["id"]))
        other_user_obj = db_session.get(models.User, uuid.UUID(other_user["id"]))
        other_application, _job, _candidate, _resume = _seed_application_records(
            db_session, other_organization, other_user_obj
        )
        resp = client.post(
            f"/api/v1/job-applications/{other_application.id}/question-sets",
            json={
                "questions": [
                    {
                        "category": "technical",
                        "text": "Explain optimistic locking.",
                        "topic": None,
                        "requirement_key": None,
                    }
                ]
            },
            headers=h,
        )
        assert resp.status_code in (404, 422)

    def test_create_question_set_empty_questions_returns_422(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))
        application, _job, _candidate, _resume = _seed_application_records(
            db_session, organization, user_obj
        )
        resp = client.post(
            f"/api/v1/job-applications/{application.id}/question-sets",
            json={"questions": []},
            headers=h,
        )
        assert resp.status_code == 422


class TestQuestionGapDisplayLabels:
    def test_candidate_specific_gap_question_never_leaks_requirement_key(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))
        application, _job, candidate, _resume = _seed_application_records(
            db_session, organization, user_obj
        )
        evaluation = _seed_evaluation(db_session, application, score="55.000")
        evaluation.score_breakdown = {
            "req-gap-example": {"text": "Distributed Systems", "category": "must_have"},
        }
        db_session.add(
            models.MatchEvidence(
                candidate_evaluation_id=evaluation.id,
                evidence_type="missing",
                requirement_ref={"requirement_key": "req-gap-example"},
                strength="weak",
            )
        )
        db_session.flush()

        resp = client.get(
            "/api/v1/interview-questions",
            params={"candidate_id": str(candidate.id)},
            headers=h,
        )
        assert resp.status_code == 200
        body = resp.json()
        gap_questions = [
            question["text"]
            for question in body["questions"]["Candidate-Specific"]
            if question["id"].startswith("cs-gap-")
        ]
        assert gap_questions
        assert "req-gap-example" not in " ".join(gap_questions)
        assert "Distributed Systems" in gap_questions[0]

    def test_generated_gap_question_uses_readable_label(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))
        application, _job, candidate, _resume = _seed_application_records(
            db_session, organization, user_obj
        )
        evaluation = _seed_evaluation(db_session, application, score="55.000")
        evaluation.score_breakdown = {
            "req-gap-example": {"text": "Distributed Systems", "category": "must_have"},
        }
        db_session.add(
            models.MatchEvidence(
                candidate_evaluation_id=evaluation.id,
                evidence_type="missing",
                requirement_ref={"requirement_key": "req-gap-example"},
                strength="weak",
            )
        )
        db_session.flush()

        resp = client.post(
            f"/api/v1/job-applications/{application.id}/question-sets/generate",
            headers=h,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert any("Distributed Systems" in question["text"] for question in body["questions"])
        for question in body["questions"]:
            assert "req-gap-example" not in question["text"]


class TestReviewBundle:
    def test_review_bundle_returns_full_shape(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))
        application, _job, _candidate, _resume = _seed_application_records(
            db_session, organization, user_obj
        )
        evaluation = _seed_evaluation(
            db_session, application, score="95.000", recommendation="advance"
        )
        evidence = models.MatchEvidence(
            candidate_evaluation_id=evaluation.id,
            evidence_type="matched",
            requirement_ref={"requirement_key": "req-python1234567890"},
            candidate_evidence={"source": "resume", "skill": "Python"},
            strength="strong",
            provenance={"source": "fake"},
        )
        decision = models.HRDecision(
            job_application_id=application.id,
            user_id=user_obj.id,
            decision="hold",
            reason="Second opinion.",
            candidate_evaluation_id=evaluation.id,
        )
        db_session.add_all([evidence, decision])
        db_session.flush()

        resp = client.get(f"/api/v1/job-applications/{application.id}/review-bundle", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["application"]["id"] == str(application.id)
        assert data["candidate"]["name"] == "Read Model Candidate"
        assert data["candidate"]["email"] == "read-model@example.com"
        assert data["job"]["title"] == "Read Model Job"
        assert len(data["evaluations"]) == 1
        assert data["evaluation"]["id"] == str(evaluation.id)
        assert data["evaluation"]["score"] == "95.000"
        assert data["evaluation"]["recommendation"] == "advance"
        assert len(data["evidence"]) == 1
        assert data["evidence"][0]["evidence_type"] == "matched"
        pool_row = data["pool_row"]
        assert pool_row["group"] == "must_review"
        assert pool_row["score"] == "95.000"
        assert pool_row["decision"] == "hold"
        assert pool_row["decision_created_at"] is not None

    def test_review_bundle_without_evaluation(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))
        application, _job, _candidate, _resume = _seed_application_records(
            db_session, organization, user_obj
        )

        resp = client.get(f"/api/v1/job-applications/{application.id}/review-bundle", headers=h)
        assert resp.status_code == 200
        data = resp.json()
        assert data["evaluations"] == []
        assert data["evaluation"] is None
        assert data["evidence"] == []
        assert data["pool_row"]["group"] == "lower_priority"
        assert data["pool_row"]["score"] is None
        assert data["pool_row"]["decision"] is None

    def test_review_bundle_org_mismatch_returns_422(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        org, user = bootstrap(client)
        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))
        application, _job, _candidate, _resume = _seed_application_records(
            db_session, organization, user_obj
        )

        other_org, other_user = bootstrap(client)
        other_h = auth_headers(other_org["id"], other_user["id"])
        resp = client.get(
            f"/api/v1/job-applications/{application.id}/review-bundle", headers=other_h
        )
        assert resp.status_code in (404, 422)

    def test_review_bundle_missing_returns_404(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        resp = client.get(f"/api/v1/job-applications/{uuid.uuid4()}/review-bundle", headers=h)
        assert resp.status_code == 404


class TestTriggerEvaluation:
    @staticmethod
    def _populate_extracted_source(
        client: httpx.Client,
        headers: dict[str, str],
        db_session: Session,
        application: models.JobApplication,
    ) -> None:
        from tests.resume_upload_fixtures import make_pdf_bytes

        original_resume_id = application.resume_id
        uploaded = client.post(
            f"/api/v1/candidates/{application.candidate_id}/resumes/upload",
            headers=headers,
            files={
                "file": (
                    "synthetic-resume.pdf",
                    make_pdf_bytes("Synthetic engineer with production Python experience."),
                    "application/pdf",
                )
            },
        )
        assert uploaded.status_code == 201, uploaded.text
        source_resume = db_session.get(models.Resume, uuid.UUID(uploaded.json()["id"]))
        assert source_resume.extracted_text == (
            "Synthetic engineer with production Python experience."
        )
        application.resume_id = source_resume.id
        candidate_profile = db_session.scalar(
            select(models.CandidateProfile).where(
                models.CandidateProfile.resume_id == original_resume_id
            )
        )
        candidate_profile.resume_id = source_resume.id
        profile = db_session.scalar(
            select(models.JobProfile).where(models.JobProfile.job_id == application.job_id)
        )
        profile.profile_data = {
            "title": "Read Model Job",
            "requirements": [
                {"text": "Python", "category": "must_have", "dimension": "skill"}
            ],
            "skills": ["Python"],
        }
        db_session.flush()

    def test_trigger_evaluation_creates_evaluation_and_traces(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))
        application, _job, _candidate, _resume = _seed_application_records(
            db_session, organization, user_obj
        )
        self._populate_extracted_source(client, h, db_session, application)

        resp = client.post(f"/api/v1/job-applications/{application.id}/evaluations", headers=h)
        assert resp.status_code == 201
        data = resp.json()
        assert data["evaluation_id"] is not None
        assert data["workflow_run_id"] is not None
        assert data["version_number"] >= 1

        workflow_runs = db_session.scalars(
            select(models.WorkflowRun).where(
                models.WorkflowRun.workflow_type == "candidate_evaluation"
            )
        ).all()
        assert len(workflow_runs) >= 1

        bundle = client.get(
            f"/api/v1/job-applications/{application.id}/review-bundle", headers=h
        ).json()
        assert bundle["evaluation"] is not None
        assert bundle["evaluation"]["id"] == data["evaluation_id"]
        assert float(bundle["pool_row"]["score"]) == 100.0
        assert bundle["evidence"][0]["candidate_evidence"]["quote_verified"] is True

    def test_evaluate_alias_still_works(self, client: httpx.Client, db_session: Session) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))
        application, _job, _candidate, _resume = _seed_application_records(
            db_session, organization, user_obj
        )
        self._populate_extracted_source(client, h, db_session, application)

        resp = client.post(f"/api/v1/job-applications/{application.id}/evaluate", headers=h)
        assert resp.status_code == 201
        data = resp.json()
        assert data["evaluation_id"] is not None

    def test_missing_source_text_returns_explicit_failure_without_zero_score(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))
        application, _job, _candidate, resume = _seed_application_records(
            db_session, organization, user_obj
        )
        assert resume.extracted_text is None

        resp = client.post(f"/api/v1/job-applications/{application.id}/evaluations", headers=h)

        assert resp.status_code == 422
        assert resp.json()["detail"] == (
            "Extracted resume text is required to generate grounded evidence."
        )
        assert db_session.scalar(select(models.CandidateEvaluation.id)) is None

    def test_trigger_evaluation_org_mismatch_returns_422(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        org, user = bootstrap(client)
        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))
        application, _job, _candidate, _resume = _seed_application_records(
            db_session, organization, user_obj
        )

        other_org, other_user = bootstrap(client)
        other_h = auth_headers(other_org["id"], other_user["id"])
        resp = client.post(
            f"/api/v1/job-applications/{application.id}/evaluations", headers=other_h
        )
        assert resp.status_code in (404, 422)

    def test_trigger_evaluation_missing_returns_404(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        resp = client.post(f"/api/v1/job-applications/{uuid.uuid4()}/evaluations", headers=h)
        assert resp.status_code == 404


class TestTalentPool:
    def test_talent_pool_returns_hold_advanced_org_scoped(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))

        hold_app, _job, hold_candidate, _resume = _seed_application_records(
            db_session, organization, user_obj
        )
        hold_app.status = "hold"
        hold_evaluation = _seed_evaluation(db_session, hold_app, score="80.000")
        db_session.add(
            models.MatchEvidence(
                candidate_evaluation_id=hold_evaluation.id,
                evidence_type="matched",
                requirement_ref={"requirement_key": "req-1234567890abcdef", "text": "Python"},
                candidate_evidence={"quote": "Built Python services.", "quote_verified": True},
            )
        )
        decision = models.HRDecision(
            job_application_id=hold_app.id,
            user_id=user_obj.id,
            candidate_evaluation_id=hold_evaluation.id,
            decision="hold",
            reason="Hold for later.",
        )
        db_session.add(decision)

        advanced_app, _job2, advanced_candidate, _resume2 = _seed_application_records(
            db_session, organization, user_obj
        )
        advanced_app.status = "advanced"
        _seed_evaluation(db_session, advanced_app, score="95.000")

        rejected_app, _job3, rejected_candidate, _resume3 = _seed_application_records(
            db_session, organization, user_obj
        )
        rejected_app.status = "rejected"
        db_session.flush()

        consented_at = datetime.now(UTC)
        for candidate in (hold_candidate, advanced_candidate, rejected_candidate):
            db_session.add(
                models.TalentPoolConsent(
                    organization_id=organization.id,
                    candidate_id=candidate.id,
                    created_by_user_id=user_obj.id,
                    token_hash=uuid.uuid4().hex * 2,
                    link_expires_at=consented_at,
                    link_used_at=consented_at,
                    response="accepted",
                    responded_at=consented_at,
                    consent_text="Synthetic test consent text.",
                    consent_version="test-v1",
                    granted_at=consented_at,
                    consent_expires_at=consented_at.replace(year=consented_at.year + 1),
                )
            )
        db_session.flush()

        other_org, other_user = bootstrap(client)
        other_organization = db_session.get(models.Organization, uuid.UUID(other_org["id"]))
        other_user_obj = db_session.get(models.User, uuid.UUID(other_user["id"]))
        other_app, _job4, _candidate4, _resume4 = _seed_application_records(
            db_session, other_organization, other_user_obj
        )
        other_app.status = "rejected"
        db_session.flush()

        resp = client.get("/api/v1/talent-pool", headers=h)
        assert resp.status_code == 200
        rows = resp.json()
        assert len(rows) == 2
        application_ids = {row["application_id"] for row in rows}
        assert application_ids == {str(hold_app.id), str(advanced_app.id)}
        hold_row = next(row for row in rows if row["application_id"] == str(hold_app.id))
        assert hold_row["full_name"] == "Read Model Candidate"
        assert hold_row["job_title"] == "Read Model Job"
        assert float(hold_row["score"]) == 80.0
        assert hold_row["decision"] == "hold"
        assert hold_row["decision_created_at"]
        assert hold_row["evidence"] == [
            {
                "evidence_type": "matched",
                "requirement": "Python",
                "quote": "Built Python services.",
                "quote_verified": True,
            }
        ]
        assert hold_row["group"] == "must_review"
        assert hold_row["skills"] == ["Python"]
        assert hold_row["consent_expires_at"]

        rejected_resp = client.get("/api/v1/talent-pool?include_rejected=true", headers=h)
        assert rejected_resp.status_code == 200
        assert {row["application_id"] for row in rejected_resp.json()} == {
            str(hold_app.id), str(advanced_app.id), str(rejected_app.id)
        }
        rejected_row = next(
            row for row in rejected_resp.json() if row["application_id"] == str(rejected_app.id)
        )
        assert rejected_row["status"] == "rejected"

    def test_talent_pool_empty_without_hold_advanced(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))
        application, _job, _candidate, _resume = _seed_application_records(
            db_session, organization, user_obj
        )
        application.status = "archived"
        db_session.flush()

        resp = client.get("/api/v1/talent-pool", headers=h)
        assert resp.status_code == 200
        assert resp.json() == []


class TestScreeningApprovalGate:
    """Prove screening never bypasses the HR JobProfile approval gate."""

    def _create_job(self, client: httpx.Client, headers: dict) -> dict:
        return client.post(
            "/api/v1/jobs",
            json={
                "title": "Gate Test Job",
                "status": "active",
                "raw_description": "Build and maintain backend services.",
            },
            headers=headers,
        ).json()

    def _pdf(self, filename: str = "gate-candidate.pdf") -> tuple[str, bytes, str]:
        from tests.resume_upload_fixtures import make_pdf_bytes

        return filename, make_pdf_bytes(), "application/pdf"

    def _screen(self, client: httpx.Client, headers: dict, job_id: str):
        return client.post(
            f"/api/v1/jobs/{job_id}/screen",
            headers=headers,
            files=[("files", self._pdf())],
        )

    def test_screen_without_approved_profile_fails(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        job = self._create_job(client, h)

        resp = self._screen(client, h, job["id"])
        assert resp.status_code == 422
        assert "approved JobProfile" in resp.json()["detail"]

    def test_screen_with_draft_profile_fails(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        job = self._create_job(client, h)

        extract = client.post(f"/api/v1/jobs/{job['id']}/extract-profile", headers=h)
        assert extract.status_code == 201

        resp = self._screen(client, h, job["id"])
        assert resp.status_code == 422
        assert "approved JobProfile" in resp.json()["detail"]

    def test_screen_with_approved_profile_succeeds(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        job = self._create_job(client, h)
        _approve_job_profile(client, h, job["id"])

        resp = self._screen(client, h, job["id"])
        assert resp.status_code == 201
        assert len(resp.json()["screened"]) == 1

    def test_extraction_never_creates_approval_metadata(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        job = self._create_job(client, h)

        extract = client.post(f"/api/v1/jobs/{job['id']}/extract-profile", headers=h)
        assert extract.status_code == 201
        profile = db_session.get(models.JobProfile, uuid.UUID(extract.json()["profile_id"]))
        assert profile is not None
        assert profile.status == "draft"
        assert profile.approved_by_user_id is None
        assert profile.approved_at is None
        assert profile.is_current is True

    def test_hr_approval_creates_approval_metadata(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        job = self._create_job(client, h)
        _approve_job_profile(client, h, job["id"])

        profile = db_session.scalar(
            select(models.JobProfile)
            .where(models.JobProfile.job_id == uuid.UUID(job["id"]))
            .order_by(models.JobProfile.version_number)
        )
        assert profile is not None
        assert profile.status == "approved"
        assert profile.approved_by_user_id == uuid.UUID(user["id"])
        assert profile.approved_at is not None
        assert profile.is_current is True

    def test_screening_does_not_overwrite_approved_profile(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        job = self._create_job(client, h)
        profile_id = _approve_job_profile(client, h, job["id"])

        resp = self._screen(client, h, job["id"])
        assert resp.status_code == 201

        profiles = client.get(f"/api/v1/jobs/{job['id']}/profiles", headers=h)
        assert profiles.status_code == 200
        versions = profiles.json()
        assert len(versions) == 1
        assert versions[0]["id"] == profile_id
        assert versions[0]["status"] == "approved"
        assert versions[0]["is_current"] is True

    def test_failed_screen_creates_no_profile_and_no_approval(self, client: httpx.Client) -> None:
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        job = self._create_job(client, h)

        resp = self._screen(client, h, job["id"])
        assert resp.status_code == 422

        profiles = client.get(f"/api/v1/jobs/{job['id']}/profiles", headers=h)
        assert profiles.status_code == 200
        assert profiles.json() == []

        job_resp = client.get(f"/api/v1/jobs/{job['id']}", headers=h)
        assert job_resp.status_code == 200
        assert job_resp.json()["status"] == "active"  # untouched by the failed screen


class _RecordingQuestionProvider:
    """Duck-typed AIProvider returning a contract-valid question payload."""

    def generate_structured(self, request):
        from app.ai.results import StructuredAIResult

        return StructuredAIResult(
            provider="recorded-soal",
            model="soal-test-model",
            data={
                "schema_version": "1.2",
                "questions": [
                    {
                        "category": "technical",
                        "text": "Describe your experience building backend services.",
                        "topic": None,
                        "requirement_key": None,
                        "review_guide": {
                            "purpose": "Explore backend development experience.",
                            "evidence_basis": "verification_question",
                            "source_quote": None,
                            "interviewer_looks_for": "A relevant example and clear explanation.",
                            "evaluation_rubric": ["Clear approach", "Relevant example"],
                        },
                    },
                    {
                        "category": "behavioral",
                        "text": "Describe a time you disagreed with a technical decision.",
                        "topic": None,
                        "requirement_key": None,
                        "review_guide": {
                            "purpose": "Understand collaboration during disagreement.",
                            "evidence_basis": "job_requirement",
                            "source_quote": None,
                            "interviewer_looks_for": "Listening and constructive resolution.",
                            "evaluation_rubric": ["Clear context", "Constructive outcome"],
                        },
                    },
                ],
            },
            schema_version=request.schema_version,
        )


class _InvalidQuestionProvider:
    def generate_structured(self, request):
        from app.ai.results import StructuredAIResult

        return StructuredAIResult(
            provider="fake",
            model="fake-model",
            data={
                "schema_version": "1.1",
                "questions": [
                    {
                        "category": "bogus",
                        "text": "",
                        "topic": None,
                        "requirement_key": None,
                    }
                ],
            },
            schema_version=request.schema_version,
        )


class TestQuestionSetGenerationProvider:
    """Prove question generation honors the configured AI provider."""

    def _seed_application(self, client: httpx.Client, db_session: Session):
        org, user = bootstrap(client)
        h = auth_headers(org["id"], user["id"])
        organization = db_session.get(models.Organization, uuid.UUID(org["id"]))
        user_obj = db_session.get(models.User, uuid.UUID(user["id"]))
        application, _job, _candidate, _resume = _seed_application_records(
            db_session, organization, user_obj
        )
        return h, application

    def test_generate_uses_fake_provider_by_default(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        h, application = self._seed_application(client, db_session)
        resp = client.post(
            f"/api/v1/job-applications/{application.id}/question-sets/generate", headers=h
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "generated"
        assert body["provenance"]["provider"] == "fake"
        assert body["provenance"]["model"] == "fake-interview-question-model"
        assert body["approved_by_user_id"] is None
        assert body["approved_at"] is None

    def test_generate_honors_soal_provider_configuration(
        self, client: httpx.Client, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorded: dict[str, object] = {}

        def stub_get_provider(settings_object, **fake_kwargs):
            recorded["provider_kwarg"] = fake_kwargs.get("provider")
            return _RecordingQuestionProvider()

        monkeypatch.setattr("app.ai.providers.get_provider", stub_get_provider)
        monkeypatch.setattr(
            "app.ai.providers.factory.resolve_ai_config",
            lambda settings_object: {
                "provider": "soal",
                "model": "soal-test-model",
                "base_url": "https://example.invalid/v1",
                "api_key": "test-key",
                "api_key_source": "environment",
                "is_fake": False,
            },
        )

        h, application = self._seed_application(client, db_session)
        resp = client.post(
            f"/api/v1/job-applications/{application.id}/question-sets/generate", headers=h
        )
        assert resp.status_code == 201
        assert recorded["provider_kwarg"] is None
        assert resp.json()["provenance"]["provider"] == "recorded-soal"
        assert resp.json()["provenance"]["model"] == "soal-test-model"

    def test_generate_reports_provider_failure(
        self, client: httpx.Client, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.ai.providers.errors import ProviderUnavailableError

        def failing_provider(settings_object, **fake_kwargs):
            raise ProviderUnavailableError("provider down")

        monkeypatch.setattr("app.ai.providers.get_provider", failing_provider)

        h, application = self._seed_application(client, db_session)
        resp = client.post(
            f"/api/v1/job-applications/{application.id}/question-sets/generate", headers=h
        )
        assert resp.status_code == 503

        sets = client.get(f"/api/v1/job-applications/{application.id}/question-sets", headers=h)
        assert sets.status_code == 200
        assert sets.json()["total"] == 0

    def test_generate_rejects_invalid_ai_output(
        self, client: httpx.Client, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.ai.providers.get_provider",
            lambda settings_object, **fake_kwargs: _InvalidQuestionProvider(),
        )

        h, application = self._seed_application(client, db_session)
        resp = client.post(
            f"/api/v1/job-applications/{application.id}/question-sets/generate", headers=h
        )
        assert resp.status_code == 422

        sets = client.get(f"/api/v1/job-applications/{application.id}/question-sets", headers=h)
        assert sets.status_code == 200
        assert sets.json()["total"] == 0

    def test_generate_creates_no_hr_decision_or_score(
        self, client: httpx.Client, db_session: Session
    ) -> None:
        h, application = self._seed_application(client, db_session)
        resp = client.post(
            f"/api/v1/job-applications/{application.id}/question-sets/generate", headers=h
        )
        assert resp.status_code == 201

        decisions = db_session.scalars(
            select(models.HRDecision).where(models.HRDecision.job_application_id == application.id)
        ).all()
        assert decisions == []

        bundle = client.get(f"/api/v1/job-applications/{application.id}/review-bundle", headers=h)
        assert bundle.status_code == 200
        assert bundle.json()["evaluations"] == []
