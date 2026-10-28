from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models import (
    Candidate,
    CandidateEvaluation,
    HRDecision,
    Interview,
    Job,
    JobApplication,
    JobProfile,
    Organization,
    Resume,
    User,
)
from app.services.decision_service import DecisionService
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.services.feedback_learning_service import FeedbackLearningService
from app.services.interview_service import InterviewService
from app.services.scheduling_workflow_service import SchedulingWorkflowService


def seed_test_pipeline(
    db: Session,
) -> tuple[Organization, User, User, Job, Candidate, JobApplication]:
    """Seed complete recruitment pipeline context with job, candidate, and application."""
    org = Organization(name="End-to-End Test Org")
    db.add(org)
    db.flush()

    recruiter = User(
        organization_id=org.id,
        email="recruiter-e2e@example.com",
        full_name="Recruiter Lead",
        role="recruiter",
    )
    interviewer = User(
        organization_id=org.id,
        email="interviewer-e2e@example.com",
        full_name="Senior Engineer Layla",
        role="recruiter",
    )
    candidate = Candidate(
        organization_id=org.id,
        full_name="Zaid Tariq",
        email="zaid.tariq@example.com",
    )
    db.add_all([recruiter, interviewer, candidate])
    db.flush()

    job = Job(
        organization_id=org.id,
        created_by_user_id=recruiter.id,
        title="Full Stack Architect",
        department="Engineering",
        location="Riyadh, Saudi Arabia",
        job_type="Full-time",
        status="active",
    )
    resume = Resume(
        candidate_id=candidate.id,
        file_uri="local://resumes/zaid.pdf",
        original_filename="zaid.pdf",
    )
    db.add_all([job, resume])
    db.flush()

    application = JobApplication(
        organization_id=org.id,
        job_id=job.id,
        candidate_id=candidate.id,
        resume_id=resume.id,
        status="created",
    )
    db.add(application)
    db.commit()

    return org, recruiter, interviewer, job, candidate, application


# ===========================================================================
# STAGE G: ADVANCE GATE TESTS
# ===========================================================================


def test_advance_gate_denies_interview_scheduling_without_advance_decision(
    db_session: Session,
) -> None:
    """Stage G: An interview must not be scheduled without an authoritative 'advance' decision."""
    org, _recruiter, interviewer, job, candidate, application = seed_test_pipeline(db_session)
    service = InterviewService()

    # Application is in 'created' state
    assert application.status == "created"

    with pytest.raises(ValidationError, match="Interview scheduling denied"):
        service.schedule(
            db_session,
            organization_id=org.id,
            candidate_id=candidate.id,
            job_id=job.id,
            interview_type="technical",
            scheduled_date=date(2026, 11, 20),
            scheduled_time="10:00 AM",
            interviewer_user_id=interviewer.id,
        )


def test_advance_gate_denies_scheduling_when_application_on_hold(
    db_session: Session,
) -> None:
    """Stage G: Putting candidate on hold denies interview progression."""
    org, recruiter, interviewer, job, candidate, application = seed_test_pipeline(db_session)

    DecisionService().create(
        db_session,
        job_application_id=application.id,
        user_id=recruiter.id,
        decision="hold",
        reason="Awaiting portfolio verification",
        organization_id=org.id,
    )
    db_session.commit()

    assert application.status == "hold"

    with pytest.raises(ValidationError, match="Interview scheduling denied"):
        InterviewService().schedule(
            db_session,
            organization_id=org.id,
            candidate_id=candidate.id,
            job_id=job.id,
            interview_type="technical",
            scheduled_date=date(2026, 11, 20),
            scheduled_time="10:00 AM",
            interviewer_user_id=interviewer.id,
        )


def test_advance_gate_denies_scheduling_when_application_rejected(
    db_session: Session,
) -> None:
    """Stage G: Rejection denies interview scheduling."""
    org, recruiter, interviewer, job, candidate, application = seed_test_pipeline(db_session)

    DecisionService().create(
        db_session,
        job_application_id=application.id,
        user_id=recruiter.id,
        decision="reject",
        reason="Insufficient core criteria experience",
        organization_id=org.id,
    )
    db_session.commit()

    assert application.status == "rejected"

    with pytest.raises(ValidationError, match="Interview scheduling denied"):
        InterviewService().schedule(
            db_session,
            organization_id=org.id,
            candidate_id=candidate.id,
            job_id=job.id,
            interview_type="technical",
            scheduled_date=date(2026, 11, 20),
            scheduled_time="10:00 AM",
            interviewer_user_id=interviewer.id,
        )


def test_advance_gate_permits_scheduling_when_advance_decision_recorded(
    db_session: Session,
) -> None:
    """Stage G: Explicit authoritative advance decision permits interview scheduling."""
    org, recruiter, interviewer, job, candidate, application = seed_test_pipeline(db_session)

    DecisionService().create(
        db_session,
        job_application_id=application.id,
        user_id=recruiter.id,
        decision="advance",
        reason="Excellent profile match across all core criteria",
        organization_id=org.id,
    )
    db_session.commit()

    assert application.status == "advanced"

    interview = InterviewService().schedule(
        db_session,
        organization_id=org.id,
        candidate_id=candidate.id,
        job_id=job.id,
        interview_type="technical",
        scheduled_date=date(2026, 11, 20),
        scheduled_time="10:00 AM",
        interviewer_user_id=interviewer.id,
    )
    db_session.commit()

    assert interview.status == "scheduled"
    assert interview.scheduled_time == "10:00 AM"


def test_hold_or_reject_after_scheduling_cancels_active_interviews(
    db_session: Session,
) -> None:
    """Stage G: Transition policy: If application is put on hold or rejected after scheduling,

    scheduled interviews are automatically cancelled to prevent contradictory state.
    """
    org, recruiter, interviewer, job, candidate, application = seed_test_pipeline(db_session)

    DecisionService().create(
        db_session,
        job_application_id=application.id,
        user_id=recruiter.id,
        decision="advance",
        organization_id=org.id,
    )
    db_session.commit()

    interview = InterviewService().schedule(
        db_session,
        organization_id=org.id,
        candidate_id=candidate.id,
        job_id=job.id,
        interview_type="technical",
        scheduled_date=date(2026, 11, 20),
        scheduled_time="10:00 AM",
        interviewer_user_id=interviewer.id,
    )
    db_session.commit()
    assert interview.status == "scheduled"

    # HR later rejects application
    DecisionService().create(
        db_session,
        job_application_id=application.id,
        user_id=recruiter.id,
        decision="reject",
        reason="Position cancelled by department",
        organization_id=org.id,
    )
    db_session.commit()

    db_session.refresh(interview)
    assert interview.status == "cancelled"


# ===========================================================================
# STAGES H & I: CANDIDATE INVITATION, AVAILABILITY & SELF-BOOKING
# ===========================================================================


def test_interviewer_publishes_availability(db_session: Session) -> None:
    """Stage H: Interviewer publishes genuine availability windows."""
    org, _recruiter, interviewer, _job, _candidate, _application = seed_test_pipeline(db_session)
    workflow = SchedulingWorkflowService()

    avail = workflow.publish_availability(
        db_session,
        organization_id=org.id,
        interviewer_user_id=interviewer.id,
        scheduled_date=date(2026, 11, 25),
        start_time="09:00",
        end_time="12:00",
        duration_minutes=60,
        timezone_name="Asia/Riyadh",
    )
    db_session.commit()

    assert avail.status == "available"
    assert avail.duration_minutes == 60
    assert avail.timezone == "Asia/Riyadh"

    avail_list = workflow.list_availability(
        db_session,
        organization_id=org.id,
        scheduled_date=date(2026, 11, 25),
    )
    assert len(avail_list) == 1
    assert avail_list[0].id == avail.id


def test_candidate_invitation_enforces_advance_gate(db_session: Session) -> None:
    """Stage H: Candidate invitation generation strictly requires an advance decision."""
    org, recruiter, _interviewer, _job, _candidate, application = seed_test_pipeline(db_session)
    workflow = SchedulingWorkflowService()

    # Application is in 'created' state
    with pytest.raises(ValidationError, match="Interview scheduling denied"):
        workflow.create_invitation(
            db_session,
            organization_id=org.id,
            job_application_id=application.id,
            actor_user_id=recruiter.id,
        )

    # Now advance candidate
    DecisionService().create(
        db_session,
        job_application_id=application.id,
        user_id=recruiter.id,
        decision="advance",
        organization_id=org.id,
    )
    db_session.commit()

    issue = workflow.create_invitation(
        db_session,
        organization_id=org.id,
        job_application_id=application.id,
        actor_user_id=recruiter.id,
        expires_in_days=7,
        notes="Please select an interview slot that fits your schedule.",
    )
    db_session.commit()

    assert issue.invitation.status == "pending"
    assert len(issue.token) >= 32
    assert issue.invitation.token_hash != issue.token
    assert len(issue.invitation.token_hash) == 64
    assert issue.invitation.notes == "Please select an interview slot that fits your schedule."

    replacement = workflow.create_invitation(
        db_session,
        organization_id=org.id,
        job_application_id=application.id,
        actor_user_id=recruiter.id,
    )
    db_session.commit()
    with pytest.raises(ValidationError, match="no longer active"):
        workflow.get_candidate_view(db_session, token=issue.token)
    assert replacement.invitation.status == "pending"


def test_candidate_invitation_expires_and_withdrawn_availability_disappears(
    db_session: Session,
) -> None:
    org, recruiter, interviewer, _job, _candidate, application = seed_test_pipeline(db_session)
    workflow = SchedulingWorkflowService()
    DecisionService().create(
        db_session,
        job_application_id=application.id,
        user_id=recruiter.id,
        decision="advance",
        organization_id=org.id,
    )
    availability = workflow.publish_availability(
        db_session,
        organization_id=org.id,
        interviewer_user_id=interviewer.id,
        scheduled_date=date.today() + timedelta(days=2),
        start_time="10:00",
        end_time="11:00",
        duration_minutes=60,
        timezone_name="Africa/Cairo",
    )
    issue = workflow.create_invitation(
        db_session,
        organization_id=org.id,
        job_application_id=application.id,
        actor_user_id=recruiter.id,
    )
    db_session.commit()

    month = availability.scheduled_date.replace(day=1)
    assert workflow.list_available_slots_for_invitation(
        db_session, token=issue.token, month=month
    )
    workflow.cancel_availability(
        db_session,
        organization_id=org.id,
        availability_id=availability.id,
    )
    db_session.commit()
    assert workflow.list_available_slots_for_invitation(
        db_session, token=issue.token, month=month
    ) == []

    issue.invitation.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    with pytest.raises(ValidationError, match="expired"):
        workflow.get_candidate_view(db_session, token=issue.token)


def test_candidate_portal_view_redacts_internal_data(db_session: Session) -> None:
    """Stage H: Candidate view returns only safe role information, strictly redacting internal scores."""
    org, recruiter, _interviewer, job, candidate, application = seed_test_pipeline(db_session)
    workflow = SchedulingWorkflowService()

    DecisionService().create(
        db_session,
        job_application_id=application.id,
        user_id=recruiter.id,
        decision="advance",
        organization_id=org.id,
    )
    db_session.commit()

    issue = workflow.create_invitation(
        db_session,
        organization_id=org.id,
        job_application_id=application.id,
        actor_user_id=recruiter.id,
    )
    db_session.commit()

    view = workflow.get_candidate_view(db_session, token=issue.token)
    assert view["candidate_name"] == candidate.full_name
    assert view["job_title"] == job.title
    assert view["department"] == "Engineering"
    assert view["location"] == "Riyadh, Saudi Arabia"

    # Verify no private internals leaked
    assert "score" not in view
    assert "evaluations" not in view
    assert "traces" not in view
    assert "recommendation" not in view


def test_candidate_books_available_slot_and_prevents_double_booking(
    db_session: Session,
) -> None:
    """Stage H: Candidate selects an open slot, books it, and prevents contention/double booking."""
    org, recruiter, interviewer, job, candidate, application = seed_test_pipeline(db_session)
    workflow = SchedulingWorkflowService()

    # 1. Publish interviewer availability (9:00 - 11:00 = two 60-min slots: 09:00 and 10:00)
    workflow.publish_availability(
        db_session,
        organization_id=org.id,
        interviewer_user_id=interviewer.id,
        scheduled_date=date(2026, 11, 28),
        start_time="09:00",
        end_time="11:00",
        duration_minutes=60,
    )
    db_session.commit()

    # 2. Advance candidate and issue invitation
    DecisionService().create(
        db_session,
        job_application_id=application.id,
        user_id=recruiter.id,
        decision="advance",
        organization_id=org.id,
    )
    db_session.commit()

    issue = workflow.create_invitation(
        db_session,
        organization_id=org.id,
        job_application_id=application.id,
        actor_user_id=recruiter.id,
    )
    db_session.commit()

    # 3. Check open slots
    open_slots = workflow.list_available_slots_for_invitation(
        db_session,
        token=issue.token,
        month=date(2026, 11, 1),
    )
    assert len(open_slots) == 2
    assert open_slots[0]["start_time"] == "09:00"
    assert open_slots[1]["start_time"] == "10:00"

    with pytest.raises(ValidationError, match="Choose an interview time shown as available"):
        workflow.candidate_book_slot(
            db_session,
            token=issue.token,
            availability_id=open_slots[0]["availability_id"],
            scheduled_time="09:30",
        )

    # 4. Candidate books 09:00 slot
    booked_interview = workflow.candidate_book_slot(
        db_session,
        token=issue.token,
        availability_id=open_slots[0]["availability_id"],
        scheduled_time="09:00",
    )
    db_session.commit()

    assert booked_interview.status == "scheduled"
    assert booked_interview.scheduled_time == "09:00"

    db_session.refresh(issue.invitation)
    assert issue.invitation.status == "booked"

    # A used invitation cannot be reused to inspect or book another slot.
    remaining_slots = workflow.list_available_slots_for_invitation(
        db_session,
        token=issue.token,
        month=date(2026, 11, 1),
    )
    assert remaining_slots == []

    # 6. Attempting to book the occupied 09:00 slot fails with ConflictError (409)
    # Create another candidate & invitation
    cand2 = Candidate(organization_id=org.id, full_name="Ali", email="ali@test.com")
    db_session.add(cand2)
    db_session.flush()
    res2 = Resume(candidate_id=cand2.id, file_uri="local://res/ali.pdf")
    db_session.add(res2)
    db_session.flush()
    app2 = JobApplication(
        organization_id=org.id,
        job_id=job.id,
        candidate_id=cand2.id,
        resume_id=res2.id,
        status="advanced",
    )
    db_session.add(app2)
    db_session.commit()

    inv2 = workflow.create_invitation(
        db_session,
        organization_id=org.id,
        job_application_id=app2.id,
        actor_user_id=recruiter.id,
    )
    db_session.commit()

    with pytest.raises(ConflictError, match="Schedule conflict"):
        workflow.candidate_book_slot(
            db_session,
            token=inv2.token,
            availability_id=open_slots[0]["availability_id"],
            scheduled_time="09:00",
        )


def test_candidate_invitation_is_single_booking_and_requires_hr_reissue_to_reschedule(db_session: Session) -> None:
    """Stage I: HR must cancel a booked interview before issuing a replacement link."""
    org, recruiter, interviewer, job, candidate, application = seed_test_pipeline(db_session)
    workflow = SchedulingWorkflowService()

    workflow.publish_availability(
        db_session,
        organization_id=org.id,
        interviewer_user_id=interviewer.id,
        scheduled_date=date(2026, 11, 29),
        start_time="13:00",
        end_time="15:00",
        duration_minutes=60,
    )
    DecisionService().create(
        db_session,
        job_application_id=application.id,
        user_id=recruiter.id,
        decision="advance",
        organization_id=org.id,
    )
    issue = workflow.create_invitation(
        db_session,
        organization_id=org.id,
        job_application_id=application.id,
        actor_user_id=recruiter.id,
    )
    db_session.commit()

    slots = workflow.list_available_slots_for_invitation(
        db_session, token=issue.token, month=date(2026, 11, 1)
    )
    # Book 13:00
    interview = workflow.candidate_book_slot(
        db_session,
        token=issue.token,
        availability_id=slots[0]["availability_id"],
        scheduled_time="13:00",
    )
    db_session.commit()
    assert interview.status == "scheduled"

    # The same public link cannot cancel or move the booked interview.
    with pytest.raises(ValidationError, match="already been used"):
        workflow.candidate_book_slot(
            db_session,
            token=issue.token,
            availability_id=slots[1]["availability_id"],
            scheduled_time="14:00",
        )
    view = workflow.get_candidate_view(db_session, token=issue.token)
    assert view["scheduled_time"] == interview.scheduled_time

    with pytest.raises(ConflictError, match="Cancel it before issuing a replacement link"):
        workflow.create_invitation(
            db_session,
            organization_id=org.id,
            job_application_id=application.id,
            actor_user_id=recruiter.id,
        )

    InterviewService().cancel(
        db_session,
        interview_id=interview.id,
        organization_id=org.id,
    )
    replacement = workflow.create_invitation(
        db_session,
        organization_id=org.id,
        job_application_id=application.id,
        actor_user_id=recruiter.id,
    )
    db_session.commit()
    assert replacement.invitation.status == "pending"


# ===========================================================================
# STAGE J: INTERVIEW FEEDBACK VALIDATION & SUBSEQUENT DECISION
# ===========================================================================


def test_interview_feedback_validation_and_subsequent_decision(
    db_session: Session,
) -> None:
    """Stage J: Submitting feedback validates rating dimensions and enables next hiring decision."""
    org, recruiter, interviewer, job, candidate, application = seed_test_pipeline(db_session)
    DecisionService().create(
        db_session,
        job_application_id=application.id,
        user_id=recruiter.id,
        decision="advance",
        organization_id=org.id,
    )
    interview = InterviewService().schedule(
        db_session,
        organization_id=org.id,
        candidate_id=candidate.id,
        job_id=job.id,
        interview_type="technical",
        scheduled_date=date(2026, 11, 20),
        scheduled_time="10:00 AM",
        interviewer_user_id=interviewer.id,
    )
    db_session.commit()

    # Invalid rating (out of range 1-5)
    with pytest.raises(ValidationError, match="technical rating must be between 1 and 5"):
        InterviewService().submit_feedback(
            db_session,
            interview_id=interview.id,
            organization_id=org.id,
            feedback={
                "technical": 6,
                "communication": 4,
                "problem_solving": 4,
                "overall": 4.5,
            },
        )

    # Valid feedback
    valid_feedback = {
        "technical": 5,
        "communication": 4,
        "problem_solving": 5,
        "overall": 4.7,
        "comments": "Outstanding architecture design and distributed systems answers.",
        "recommendation": "advance",
        "strengths": ["System design", "Python concurrency", "PostgreSQL tuning"],
        "concerns": [],
    }
    completed_interview = InterviewService().submit_feedback(
        db_session,
        interview_id=interview.id,
        organization_id=org.id,
        feedback=valid_feedback,
    )
    db_session.commit()

    assert completed_interview.status == "completed"
    assert completed_interview.feedback["overall"] == 4.7

    # Prevent accidental duplicate overwrite without explicit amendment flag
    with pytest.raises(ValidationError, match="Feedback has already been submitted"):
        InterviewService().submit_feedback(
            db_session,
            interview_id=interview.id,
            organization_id=org.id,
            feedback=valid_feedback,
            is_amendment=False,
        )

    # Amendment works and preserves history
    amended_feedback = dict(valid_feedback)
    amended_feedback["overall"] = 4.9
    amended = InterviewService().submit_feedback(
        db_session,
        interview_id=interview.id,
        organization_id=org.id,
        feedback=amended_feedback,
        is_amendment=True,
    )
    db_session.commit()
    assert amended.feedback["overall"] == 4.9
    assert len(amended.feedback["_history"]) == 1
    assert amended.feedback["_history"][0]["overall"] == 4.7

    # Post-interview subsequent HR decision: Advance to Offer!
    offer_decision = DecisionService().create(
        db_session,
        job_application_id=application.id,
        user_id=recruiter.id,
        decision="advance",
        reason="Interview feedback scored 4.9/5; extending formal employment offer.",
        organization_id=org.id,
    )
    db_session.commit()
    assert offer_decision.decision == "advance"


# ===========================================================================
# STAGE K: HR FEEDBACK LEARNING LOOP TESTS
# ===========================================================================


def test_feedback_learning_loop_records_corrections_and_analytics(
    db_session: Session,
) -> None:
    """Stage K: Controlled learning loop captures corrections and computes override rates."""
    org, recruiter, _interviewer, job, _candidate, application = seed_test_pipeline(db_session)
    feedback_service = FeedbackLearningService()

    # 1. Record an extraction correction
    c1 = feedback_service.record_correction(
        db_session,
        organization_id=org.id,
        user_id=recruiter.id,
        correction_type="extraction_correction",
        job_id=job.id,
        original_ai_output={"extracted_skills": ["Java"]},
        hr_corrected_result={"extracted_skills": ["Java", "Spring Boot"]},
        reason="CV explicitly mentioned Spring Boot in Project 2",
    )
    # 2. Record a recommendation override
    c2 = feedback_service.record_correction(
        db_session,
        organization_id=org.id,
        user_id=recruiter.id,
        correction_type="recommendation_override",
        job_id=job.id,
        original_ai_output={"recommendation": "needs_review"},
        hr_corrected_result={"recommendation": "advance"},
        reason="Strong open source GitHub portfolio overrides missing credential",
    )
    # 3. Record a requirement match correction
    c3 = feedback_service.record_correction(
        db_session,
        organization_id=org.id,
        user_id=recruiter.id,
        correction_type="requirement_match_correction",
        job_id=job.id,
        original_ai_output={"requirement": "FastAPI", "match": "missing"},
        hr_corrected_result={"requirement": "FastAPI", "match": "matched"},
        reason="Candidate built REST APIs with Python/FastAPI",
    )
    db_session.commit()

    assert c1.id is not None
    assert c2.id is not None
    assert c3.id is not None

    # Check analytics
    analytics = feedback_service.get_analytics(db_session, organization_id=org.id)
    assert analytics["total_corrections"] == 3
    assert analytics["extraction_error_count"] == 1
    assert analytics["requirement_match_correction_count"] == 1
    assert analytics["corrections_by_type"]["recommendation_override"] == 1
    assert analytics["recommendation_override_rate_pct"] == 33.33


def test_feedback_learning_propose_skill_alias_and_benchmark(
    db_session: Session,
) -> None:
    """Stage K: Approved correction dynamically extends technical synonyms and evaluates benchmark."""
    org, recruiter, _interviewer, _job, _candidate, _application = seed_test_pipeline(db_session)
    feedback_service = FeedbackLearningService()

    # Propose new technical synonym: "k8s" -> "kubernetes"
    res = feedback_service.propose_skill_alias(
        db_session,
        organization_id=org.id,
        user_id=recruiter.id,
        alias="k8s",
        canonical_skill="kubernetes",
        reason="Common industry abbreviation",
    )
    db_session.commit()

    assert res["status"] == "activated"
    assert "k8s" in res["synonyms"]

    # Controlled evaluation against validation cases
    benchmark_cases = [
        {"text": "Experienced in deploying services to k8s clusters", "term": "kubernetes", "expected": True},
        {"text": "Built web applications using React and Python", "term": "python", "expected": True},
        {"text": "Marketing manager with SEO skills", "term": "kubernetes", "expected": False},
    ]

    eval_result = feedback_service.evaluate_rules_on_dataset(
        db_session,
        organization_id=org.id,
        test_cases=benchmark_cases,
    )
    assert eval_result["total_evaluated"] == 3
    assert eval_result["matches"] == 3
    assert eval_result["accuracy_pct"] == 100.0
    assert eval_result["ready_for_release"] is True
