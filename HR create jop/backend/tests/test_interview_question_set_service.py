import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.models import (
    Candidate,
    CandidateProfile,
    InterviewQuestion,
    Job,
    JobApplication,
    JobProfile,
    Organization,
    Resume,
    User,
)
from app.services.errors import InvalidStateError, NotFoundError, ValidationError
from app.services.interview_question_service import InterviewQuestionService


def create_context(
    db_session: Session,
) -> tuple[Organization, User, JobApplication]:
    organization = Organization(name="Question Set Org")
    db_session.add(organization)
    db_session.flush()
    user = User(
        organization_id=organization.id,
        email="set-user@example.com",
        full_name="Set User",
    )
    candidate = Candidate(
        organization_id=organization.id,
        full_name="Set Candidate",
        email="set-candidate@example.com",
    )
    db_session.add_all([user, candidate])
    db_session.flush()
    job = Job(
        organization_id=organization.id,
        created_by_user_id=user.id,
        title="Backend Developer",
    )
    resume = Resume(candidate_id=candidate.id, file_uri="local://resumes/set.pdf")
    db_session.add_all([job, resume])
    db_session.flush()
    application = JobApplication(
        organization_id=organization.id,
        job_id=job.id,
        candidate_id=candidate.id,
        resume_id=resume.id,
    )
    db_session.add(application)
    db_session.flush()
    db_session.add(
        JobProfile(
            job_id=job.id,
            version_number=1,
            status="approved",
            source="hr_created",
            profile_data={"title": "Backend Developer", "requirements": []},
            approved_by_user_id=user.id,
            approved_at=datetime.now(UTC),
            is_current=True,
        )
    )
    db_session.add(
        CandidateProfile(
            resume_id=resume.id,
            version_number=1,
            status="current",
            source="system_extracted",
            profile_data={"skills": ["Python"]},
            is_current=True,
        )
    )
    db_session.commit()
    return organization, user, application


def sample_questions() -> list[dict]:
    return [
        {
            "category": "technical",
            "text": "Design a REST API.",
            "topic": "API",
            "requirement_key": None,
        },
        {
            "category": "behavioral",
            "text": "Tell me about a conflict at work.",
            "topic": None,
            "requirement_key": None,
        },
    ]


def create_set(db_session: Session, *, organization_id, job_application_id, status="generated"):
    return InterviewQuestionService().create_version(
        db_session,
        job_application_id=job_application_id,
        status=status,
        questions=sample_questions(),
        generated_by="fake:fake-model",
        provenance={"workflow": "interview_question_generation", "provider": "fake"},
        organization_id=organization_id,
    )


def test_create_version_persists_ordered_questions(db_session: Session) -> None:
    organization, _user, application = create_context(db_session)
    question_set = create_set(
        db_session, organization_id=organization.id, job_application_id=application.id
    )
    db_session.commit()

    assert question_set.version_number == 1
    assert question_set.status == "generated"
    assert question_set.is_current is False
    assert len(question_set.questions) == 2
    assert [q.position for q in question_set.questions] == [0, 1]


def test_generate_rejects_empty_question_set(db_session: Session) -> None:
    organization, _user, application = create_context(db_session)
    with pytest.raises(ValidationError, match="at least one question"):
        InterviewQuestionService().create_version(
            db_session,
            job_application_id=application.id,
            status="generated",
            questions=[],
            organization_id=organization.id,
        )


def test_generate_requires_valid_status(db_session: Session) -> None:
    organization, _user, application = create_context(db_session)
    with pytest.raises(ValidationError, match="status"):
        InterviewQuestionService().create_version(
            db_session,
            job_application_id=application.id,
            status="bogus",
            questions=sample_questions(),
            organization_id=organization.id,
        )


def test_approve_marks_approved_and_current(db_session: Session) -> None:
    organization, user, application = create_context(db_session)
    question_set = create_set(
        db_session, organization_id=organization.id, job_application_id=application.id
    )
    db_session.commit()

    approved = InterviewQuestionService().approve(
        db_session,
        question_set_id=question_set.id,
        approved_by_user_id=user.id,
        organization_id=organization.id,
    )
    db_session.commit()

    assert approved.status == "approved"
    assert approved.is_current is True
    assert approved.approved_by_user_id == user.id
    assert approved.approved_at is not None


def test_approve_is_version_aware_preserving_prior_sets(db_session: Session) -> None:
    organization, user, application = create_context(db_session)
    first = create_set(
        db_session, organization_id=organization.id, job_application_id=application.id
    )
    db_session.commit()
    second = InterviewQuestionService().create_version(
        db_session,
        job_application_id=application.id,
        status="generated",
        questions=sample_questions(),
        generated_by="fake:fake-model",
        organization_id=organization.id,
    )
    db_session.commit()

    InterviewQuestionService().approve(
        db_session,
        question_set_id=first.id,
        approved_by_user_id=user.id,
        organization_id=organization.id,
    )
    db_session.commit()

    db_session.refresh(first)
    db_session.refresh(second)
    assert first.status == "approved"
    assert first.is_current is True
    assert second.status == "generated"
    assert second.is_current is False


def test_double_approve_fails(db_session: Session) -> None:
    organization, user, application = create_context(db_session)
    question_set = create_set(
        db_session, organization_id=organization.id, job_application_id=application.id
    )
    InterviewQuestionService().approve(
        db_session,
        question_set_id=question_set.id,
        approved_by_user_id=user.id,
        organization_id=organization.id,
    )
    db_session.commit()

    with pytest.raises(InvalidStateError, match="already approved"):
        InterviewQuestionService().approve(
            db_session,
            question_set_id=question_set.id,
            approved_by_user_id=user.id,
            organization_id=organization.id,
        )


def test_update_edits_and_reorders_generated_set(db_session: Session) -> None:
    organization, user, application = create_context(db_session)
    question_set = create_set(
        db_session, organization_id=organization.id, job_application_id=application.id
    )
    db_session.commit()

    updated = InterviewQuestionService().update_questions(
        db_session,
        question_set_id=question_set.id,
        questions=[
            {
                "category": "behavioral",
                "text": "Tell me about a failure.",
                "topic": None,
                "requirement_key": None,
            },
            {
                "category": "situational",
                "text": "A teammate misses deadlines.",
                "topic": None,
                "requirement_key": None,
            },
        ],
        organization_id=organization.id,
    )
    db_session.commit()

    db_session.refresh(updated)
    assert len(updated.questions) == 2
    assert [q.text for q in updated.questions] == [
        "Tell me about a failure.",
        "A teammate misses deadlines.",
    ]
    assert updated.questions[0].category == "behavioral"
    assert updated.questions[1].category == "situational"


def test_cannot_edit_approved_set(db_session: Session) -> None:
    organization, user, application = create_context(db_session)
    question_set = create_set(
        db_session, organization_id=organization.id, job_application_id=application.id
    )
    InterviewQuestionService().approve(
        db_session,
        question_set_id=question_set.id,
        approved_by_user_id=user.id,
        organization_id=organization.id,
    )
    db_session.commit()

    with pytest.raises(InvalidStateError, match="cannot be edited"):
        InterviewQuestionService().update_questions(
            db_session,
            question_set_id=question_set.id,
            questions=sample_questions(),
            organization_id=organization.id,
        )


def test_get_rejects_other_org(db_session: Session) -> None:
    organization, _user, application = create_context(db_session)
    question_set = create_set(
        db_session, organization_id=organization.id, job_application_id=application.id
    )
    db_session.commit()
    other_org = Organization(name="Other Org")
    db_session.add(other_org)
    db_session.commit()

    with pytest.raises(ValidationError, match="different organization"):
        InterviewQuestionService().get(
            db_session,
            question_set_id=question_set.id,
            organization_id=other_org.id,
        )


def test_get_missing_set_raises_not_found(db_session: Session) -> None:
    organization, _user, _application = create_context(db_session)
    with pytest.raises(NotFoundError, match="InterviewQuestionSet was not found"):
        InterviewQuestionService().get(
            db_session,
            question_set_id=uuid.uuid4(),
            organization_id=organization.id,
        )


def test_list_for_application_orders_by_version(db_session: Session) -> None:
    organization, _user, application = create_context(db_session)
    first = create_set(
        db_session, organization_id=organization.id, job_application_id=application.id
    )
    db_session.commit()
    second = InterviewQuestionService().create_version(
        db_session,
        job_application_id=application.id,
        status="generated",
        questions=sample_questions(),
        generated_by="fake:fake-model",
        organization_id=organization.id,
    )
    db_session.commit()

    versions = InterviewQuestionService().list_for_application(
        db_session,
        job_application_id=application.id,
        organization_id=organization.id,
    )
    assert [v.id for v in versions] == [first.id, second.id]


def test_get_current_or_latest_prefers_current(db_session: Session) -> None:
    organization, user, application = create_context(db_session)
    first = create_set(
        db_session, organization_id=organization.id, job_application_id=application.id
    )
    db_session.commit()
    InterviewQuestionService().approve(
        db_session,
        question_set_id=first.id,
        approved_by_user_id=user.id,
        organization_id=organization.id,
    )
    InterviewQuestionService().create_version(
        db_session,
        job_application_id=application.id,
        status="generated",
        questions=sample_questions(),
        generated_by="fake:fake-model",
        organization_id=organization.id,
    )
    db_session.commit()

    current = InterviewQuestionService().get_current_or_latest(
        db_session,
        job_application_id=application.id,
        organization_id=organization.id,
    )
    assert current.id == first.id


def test_question_rows_are_replaced_on_update(db_session: Session) -> None:
    organization, _user, application = create_context(db_session)
    question_set = create_set(
        db_session, organization_id=organization.id, job_application_id=application.id
    )
    original_ids = [q.id for q in question_set.questions]
    db_session.commit()

    InterviewQuestionService().update_questions(
        db_session,
        question_set_id=question_set.id,
        questions=[
            {
                "category": "technical",
                "text": "Only one question now.",
                "topic": None,
                "requirement_key": None,
            }
        ],
        organization_id=organization.id,
    )
    db_session.commit()

    rows = (
        db_session.query(InterviewQuestion)
        .filter(InterviewQuestion.question_set_id == question_set.id)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].id not in original_ids
    assert rows[0].text == "Only one question now."
