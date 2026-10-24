import uuid
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.models import (
    Candidate,
    Interview,
    Job,
    JobApplication,
    Organization,
    Resume,
    User,
)
from app.services.errors import NotFoundError, ValidationError
from app.services.interview_service import InterviewService


def create_parent_records(
    db_session: Session,
) -> tuple[Organization, User, User, Job, JobApplication, Candidate]:
    organization = Organization(name="Interviews Org")
    db_session.add(organization)
    db_session.flush()

    user = User(
        organization_id=organization.id,
        email="interviews@example.com",
        full_name="Interview Org User",
    )
    interviewer = User(
        organization_id=organization.id,
        email="interviewer@example.com",
        full_name="Sara Ahmed",
    )
    candidate = Candidate(
        organization_id=organization.id,
        full_name="Omar Adel",
        email="omar.adel@example.com",
    )
    db_session.add_all([user, interviewer, candidate])
    db_session.flush()

    job = Job(
        organization_id=organization.id,
        created_by_user_id=user.id,
        title="Backend Developer",
    )
    resume = Resume(candidate_id=candidate.id, file_uri="local://resumes/interview-candidate.pdf")
    db_session.add_all([job, resume])
    db_session.flush()

    application = JobApplication(
        organization_id=organization.id,
        job_id=job.id,
        candidate_id=candidate.id,
        resume_id=resume.id,
        status="advanced",
    )
    db_session.add(application)
    db_session.commit()

    return organization, user, interviewer, job, application, candidate


def test_schedule_resolves_application_and_sets_fields(db_session: Session) -> None:
    organization, _user, interviewer, job, _application, _candidate = create_parent_records(
        db_session
    )
    service = InterviewService()

    interview = service.schedule(
        db_session,
        organization_id=organization.id,
        candidate_id=_candidate.id,
        job_id=job.id,
        interview_type="technical",
        scheduled_date=date(2026, 9, 9),
        scheduled_time="10:00 AM",
        interviewer_user_id=interviewer.id,
        meeting_link="https://meet.example.com/abc",
    )
    db_session.commit()

    assert interview.status == "scheduled"
    assert interview.interview_type == "technical"
    assert interview.scheduled_date == date(2026, 9, 9)
    assert interview.scheduled_time == "10:00 AM"
    assert interview.meeting_link == "https://meet.example.com/abc"
    assert interview.interviewer_user_id == interviewer.id


def test_schedule_without_application_fails(db_session: Session) -> None:
    organization, _user, interviewer, _job, _application, candidate = create_parent_records(
        db_session
    )
    other_job = Job(
        organization_id=organization.id,
        created_by_user_id=_user.id,
        title="Unrelated Job",
    )
    db_session.add(other_job)
    db_session.commit()

    with pytest.raises(ValidationError, match="Screen the candidate"):
        InterviewService().schedule(
            db_session,
            organization_id=organization.id,
            candidate_id=candidate.id,
            job_id=other_job.id,
            interview_type="technical",
            scheduled_date=date(2026, 9, 9),
            scheduled_time="10:00 AM",
            interviewer_user_id=interviewer.id,
        )


def test_schedule_rejects_interviewer_from_other_org(db_session: Session) -> None:
    organization, _user, _interviewer, job, _application, candidate = create_parent_records(
        db_session
    )
    other_org = Organization(name="Other Org")
    db_session.add(other_org)
    db_session.flush()
    other_user = User(
        organization_id=other_org.id,
        email="other@example.com",
        full_name="Other Interviewer",
    )
    db_session.add_all([other_org, other_user])
    db_session.commit()

    with pytest.raises((ValidationError, NotFoundError)):
        InterviewService().schedule(
            db_session,
            organization_id=organization.id,
            candidate_id=candidate.id,
            job_id=job.id,
            interview_type="technical",
            scheduled_date=date(2026, 9, 9),
            scheduled_time="10:00 AM",
            interviewer_user_id=other_user.id,
        )


def test_list_filters_by_status_and_scopes_to_org(db_session: Session) -> None:
    organization, _user, interviewer, job, _application, _candidate = create_parent_records(
        db_session
    )
    service = InterviewService()
    interview = service.schedule(
        db_session,
        organization_id=organization.id,
        candidate_id=_candidate.id,
        job_id=job.id,
        interview_type="hr",
        scheduled_date=date(2026, 9, 10),
        scheduled_time="11:00 AM",
        interviewer_user_id=interviewer.id,
    )
    db_session.commit()

    scheduled = service.list(db_session, organization_id=organization.id, status="scheduled")
    assert [item.id for item in scheduled] == [interview.id]
    assert service.list(db_session, organization_id=organization.id, status="completed") == []

    other_org = Organization(name="Other Org")
    db_session.add(other_org)
    db_session.commit()
    with pytest.raises((ValidationError, NotFoundError)):
        service.get(
            db_session,
            interview_id=interview.id,
            organization_id=other_org.id,
        )


def test_cancel_marks_cancelled(db_session: Session) -> None:
    organization, _user, interviewer, job, _application, _candidate = create_parent_records(
        db_session
    )
    service = InterviewService()
    interview = service.schedule(
        db_session,
        organization_id=organization.id,
        candidate_id=_candidate.id,
        job_id=job.id,
        interview_type="behavioral",
        scheduled_date=date(2026, 9, 11),
        scheduled_time="02:00 PM",
        interviewer_user_id=interviewer.id,
    )
    db_session.commit()

    service.cancel(
        db_session,
        interview_id=interview.id,
        organization_id=organization.id,
    )
    db_session.commit()
    assert db_session.get(Interview, interview.id).status == "cancelled"


def test_completed_interview_cannot_be_cancelled(db_session: Session) -> None:
    organization, _user, interviewer, job, _application, _candidate = create_parent_records(
        db_session
    )
    service = InterviewService()
    interview = service.schedule(
        db_session,
        organization_id=organization.id,
        candidate_id=_candidate.id,
        job_id=job.id,
        interview_type="technical",
        scheduled_date=date(2026, 9, 11),
        scheduled_time="02:00 PM",
        interviewer_user_id=interviewer.id,
    )
    db_session.commit()
    service.submit_feedback(
        db_session,
        interview_id=interview.id,
        organization_id=organization.id,
        feedback={"technical": 4, "communication": 5, "problem_solving": 4, "overall": 4.3},
    )
    db_session.commit()

    with pytest.raises(ValidationError, match="cannot be cancelled"):
        service.cancel(
            db_session,
            interview_id=interview.id,
            organization_id=organization.id,
        )


def test_submit_feedback_marks_completed_and_stores_payload(db_session: Session) -> None:
    organization, _user, interviewer, job, _application, _candidate = create_parent_records(
        db_session
    )
    service = InterviewService()
    interview = service.schedule(
        db_session,
        organization_id=organization.id,
        candidate_id=_candidate.id,
        job_id=job.id,
        interview_type="technical",
        scheduled_date=date(2026, 9, 11),
        scheduled_time="02:00 PM",
        interviewer_user_id=interviewer.id,
    )
    db_session.commit()

    interview = service.submit_feedback(
        db_session,
        interview_id=interview.id,
        organization_id=organization.id,
        feedback={"technical": 4, "communication": 5, "problem_solving": 4, "overall": 4.3},
    )
    db_session.commit()

    assert interview.status == "completed"
    assert interview.feedback["technical"] == 4
    assert interview.feedback["overall"] == 4.3
    assert "submitted_at" in interview.feedback


def test_cancelled_interview_rejects_feedback(db_session: Session) -> None:
    organization, _user, interviewer, job, _application, _candidate = create_parent_records(
        db_session
    )
    service = InterviewService()
    interview = service.schedule(
        db_session,
        organization_id=organization.id,
        candidate_id=_candidate.id,
        job_id=job.id,
        interview_type="technical",
        scheduled_date=date(2026, 9, 11),
        scheduled_time="02:00 PM",
        interviewer_user_id=interviewer.id,
    )
    db_session.commit()
    service.cancel(
        db_session,
        interview_id=interview.id,
        organization_id=organization.id,
    )
    db_session.commit()

    with pytest.raises(ValidationError, match="cancelled interview"):
        service.submit_feedback(
            db_session,
            interview_id=interview.id,
            organization_id=organization.id,
            feedback={"technical": 4, "communication": 5, "problem_solving": 4, "overall": 4.3},
        )


def test_to_response_includes_candidate_job_and_interviewer(db_session: Session) -> None:
    organization, _user, interviewer, job, _application, candidate = create_parent_records(
        db_session
    )
    service = InterviewService()
    interview = service.schedule(
        db_session,
        organization_id=organization.id,
        candidate_id=candidate.id,
        job_id=job.id,
        interview_type="technical",
        scheduled_date=date(2026, 9, 11),
        scheduled_time="10:00 AM",
        interviewer_user_id=interviewer.id,
    )
    db_session.commit()

    payload = service.to_response(interview)
    assert payload["candidate_id"] == candidate.id
    assert payload["candidate_name"] == "Omar Adel"
    assert payload["candidate_email"] == "omar.adel@example.com"
    assert payload["job_id"] == job.id
    assert payload["job_title"] == "Backend Developer"
    assert payload["interviewer_name"] == "Sara Ahmed"
    assert payload["status"] == "scheduled"


def test_get_missing_interview_raises_not_found(db_session: Session) -> None:
    organization, _user, _interviewer, _job, _application, _candidate = create_parent_records(
        db_session
    )
    with pytest.raises(NotFoundError, match="Interview was not found"):
        InterviewService().get(
            db_session,
            interview_id=uuid.uuid4(),
            organization_id=organization.id,
        )
