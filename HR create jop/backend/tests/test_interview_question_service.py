import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.models import (
    Candidate,
    CandidateEvaluation,
    CandidateProfile,
    Job,
    JobApplication,
    JobProfile,
    MatchEvidence,
    Organization,
    Resume,
    User,
)
from app.services.errors import NotFoundError, ValidationError
from app.services.interview_question_service import (
    QUESTION_BANKS,
    QUESTION_CATEGORIES,
    InterviewQuestionService,
)


def create_candidate_context(
    db_session: Session,
) -> tuple[Organization, Candidate, Job, JobApplication]:
    organization = Organization(name="Interview Questions Org")
    db_session.add(organization)
    db_session.flush()
    user = User(
        organization_id=organization.id,
        email="questions@example.com",
        full_name="Questions User",
    )
    candidate = Candidate(
        organization_id=organization.id,
        full_name="Omar Adel",
        email="omar@example.com",
    )
    db_session.add_all([user, candidate])
    db_session.flush()
    job = Job(organization_id=organization.id, created_by_user_id=user.id, title="ML Engineer")
    resume = Resume(candidate_id=candidate.id, file_uri="local://resumes/questions.pdf")
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
            profile_data={"title": "ML Engineer", "requirements": [], "skills": []},
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
            profile_data={"skills": ["Python", "Machine Learning"]},
            is_current=True,
        )
    )
    db_session.commit()
    return organization, candidate, job, application


def test_question_bank_categories_and_counts(db_session: Session) -> None:
    organization, _candidate, _job, _application = create_candidate_context(db_session)

    payload = InterviewQuestionService().get_questions(
        db_session,
        organization_id=organization.id,
        candidate_id=None,
    )
    assert payload["categories"] == QUESTION_CATEGORIES
    assert payload["candidate_id"] is None
    assert payload["questions"]["Candidate-Specific"] == []
    assert len(payload["questions"]["Technical"]) == len(QUESTION_BANKS["Technical"])
    assert len(payload["questions"]["Behavioral"]) == len(QUESTION_BANKS["Behavioral"])
    assert len(payload["questions"]["Situational"]) == len(QUESTION_BANKS["Situational"])


def test_candidate_specific_uses_real_skills(db_session: Session) -> None:
    organization, candidate, _job, _application = create_candidate_context(db_session)

    payload = InterviewQuestionService().get_questions(
        db_session,
        organization_id=organization.id,
        candidate_id=candidate.id,
    )
    specific = payload["questions"]["Candidate-Specific"]
    assert len(specific) >= 1
    assert "Python" in specific[0]["text"]
    assert specific[0]["id"] == f"cs-match-{candidate.id}"


def test_candidate_specific_uses_real_gaps(db_session: Session) -> None:
    organization, candidate, _job, application = create_candidate_context(db_session)
    evaluation = CandidateEvaluation(
        job_application_id=application.id,
        job_profile_id=(
            db_session.query(JobProfile).filter(JobProfile.job_id == application.job_id).one().id
        ),
        candidate_profile_id=(
            db_session.query(CandidateProfile)
            .filter(CandidateProfile.resume_id == application.resume_id)
            .one()
            .id
        ),
        version_number=1,
        status="completed",
        is_current=True,
    )
    db_session.add(evaluation)
    db_session.flush()
    db_session.add(
        MatchEvidence(
            candidate_evaluation_id=evaluation.id,
            evidence_type="missing",
            requirement_ref={"requirement_key": "must_have:Go"},
        )
    )
    db_session.commit()

    payload = InterviewQuestionService().get_questions(
        db_session,
        organization_id=organization.id,
        candidate_id=candidate.id,
    )
    specific = payload["questions"]["Candidate-Specific"]
    gap_texts = [question["text"] for question in specific]
    assert any("Go" in text for text in gap_texts)


def test_unknown_candidate_raises_not_found(db_session: Session) -> None:
    organization, _candidate, _job, _application = create_candidate_context(db_session)
    with pytest.raises(NotFoundError, match="Candidate was not found"):
        InterviewQuestionService().get_questions(
            db_session,
            organization_id=organization.id,
            candidate_id=uuid.uuid4(),
        )


def test_candidate_from_other_org_rejected(db_session: Session) -> None:
    organization, candidate, _job, _application = create_candidate_context(db_session)
    other_org = Organization(name="Other Org")
    db_session.add(other_org)
    db_session.commit()

    with pytest.raises(ValidationError, match="different organization"):
        InterviewQuestionService().get_questions(
            db_session,
            organization_id=other_org.id,
            candidate_id=candidate.id,
        )
