"""Live AI screening verification against the real OpenRouter provider.

Runs stages A-D of the e2e flow in-process (SQLite StaticPool + TestClient) but
with AI_PROVIDER=openrouter so extraction/scoring calls hit the real model.
Deliberately minimal: 2 tiny CVs only, then reads AIUsageEvent rows to report
the exact credit spent.

Usage:
    cd backend && OPENROUTER_API_KEY=sk-or-... .venv/bin/python ../tools/live_openrouter_screening_check.py

Never prints the API key.
"""
from __future__ import annotations

import io
import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Config must be set before app modules read settings.
os.environ.setdefault("JWT_SECRET_KEY", "hera-dev-jwt-secret-key-explicitly-configured-32bytes")
if not os.environ.get("OPENROUTER_API_KEY") and os.environ.get("AI_PROVIDER", "openrouter") == "openrouter":
    print("ERROR: OPENROUTER_API_KEY not set in environment.", file=sys.stderr)
    sys.exit(2)
os.environ.setdefault("AI_PROVIDER", "openrouter")
os.environ.setdefault("OPENROUTER_MODEL", "deepseek/deepseek-v4.1-flash-1017")
os.environ.setdefault("OPENROUTER_MAX_TOKENS", "4096")

ORG_ID = "09df6372-c821-4c6f-b633-9f9fe8438f85"
USER_ID = "76598a7a-f0bc-4531-ad74-e232a3e30a53"
HEADERS = {"X-Organization-Id": ORG_ID, "X-User-Id": USER_ID}

# Abort the live run below this remaining balance (USD): the key's credit is
# reserved for real app users; the whole check costs well under $0.02.
MIN_REMAINING_BALANCE_USD = 0.05

FAILURES: list[str] = []


def fetch_key_balance() -> dict:
    """Read the OpenRouter key's usage and remaining limit (no inference call)."""
    import httpx

    resp = httpx.get(
        "https://openrouter.ai/api/v1/auth/key",
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("data") or {}


def print_balance(label: str, data: dict) -> float | None:
    usage = data.get("usage")
    limit = data.get("limit")
    remaining = data.get("limit_remaining")
    free_tier = data.get("is_free_tier")
    print(
        f"[BALANCE {label}] usage={usage} limit={limit} "
        f"limit_remaining={remaining} is_free_tier={free_tier}"
    )
    return float(remaining) if remaining is not None else None


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}: {name}" + (f" | {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)


def build_client():
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.core.database import Base, get_db
    from app.main import app
    from app.models import Organization, User

    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()

    org_uuid = uuid.UUID(ORG_ID)
    user_uuid = uuid.UUID(USER_ID)
    if not session.get(Organization, org_uuid):
        session.add(Organization(id=org_uuid, name="HERA Live Check Org"))
        session.flush()
    if not session.get(User, user_uuid):
        session.add(User(
            id=user_uuid,
            organization_id=org_uuid,
            email="hera-live-check@example.com",
            full_name="HERA Live Checker",
            role="recruiter",
        ))
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
    client = TestClient(app, base_url="http://testserver/api/v1")
    client.headers.update(HEADERS)
    return client, TestingSession


def make_docx_bytes() -> bytes:
    from docx import Document
    text = [
        "Ada Lovelace",
        "ada.lovelace@example.com",
        "SKILLS: Python, Postgres, Docker, Kubernetes, Machine Learning",
        "EXPERIENCE: Senior Data Engineer, 5 years",
        "EDUCATION: MSc Data Science",
    ]
    doc = Document()
    for line in text:
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_pdf_bytes() -> bytes:
    text = "Grace Hopper - engineer, Python, Data Structures, Algorithms, 4 years experience."
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


def main() -> None:
    from app.core.config import settings

    print(f"[INFO] provider={settings.ai_provider} model={settings.openrouter_model} max_tokens={settings.openrouter_max_tokens}")

    # Credit guard: report the key's balance BEFORE any screening call.
    if os.environ.get("AI_PROVIDER", "openrouter") == "openrouter":
        before = print_balance("BEFORE", fetch_key_balance())
        if "--balance-only" in sys.argv:
            sys.exit(0)
        if before is not None and before < MIN_REMAINING_BALANCE_USD:
            print(
                f"ABORT: remaining balance ${before} is below the "
                f"${MIN_REMAINING_BALANCE_USD} safety floor; no screening calls made."
            )
            sys.exit(3)

    client, TestingSession = build_client()

    # Stage A: job draft
    job_payload = {
        "title": "Live Check Data Engineer",
        "status": "draft",
        "job_type": "full_time",
        "department": "Infrastructure",
        "location": "London, UK (Hybrid)",
        "raw_description": "Build data pipelines with Python, Postgres and Docker.",
        "required_skills": ["Python", "Postgres", "Docker"],
        "requirements": ["Kubernetes"],
        "experience": "3+ years",
    }
    job_resp = client.post("/jobs", json=job_payload)
    check("A: create job draft", job_resp.status_code == 201, f"status={job_resp.status_code}")
    job_id = job_resp.json()["id"]

    # Stage B: profile + approve + activate
    profile_payload = {
        "status": "draft",
        "source": "ai_extracted",
        "profile_data": {
            "title": job_payload["title"],
            "required_skills": ["Python", "Postgres", "Docker"],
            "requirements": [
                {"text": "Python", "category": "must_have", "dimension": "skill"},
                {"text": "Postgres", "category": "important", "dimension": "skill"},
                {"text": "Docker", "category": "nice_to_have", "dimension": "skill"},
            ],
        },
        "raw_input_snapshot": {"raw_description": job_payload["raw_description"]},
    }
    profile_resp = client.post(f"/jobs/{job_id}/profiles", json=profile_payload)
    check("B: create profile", profile_resp.status_code == 201, f"status={profile_resp.status_code}")
    profile_id = profile_resp.json()["id"]
    approve_resp = client.post(f"/job-profiles/{profile_id}/approve")
    check("B: approve profile", approve_resp.status_code == 200, f"status={approve_resp.status_code}")
    activate_resp = client.patch(f"/jobs/{job_id}", json={"status": "active"})
    check("B: activate job", activate_resp.status_code == 200, f"status={activate_resp.status_code}")

    # Stage C/D: screen two tiny CVs against the real model
    screen_resp = client.post(
        f"/jobs/{job_id}/screen",
        files=[
            ("files", ("ada-cv.docx", make_docx_bytes(),
                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
            ("files", ("grace-cv.pdf", make_pdf_bytes(), "application/pdf")),
        ],
    )
    check("C: screen 2 CVs", screen_resp.status_code == 201,
          f"status={screen_resp.status_code} body={screen_resp.text[:300]}")
    if screen_resp.status_code != 201:
        print("Aborting: screening call failed.")
        sys.exit(1)
    rows = screen_resp.json()["screened"]
    check("C: 2 results", len(rows) == 2, f"rows={len(rows)}")
    for idx, row in enumerate(rows):
        score = float(row["score"])
        check(f"D: score positive (row {idx + 1})", score > 0, f"score={score}")

        # Extracted profile via real provider
        profiles_resp = client.get(f"/resumes/{row['resume_id']}/profiles")
        check(f"D: profile endpoint (row {idx + 1})", profiles_resp.status_code == 200,
              f"status={profiles_resp.status_code}")
        profiles_list = profiles_resp.json()
        check(f"D: profile extracted (row {idx + 1})", len(profiles_list) >= 1)
        if profiles_list:
            cp = profiles_list[0].get("profile_data") or {}
            name = cp.get("full_name") or "?"
            skills = cp.get("skills") or []
            print(f"    row {idx + 1}: extracted name={name} email={cp.get('email')} "
                  f"skills={len(skills)} -> {skills[:6]}")
            check(f"D: skills extracted (row {idx + 1})", len(skills) >= 1, f"skills={skills[:6]}")

        # Evidence attached to evaluation
        ev_resp = client.get(f"/evaluations/{row['evaluation_id']}/evidence")
        check(f"D: evidence endpoint (row {idx + 1})", ev_resp.status_code == 200,
              f"status={ev_resp.status_code}")
        if ev_resp.status_code == 200:
            ev_items = ev_resp.json()
            check(f"D: evidence attached (row {idx + 1})", len(ev_items) >= 1,
                  f"items={len(ev_items)}")
            for item in ev_items[:3]:
                print(f"    evidence: type={item.get('evidence_type')} req={item.get('requirement_text')!r:.60}")

    # Credit usage: read the metering table
    from app.models.ai_usage import AIUsageEvent

    session = TestingSession()
    events = session.query(AIUsageEvent).all()
    total = Decimal("0")
    print("\n--- AI usage events (real OpenRouter calls) ---")
    for ev in events:
        cost = ev.reported_cost_usd if ev.reported_cost_usd is not None else Decimal("0")
        total += cost
        print(
            f"    feature={ev.feature} model={ev.model} status={ev.status} "
            f"in={ev.input_tokens} out={ev.output_tokens} cost_usd={ev.reported_cost_usd}"
        )
    print(f"--- TOTAL reported cost this run: ${total} ({len(events)} model calls) ---")

    if os.environ.get("AI_PROVIDER", "openrouter") == "openrouter":
        print_balance("AFTER", fetch_key_balance())

    print("\nRESULT:", "ALL CHECKS PASSED" if not FAILURES else f"FAILURES: {FAILURES}")
    sys.exit(0 if not FAILURES else 1)


if __name__ == "__main__":
    main()
