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
from app.services.errors import ConflictError, ValidationError
from app.services.interview_question_service import InterviewQuestionService
from app.services.interview_service import InterviewService


def create_parent_records(
    db_session: Session,
    *,
    org_name: str = "Conflicts Org",
    candidate_name: str = "Conflict Candidate",
) -> tuple[Organization, User, User, Job, JobApplication, Candidate]:
    organization = Organization(name=org_name)
    db_session.add(organization)
    db_session.flush()

    user = User(
        organization_id=organization.id,
        email=f"owner-{uuid.uuid4().hex}@example.com",
        full_name="Conflict Org User",
    )
    interviewer = User(
        organization_id=organization.id,
        email=f"interviewer-{uuid.uuid4().hex}@example.com",
        full_name="Sara Ahmed",
    )
    candidate = Candidate(
        organization_id=organization.id,
        full_name=candidate_name,
        email=f"candidate-{uuid.uuid4().hex}@example.com",
    )
    db_session.add_all([user, interviewer, candidate])
    db_session.flush()

    job = Job(
        organization_id=organization.id,
        created_by_user_id=user.id,
        title="Backend Developer",
    )
    resume = Resume(candidate_id=candidate.id, file_uri="local://resumes/conflict.pdf")
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


def schedule(
    db_session: Session,
    *,
    organization_id: uuid.UUID,
    application: JobApplication,
    interviewer_user_id: uuid.UUID,
    scheduled_time: str,
    scheduled_date: date = date(2026, 9, 9),
    scheduled_duration_minutes: int = 60,
) -> Interview:
    return InterviewService().schedule(
        db_session,
        organization_id=organization_id,
        candidate_id=application.candidate_id,
        job_id=application.job_id,
        interview_type="technical",
        scheduled_date=scheduled_date,
        scheduled_time=scheduled_time,
        interviewer_user_id=interviewer_user_id,
        scheduled_duration_minutes=scheduled_duration_minutes,
    )


def create_second_application(
    db_session: Session,
    *,
    organization_id: uuid.UUID,
    job_id: uuid.UUID,
) -> JobApplication:
    second_candidate = Candidate(
        organization_id=organization_id,
        full_name="Second Conflict Candidate",
        email=f"sc2-{uuid.uuid4().hex}@example.com",
    )
    db_session.add(second_candidate)
    db_session.commit()
    second_resume = Resume(candidate_id=second_candidate.id, file_uri="local://resumes/sc2.pdf")
    db_session.add(second_resume)
    db_session.commit()
    second_application = JobApplication(
        organization_id=organization_id,
        job_id=job_id,
        candidate_id=second_candidate.id,
        resume_id=second_resume.id,
        status="advanced",
    )
    db_session.add(second_application)
    db_session.commit()
    return second_application


def test_same_interviewer_same_slot_conflicts(db_session: Session) -> None:
    organization, _user, interviewer, job, application, _candidate = create_parent_records(
        db_session
    )
    schedule(
        db_session,
        organization_id=organization.id,
        application=application,
        interviewer_user_id=interviewer.id,
        scheduled_time="10:00 AM",
    )
    db_session.commit()

    second_application = create_second_application(
        db_session, organization_id=organization.id, job_id=job.id
    )
    with pytest.raises(ConflictError, match="Sara Ahmed is already booked"):
        schedule(
            db_session,
            organization_id=organization.id,
            application=second_application,
            interviewer_user_id=interviewer.id,
            scheduled_time="10:00 AM",
        )


def test_same_interviewer_overlap_conflicts(db_session: Session) -> None:
    organization, _user, interviewer, _job, application, candidate = create_parent_records(
        db_session
    )
    schedule(
        db_session,
        organization_id=organization.id,
        application=application,
        interviewer_user_id=interviewer.id,
        scheduled_time="10:00 AM",
        scheduled_duration_minutes=60,
    )
    db_session.commit()

    with pytest.raises(ConflictError):
        schedule(
            db_session,
            organization_id=organization.id,
            application=application,
            interviewer_user_id=interviewer.id,
            scheduled_time="10:30 AM",
            scheduled_duration_minutes=60,
        )
    with pytest.raises(ConflictError):
        schedule(
            db_session,
            organization_id=organization.id,
            application=application,
            interviewer_user_id=interviewer.id,
            scheduled_time="10:45 AM",
        )


def test_back_to_back_interviews_do_not_conflict(db_session: Session) -> None:
    organization, _user, interviewer, _job, application, candidate = create_parent_records(
        db_session
    )
    schedule(
        db_session,
        organization_id=organization.id,
        application=application,
        interviewer_user_id=interviewer.id,
        scheduled_time="10:00 AM",
        scheduled_duration_minutes=60,
    )
    db_session.commit()

    second = schedule(
        db_session,
        organization_id=organization.id,
        application=application,
        interviewer_user_id=interviewer.id,
        scheduled_time="11:00 AM",
        scheduled_duration_minutes=60,
    )
    db_session.commit()
    assert second.status == "scheduled"


def test_same_candidate_different_interviewer_conflicts(db_session: Session) -> None:
    organization, _user, interviewer, _job, application, candidate = create_parent_records(
        db_session
    )
    second_interviewer = User(
        organization_id=organization.id,
        email=f"i2-{uuid.uuid4().hex}@example.com",
        full_name="Khalid Hassan",
    )
    db_session.add(second_interviewer)
    db_session.commit()

    schedule(
        db_session,
        organization_id=organization.id,
        application=application,
        interviewer_user_id=interviewer.id,
        scheduled_time="10:00 AM",
    )
    db_session.commit()

    with pytest.raises(ConflictError, match="Schedule conflict"):
        schedule(
            db_session,
            organization_id=organization.id,
            application=application,
            interviewer_user_id=second_interviewer.id,
            scheduled_time="10:00 AM",
        )


def test_same_candidate_across_different_jobs_conflicts(db_session: Session) -> None:
    organization, _user, interviewer, _job, application, candidate = create_parent_records(
        db_session
    )
    second_interviewer = User(
        organization_id=organization.id,
        email=f"i4-{uuid.uuid4().hex}@example.com",
        full_name="Khalid Hassan",
    )
    db_session.add(second_interviewer)
    db_session.commit()

    second_job = Job(
        organization_id=organization.id,
        created_by_user_id=_user.id,
        title="Second Developer Role",
    )
    second_resume = Resume(candidate_id=candidate.id, file_uri="local://resumes/conflict2.pdf")
    db_session.add_all([second_job, second_resume])
    db_session.commit()
    second_application = JobApplication(
        organization_id=organization.id,
        job_id=second_job.id,
        candidate_id=candidate.id,
        resume_id=second_resume.id,
        status="advanced",
    )
    db_session.add(second_application)
    db_session.commit()

    schedule(
        db_session,
        organization_id=organization.id,
        application=application,
        interviewer_user_id=interviewer.id,
        scheduled_time="10:00 AM",
    )
    db_session.commit()

    with pytest.raises(ConflictError, match="candidate Conflict Candidate is already booked"):
        schedule(
            db_session,
            organization_id=organization.id,
            application=second_application,
            interviewer_user_id=second_interviewer.id,
            scheduled_time="10:30 AM",
            scheduled_duration_minutes=60,
        )


def test_conflicts_respect_organization_isolation(db_session: Session) -> None:
    organization, _user, interviewer, _job, application, _candidate = create_parent_records(
        db_session, org_name="Isolation Org One"
    )
    other_org, _other_user, other_interviewer, _job2, application2, _candidate2 = (
        create_parent_records(db_session, org_name="Isolation Org Two")
    )

    schedule(
        db_session,
        organization_id=organization.id,
        application=application,
        interviewer_user_id=interviewer.id,
        scheduled_time="10:00 AM",
    )
    db_session.commit()

    interview = schedule(
        db_session,
        organization_id=other_org.id,
        application=application2,
        interviewer_user_id=other_interviewer.id,
        scheduled_time="10:00 AM",
    )
    db_session.commit()
    assert interview.status == "scheduled"


def test_different_candidate_and_interviewer_schedule_fine(db_session: Session) -> None:
    organization, _user, interviewer, _job, application, candidate = create_parent_records(
        db_session
    )
    second_interviewer = User(
        organization_id=organization.id,
        email=f"i3-{uuid.uuid4().hex}@example.com",
        full_name="Layla Nasser",
    )
    db_session.add(second_interviewer)
    db_session.commit()
    second_candidate = Candidate(
        organization_id=organization.id,
        full_name="Second Candidate",
        email=f"sc-{uuid.uuid4().hex}@example.com",
    )
    db_session.add(second_candidate)
    db_session.commit()
    second_resume = Resume(candidate_id=second_candidate.id, file_uri="local://resumes/s2.pdf")
    db_session.add(second_resume)
    db_session.commit()
    second_application = JobApplication(
        organization_id=organization.id,
        job_id=application.job_id,
        candidate_id=second_candidate.id,
        resume_id=second_resume.id,
        status="advanced",
    )
    db_session.add(second_application)
    db_session.commit()

    schedule(
        db_session,
        organization_id=organization.id,
        application=application,
        interviewer_user_id=interviewer.id,
        scheduled_time="10:00 AM",
    )
    db_session.commit()

    interview = schedule(
        db_session,
        organization_id=organization.id,
        application=second_application,
        interviewer_user_id=second_interviewer.id,
        scheduled_time="10:00 AM",
    )
    db_session.commit()
    assert interview.status == "scheduled"


def test_cancelled_interviews_do_not_conflict(db_session: Session) -> None:
    organization, _user, interviewer, _job, application, candidate = create_parent_records(
        db_session
    )
    existing = schedule(
        db_session,
        organization_id=organization.id,
        application=application,
        interviewer_user_id=interviewer.id,
        scheduled_time="10:00 AM",
    )
    db_session.commit()
    InterviewService().cancel(
        db_session,
        interview_id=existing.id,
        organization_id=organization.id,
    )
    db_session.commit()

    new = schedule(
        db_session,
        organization_id=organization.id,
        application=application,
        interviewer_user_id=interviewer.id,
        scheduled_time="10:00 AM",
    )
    db_session.commit()
    assert new.status == "scheduled"


def test_find_conflicts_returns_overlapping_interviews(db_session: Session) -> None:
    organization, _user, interviewer, _job, application, candidate = create_parent_records(
        db_session
    )
    existing = schedule(
        db_session,
        organization_id=organization.id,
        application=application,
        interviewer_user_id=interviewer.id,
        scheduled_time="10:00 AM",
        scheduled_duration_minutes=90,
    )
    db_session.commit()

    conflicts = InterviewService().find_conflicts(
        db_session,
        organization_id=organization.id,
        job_application_id=application.id,
        candidate_id=application.candidate_id,
        interviewer_user_id=interviewer.id,
        scheduled_date=date(2026, 9, 9),
        start_minutes=630,
        duration_minutes=30,
    )
    assert [c.id for c in conflicts] == [existing.id]


def test_schedule_rejects_invalid_duration(db_session: Session) -> None:
    organization, _user, interviewer, _job, application, candidate = create_parent_records(
        db_session
    )
    with pytest.raises(ValidationError, match="between 15 and 480"):
        schedule(
            db_session,
            organization_id=organization.id,
            application=application,
            interviewer_user_id=interviewer.id,
            scheduled_time="10:00 AM",
            scheduled_duration_minutes=10,
        )
    with pytest.raises(ValidationError, match="between 15 and 480"):
        schedule(
            db_session,
            organization_id=organization.id,
            application=application,
            interviewer_user_id=interviewer.id,
            scheduled_time="10:00 AM",
            scheduled_duration_minutes=600,
        )


def test_schedule_persists_custom_duration(db_session: Session) -> None:
    organization, _user, interviewer, _job, application, candidate = create_parent_records(
        db_session
    )
    interview = schedule(
        db_session,
        organization_id=organization.id,
        application=application,
        interviewer_user_id=interviewer.id,
        scheduled_time="10:00 AM",
        scheduled_duration_minutes=45,
    )
    db_session.commit()
    assert interview.scheduled_duration_minutes == 45


def test_list_slots_for_date_returns_occupied_windows(db_session: Session) -> None:
    organization, _user, interviewer, _job, application, candidate = create_parent_records(
        db_session
    )
    schedule(
        db_session,
        organization_id=organization.id,
        application=application,
        interviewer_user_id=interviewer.id,
        scheduled_time="10:00 AM",
        scheduled_duration_minutes=60,
    )
    db_session.commit()

    slots = InterviewService().list_slots_for_date(
        db_session,
        organization_id=organization.id,
        scheduled_date=date(2026, 9, 9),
        interviewer_user_id=interviewer.id,
    )
    assert slots == [
        {
            "interview_id": slots[0]["interview_id"],
            "interviewer_user_id": interviewer.id,
            "start_minutes": 600,
            "end_minutes": 660,
            "start_time": "10:00",
            "end_time": "11:00",
        },
    ]


def test_schedule_rejects_question_set_from_another_application(db_session: Session) -> None:
    organization, _user, interviewer, job, application, _candidate = create_parent_records(
        db_session
    )
    other_candidate = Candidate(
        organization_id=organization.id,
        full_name="Different Candidate",
        email=f"dc-{uuid.uuid4().hex}@example.com",
    )
    db_session.add(other_candidate)
    db_session.commit()
    other_resume = Resume(candidate_id=other_candidate.id, file_uri="local://resumes/dc.pdf")
    db_session.add(other_resume)
    db_session.commit()
    other_application = JobApplication(
        organization_id=organization.id,
        job_id=job.id,
        candidate_id=other_candidate.id,
        resume_id=other_resume.id,
    )
    db_session.add(other_application)
    db_session.commit()

    foreign_set = InterviewQuestionService().create_version(
        db_session,
        job_application_id=other_application.id,
        status="generated",
        questions=[{"category": "technical", "text": "Q", "topic": None}],
        generated_by="fake:fake-model",
        organization_id=organization.id,
    )
    db_session.commit()

    with pytest.raises(ValidationError, match="does not belong"):
        InterviewService().schedule(
            db_session,
            organization_id=organization.id,
            candidate_id=application.candidate_id,
            job_id=application.job_id,
            interview_type="technical",
            scheduled_date=date(2026, 9, 9),
            scheduled_time="10:00 AM",
            interviewer_user_id=interviewer.id,
            interview_question_set_id=foreign_set.id,
        )


def test_schedule_rejects_unapproved_question_set(db_session: Session) -> None:
    organization, user, interviewer, _job, application, _candidate = create_parent_records(
        db_session
    )
    generated_set = InterviewQuestionService().create_version(
        db_session,
        job_application_id=application.id,
        status="generated",
        questions=[{"category": "technical", "text": "Q", "topic": None}],
        generated_by="fake:fake-model",
        organization_id=organization.id,
    )
    db_session.commit()

    with pytest.raises(ValidationError, match="approved interview question set"):
        InterviewService().schedule(
            db_session,
            organization_id=organization.id,
            candidate_id=application.candidate_id,
            job_id=application.job_id,
            interview_type="technical",
            scheduled_date=date(2026, 9, 9),
            scheduled_time="10:00 AM",
            interviewer_user_id=interviewer.id,
            interview_question_set_id=generated_set.id,
        )

    approved = InterviewQuestionService().approve(
        db_session,
        question_set_id=generated_set.id,
        approved_by_user_id=user.id,
        organization_id=organization.id,
    )
    db_session.commit()

    interview = InterviewService().schedule(
        db_session,
        organization_id=organization.id,
        candidate_id=application.candidate_id,
        job_id=application.job_id,
        interview_type="technical",
        scheduled_date=date(2026, 9, 9),
        scheduled_time="10:00 AM",
        interviewer_user_id=interviewer.id,
        interview_question_set_id=approved.id,
    )
    db_session.commit()
    assert interview.interview_question_set_id == approved.id
