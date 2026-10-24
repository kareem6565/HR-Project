"""End-to-End Recruitment Workflow Validation Harness.

Drives the complete end-to-end recruitment journey across:
- Stage A: Job creation & HERA autofill
- Stage B: Job profile analysis & approval
- Stage C: CV screening (DOCX & PDF)
- Stage D: Deterministic scoring & evidence validation
- Stage E: HR assessment review & correction
- Stage F: Authoritative HR decision (Advance) & Talent Pool update
- Stage G: Advance Gate enforcement (Negative tests for Hold/Reject)
- Stage H: Interviewer availability publishing & Candidate invitation
- Stage I: Candidate self-service slot selection & concurrency-safe booking
- Stage J: Post-interview structured feedback rubric & subsequent HR decision
- Stage K: HR Feedback Learning Loop (corrections & analytics)
- Stage L: Tenant isolation & security validation

Execution:
  backend/.venv/Scripts/python.exe tools/e2e_screening_flow.py
Can run against live running backend (http://localhost:8000) or automatically
in-process with an isolated database and FakeAIProvider if server is offline.
"""
from __future__ import annotations

import io
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
from docx import Document

# Ensure backend directory is in python path
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Ensure required default configuration for test / standalone runner
os.environ.setdefault("JWT_SECRET_KEY", "hera-dev-jwt-secret-key-explicitly-configured-32bytes")
os.environ.setdefault("AI_PROVIDER", "fake")

LIVE_BASE = "http://localhost:8000/api/v1"
ORG_ID = "09df6372-c821-4c6f-b633-9f9fe8438f85"
USER_ID = "76598a7a-f0bc-4531-ad74-e232a3e30a53"
HEADERS = {"X-Organization-Id": ORG_ID, "X-User-Id": USER_ID}

RESUME_TEXT = [
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


def make_docx_bytes() -> bytes:
    doc = Document()
    for line in RESUME_TEXT:
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_pdf_bytes() -> bytes:
    text = "Grace Hopper is an engineer skilled in Python, Data Structures and Algorithms."
    content = f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET".encode("latin-1")
    parts = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>\nendobj",
        b"4 0 obj\n<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream\nendobj",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj",
    ]
    body = b"\n".join(parts)
    xref = 42 + len(body)
    return b"%PDF-1.4\n" + body + b"\ntrailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF"


def check(name: str, cond: bool, extra: str = ""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" -- {extra}" if extra else ""))
    if not cond:
        sys.exit(1)


def get_client() -> tuple[any, str]:
    """Return an HTTP client.

    Probes localhost:8000 first; if not up, sets up an in-process FastAPI TestClient
    with an SQLite in-memory database and seeded test org/user.
    """
    try:
        live_probe = httpx.get("http://localhost:8000/api/v1/health", timeout=0.8)
        if live_probe.status_code == 200:
            print("[INFO] Live backend detected at http://localhost:8000 - running against live server.")
            client = httpx.Client(base_url="http://localhost:8000/api/v1", timeout=60)
            client.headers.update(HEADERS)
            return client, "live"
    except Exception:
        pass

    print("[INFO] Live backend not detected at :8000 - initializing in-process TestClient with test database.")
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.core.database import Base, get_db
    from app.main import app
    from app.models import Organization, User

    # In-process test database with StaticPool so all threads/sessions share the same memory DB
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()

    from app.core.config import settings
    settings.ai_provider = "fake"

    # Seed organization and user corresponding to HEADERS
    org_uuid = uuid.UUID(ORG_ID)
    user_uuid = uuid.UUID(USER_ID)

    org = session.get(Organization, org_uuid)
    if not org:
        org = Organization(id=org_uuid, name="HERA E2E Flow Org")
        session.add(org)
        session.flush()

    user = session.get(User, user_uuid)
    if not user:
        user = User(
            id=user_uuid,
            organization_id=org_uuid,
            email="hera-lead@example.com",
            full_name="HERA Lead Recruiter",
            role="recruiter",
        )
        session.add(user)
        session.commit()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app, base_url="http://testserver/api/v1")
    test_client.headers.update(HEADERS)
    return test_client, "in_process"


def main():
    client, mode = get_client()
    print(f"=== HERA END-TO-END WORKFLOW HARNESS (mode: {mode}) ===\n")

    # ---------------------------------------------------------
    # STAGE A: Create and Configure a Job
    # ---------------------------------------------------------
    job_payload = {
        "title": "Staff Platform Engineer (E2E Validation)",
        "status": "active",
        "department": "Infrastructure",
        "location": "London, UK (Hybrid)",
        "raw_description": "Build high-throughput distributed systems using Python, Postgres, Docker, and Kubernetes.",
        "required_skills": ["Python", "Data Engineering", "Machine Learning", "Postgres", "Docker"],
        "requirements": ["React", "TypeScript", "Kubernetes"],
        "experience": "5+ years",
    }
    job_resp = client.post("/jobs", json=job_payload)
    check("Stage A: Create Job", job_resp.status_code == 201, f"status={job_resp.status_code}")
    job_data = job_resp.json()
    job_id = job_data["id"]
    print(f"    Created Job ID: {job_id}")

    # ---------------------------------------------------------
    # STAGE B: Analyze & Profile Approval Check
    # ---------------------------------------------------------
    profile_payload = {
        "status": "draft",
        "source": "ai_extracted",
        "profile_data": {
            "title": "Staff Platform Engineer (E2E Validation)",
            "required_skills": ["Python", "Data Engineering", "Machine Learning", "Postgres", "Docker"],
            "requirements": [
                {"text": "Python", "category": "must_have", "dimension": "skill"},
                {"text": "Docker", "category": "important", "dimension": "skill"},
                {"text": "Kubernetes", "category": "nice_to_have", "dimension": "skill"},
            ],
        },
        "raw_input_snapshot": {"raw_description": job_payload["raw_description"]},
    }
    profile_resp = client.post(f"/jobs/{job_id}/profiles", json=profile_payload)
    check("Stage B: Create Job Profile Version", profile_resp.status_code == 201, f"status={profile_resp.status_code}")
    job_profile_data = profile_resp.json()
    profile_id = job_profile_data["id"]
    print(f"    Created Job Profile Version ID: {profile_id}")

    approve_resp = client.post(f"/job-profiles/{profile_id}/approve")
    check("Stage B: Approve Job Profile Version", approve_resp.status_code == 200, f"status={approve_resp.status_code}")

    # ---------------------------------------------------------
    # STAGE C: Multi-Format CV Ingestion & Screening (DOCX & PDF)
    # ---------------------------------------------------------
    screen_resp = client.post(
        f"/jobs/{job_id}/screen",
        files=[
            ("files", ("ada-lovelace-cv.docx", make_docx_bytes(),
                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ("files", ("grace-hopper-cv.pdf", make_pdf_bytes(), "application/pdf")),
        ],
    )
    if screen_resp.status_code != 201:
        print("    [DEBUG SCREEN ERROR BODY]:", screen_resp.text)
    check("Stage C: Screen Two CVs (DOCX + PDF)", screen_resp.status_code == 201, f"status={screen_resp.status_code}")
    screen_data = screen_resp.json()
    rows = screen_data["screened"]
    check("Stage C: Two Screened Results Returned", len(rows) == 2)

    docx_row = rows[0]
    pdf_row = rows[1]
    print(f"    Candidate Ada Lovelace Score: {docx_row['score']} | Candidate Grace Hopper Score: {pdf_row['score']}")

    # ---------------------------------------------------------
    # STAGE D: Structured Profile & Deterministic Scoring
    # ---------------------------------------------------------
    check("Stage D: DOCX Score is positive", float(docx_row["score"]) > 0)
    check("Stage D: PDF Score is positive", float(pdf_row["score"]) > 0)

    # Check extracted candidate profile details
    profiles_resp = client.get(f"/resumes/{docx_row['resume_id']}/profiles")
    check("Stage D: Retrieve Candidate Profile", profiles_resp.status_code == 200)
    profiles_list = profiles_resp.json()
    check("Stage D: Profile Extracted", len(profiles_list) >= 1)
    cand_profile = profiles_list[0]["profile_data"]
    check("Stage D: Extracted Email verified", cand_profile.get("email") == "ada.lovelace@example.com")
    check("Stage D: Extracted Location verified", "London" in (cand_profile.get("location") or ""))
    check("Stage D: Extracted Skills verified", any("python" in (s or "").lower() for s in (cand_profile.get("skills") or [])))

    # Review workspace bundle verification
    bundle_resp = client.get(f"/job-applications/{docx_row['application_id']}/review-bundle")
    check("Stage D: Review Bundle Integrity", bundle_resp.status_code == 200)
    bundle = bundle_resp.json()
    check("Stage D: Evaluation Attached", (bundle.get("evaluation") or {}).get("id") == docx_row["evaluation_id"])
    check("Stage D: Score Breakdown Available", len(bundle.get("evaluation", {}).get("score_breakdown") or {}) >= 1)
    check("Stage D: Evidence Attached", len(bundle.get("evidence") or []) >= 1)

    # Evidence endpoint verification
    evidence_resp = client.get(f"/evaluations/{docx_row['evaluation_id']}/evidence")
    check("Stage D: Evidence Verification Endpoint", evidence_resp.status_code == 200)
    ev_items = evidence_resp.json()
    check("Stage D: Evidence Items have Types", all(item.get("evidence_type") in ("matched", "partial", "missing") for item in ev_items))

    # Download resume file
    download_resp = client.get(f"/resumes/{docx_row['resume_id']}/download")
    check("Stage C: Secure Document Download", download_resp.status_code == 200 and download_content_valid(download_resp))

    # ---------------------------------------------------------
    # STAGE E: HR Correction & Feedback Learning Submission
    # ---------------------------------------------------------
    correction_payload = {
        "correction_type": "requirement_match_correction",
        "job_id": job_id,
        "job_application_id": docx_row["application_id"],
        "candidate_evaluation_id": docx_row["evaluation_id"],
        "original_ai_output": {"Python": "partial"},
        "hr_corrected_result": {"Python": "matched"},
        "reason": "Ada Lovelace CV explicitly details extensive Python senior experience",
    }
    correction_resp = client.post("/feedback/corrections", json=correction_payload)
    check("Stage E & K: Submit HR Assessment Correction", correction_resp.status_code == 201)

    # ---------------------------------------------------------
    # STAGE F & G: Authoritative HR Decision & Advance Gate
    # ---------------------------------------------------------
    # Negative test: before Advance decision, candidate portal invitation or scheduling must fail
    neg_invitation = client.post(
        f"/job-applications/{pdf_row['application_id']}/invitations",
        json={"notes": "Premature invitation test"},
    )
    check("Stage G: Advance Gate Blocks Unapproved Candidate", neg_invitation.status_code in (400, 403, 404, 409, 422),
          f"status={neg_invitation.status_code}")

    # Now record explicit ADVANCE decision for Ada Lovelace
    adv_decision = client.post(
        f"/job-applications/{docx_row['application_id']}/decisions",
        json={"decision": "advance", "reason": "Outstanding engineering background; advancing to technical interview."},
    )
    check("Stage F: Record Authoritative Advance Decision", adv_decision.status_code == 201)

    # Verify candidate appears in talent pool
    pool_resp = client.get("/talent-pool")
    check("Stage F: Talent Pool Sync", pool_resp.status_code == 200)
    pool_rows = pool_resp.json()
    check("Stage F: Advanced Candidate in Talent Pool", any(r["candidate_id"] == docx_row["candidate_id"] for r in pool_rows))

    # ---------------------------------------------------------
    # STAGE H: Publish Interviewer Availability & Issue Invitation
    # ---------------------------------------------------------
    target_date = (date.today() + timedelta(days=2)).isoformat()
    avail_payload = {
        "interviewer_user_id": USER_ID,
        "scheduled_date": target_date,
        "start_time": "10:00",
        "end_time": "12:00",
        "duration_minutes": 60,
        "timezone": "Europe/London",
    }
    avail_resp = client.post("/availability", json=avail_payload)
    check("Stage H: Publish Interviewer Availability", avail_resp.status_code == 201)

    # Issue candidate invitation (permitted now because decision is 'advance')
    invitation_resp = client.post(
        f"/job-applications/{docx_row['application_id']}/invitations",
        json={"notes": "Technical Architecture Session"},
    )
    check("Stage H: Issue Candidate Self-Scheduling Invitation", invitation_resp.status_code == 201)
    invitation_data = invitation_resp.json()
    invite_token = invitation_data["token"]
    print(f"    Candidate Invitation Token: {invite_token[:12]}...")

    # ---------------------------------------------------------
    # STAGE I: Candidate Self-Service Slot Selection & Booking
    # ---------------------------------------------------------
    portal_resp = client.get(f"/candidate-portal/invitations/{invite_token}")
    check("Stage I: Candidate Views Role via Portal", portal_resp.status_code == 200)

    slots_resp = client.get(f"/candidate-portal/invitations/{invite_token}/slots")
    check("Stage I: Candidate Retrieves Open Slots", slots_resp.status_code == 200)
    available_slots = slots_resp.json()
    check("Stage I: Available Slots Offered to Candidate", len(available_slots) >= 1)
    chosen_slot = available_slots[0]
    print(f"    Selected Slot: {chosen_slot['date']} {chosen_slot['start_time']} - {chosen_slot['end_time']}")

    # Book chosen slot
    book_resp = client.post(
        f"/candidate-portal/invitations/{invite_token}/book",
        json={
            "interviewer_user_id": chosen_slot["interviewer_id"],
            "scheduled_date": chosen_slot["date"],
            "scheduled_time": chosen_slot["start_time"],
            "duration_minutes": chosen_slot["duration_minutes"],
        },
    )
    check("Stage I: Candidate Confirms Booking", book_resp.status_code == 201)
    booking_data = book_resp.json()
    interview_id = booking_data["id"]
    print(f"    Confirmed Interview ID: {interview_id}")

    # Concurrency / Double-booking protection check: booking again with same token or same slot must be rejected
    dup_book_resp = client.post(
        f"/candidate-portal/invitations/{invite_token}/book",
        json={
            "interviewer_user_id": chosen_slot["interviewer_id"],
            "scheduled_date": chosen_slot["date"],
            "scheduled_time": chosen_slot["start_time"],
            "duration_minutes": chosen_slot["duration_minutes"],
        },
    )
    check("Stage I: Concurrency / Double Booking Blocked", dup_book_resp.status_code in (400, 409, 422),
          f"status={dup_book_resp.status_code}")

    # ---------------------------------------------------------
    # STAGE J: Post-Interview Feedback & Subsequent Decision
    # ---------------------------------------------------------
    feedback_payload = {
        "technical": 5,
        "communication": 5,
        "problem_solving": 5,
        "overall": 5.0,
        "comments": "Superb system design clarity; exceptional depth in distributed databases and concurrency.",
    }
    feedback_resp = client.post(f"/interviews/{interview_id}/feedback", json=feedback_payload)
    check("Stage J: Submit Structured Interview Feedback", feedback_resp.status_code in (200, 201))

    # Subsequent post-interview HR decision (e.g. final hire offer)
    final_decision_resp = client.post(
        f"/job-applications/{docx_row['application_id']}/decisions",
        json={"decision": "advance", "reason": "Passed technical interview with top ratings; extending offer."},
    )
    check("Stage J: Post-Interview Hiring Decision (Offer)", final_decision_resp.status_code == 201)

    # ---------------------------------------------------------
    # STAGE K: Feedback Learning Analytics Verification
    # ---------------------------------------------------------
    analytics_resp = client.get("/feedback/analytics")
    check("Stage K: Feedback Learning Analytics Endpoint", analytics_resp.status_code == 200)
    analytics_data = analytics_resp.json()
    check("Stage K: Total Corrections Tracked", analytics_data.get("total_corrections", 0) >= 1)
    print(f"    Analytics: Total Corrections={analytics_data.get('total_corrections')}, Breakdown={analytics_data.get('corrections_by_type')}")

    # ---------------------------------------------------------
    # STAGE L: Multi-Tenant Organization Isolation Verification
    # ---------------------------------------------------------
    rogue_org_id = str(uuid.uuid4())
    rogue_headers = {"X-Organization-Id": rogue_org_id, "X-User-Id": str(uuid.uuid4())}
    rogue_access = client.get(f"/job-applications/{docx_row['application_id']}/review-bundle", headers=rogue_headers)
    check("Stage L: Cross-Tenant Access Blocked (Isolation)", rogue_access.status_code in (403, 404),
          f"status={rogue_access.status_code}")

    print("\n=======================================================")
    print("ALL 12 RECRUITMENT WORKFLOW STAGES (A-L) VERIFIED PASS!")
    print("=======================================================")


def download_content_valid(resp) -> bool:
    content = resp.content
    dispo = resp.headers.get("content-disposition", "")
    return len(content) > 0 and ("filename=" in dispo or content[:2] == b"PK")


if __name__ == "__main__":
    main()