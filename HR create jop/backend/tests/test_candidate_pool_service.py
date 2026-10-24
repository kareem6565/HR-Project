import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models import (
    Candidate,
    CandidateEvaluation,
    CandidateProfile,
    HRDecision,
    Job,
    JobApplication,
    JobProfile,
    Organization,
    Resume,
    User,
)
from app.services.candidate_pool_service import (
    GROUP_CONSIDER,
    GROUP_LOWER_PRIORITY,
    GROUP_MUST_REVIEW,
    CandidatePoolService,
    assign_group,
)
from app.services.errors import NotFoundError, ValidationError


def _add(db: Session, obj) -> None:
    db.add(obj)
    db.flush()


def _make_org(db: Session, name: str) -> Organization:
    org = Organization(name=name)
    _add(db, org)
    return org


def _make_user(db: Session, org: Organization) -> User:
    user = User(
        organization_id=org.id,
        email=f"pool-{_make_user_suffix()}@example.com",
        full_name="Pool User",
    )
    _add(db, user)
    return user


def _make_user_suffix() -> str:
    return uuid.uuid4().hex[:8]


def _make_job(db: Session, org: Organization, user: User) -> Job:
    job = Job(organization_id=org.id, created_by_user_id=user.id, title="Engineer")
    _add(db, job)
    return job


def _make_candidate(db: Session, org: Organization, full_name: str, email: str) -> Candidate:
    candidate = Candidate(
        organization_id=org.id,
        full_name=full_name,
        email=email,
    )
    _add(db, candidate)
    return candidate


def _make_resume(db: Session, candidate: Candidate) -> Resume:
    resume = Resume(candidate_id=candidate.id, file_uri=f"local://resumes/{uuid.uuid4()}.pdf")
    _add(db, resume)
    return resume


def _make_application(
    db: Session,
    org: Organization,
    job: Job,
    candidate: Candidate,
    resume: Resume,
    status: str = "ready_for_review",
) -> JobApplication:
    application = JobApplication(
        organization_id=org.id,
        job_id=job.id,
        candidate_id=candidate.id,
        resume_id=resume.id,
        status=status,
    )
    _add(db, application)
    return application


def _make_job_profile(db: Session, job: Job, user: User) -> JobProfile:
    profile = JobProfile(
        job_id=job.id,
        version_number=1,
        status="approved",
        source="hr_created",
        profile_data={"title": "Engineer"},
        approved_by_user_id=user.id,
        approved_at=datetime.now(UTC),
        is_current=True,
    )
    _add(db, profile)
    return profile


def _make_candidate_profile(db: Session, resume: Resume) -> CandidateProfile:
    profile = CandidateProfile(
        resume_id=resume.id,
        version_number=1,
        status="current",
        source="system_extracted",
        profile_data={"skills": []},
        is_current=True,
    )
    _add(db, profile)
    return profile


def _make_evaluation(
    db: Session,
    application: JobApplication,
    job_profile: JobProfile,
    candidate_profile: CandidateProfile,
    score: Decimal,
) -> CandidateEvaluation:
    evaluation = CandidateEvaluation(
        job_application_id=application.id,
        job_profile_id=job_profile.id,
        candidate_profile_id=candidate_profile.id,
        version_number=1,
        status="completed",
        score=score,
        recommendation="advance",
        is_current=True,
        completed_at=datetime.now(UTC),
    )
    _add(db, evaluation)
    return evaluation


def _make_decision(
    db: Session,
    application: JobApplication,
    user: User,
    decision: str,
    *,
    created_at: datetime | None = None,
) -> HRDecision:
    hr_decision = HRDecision(
        job_application_id=application.id,
        user_id=user.id,
        decision=decision,
        reason="Reviewer decision.",
        created_at=created_at or datetime.now(UTC),
    )
    _add(db, hr_decision)
    return hr_decision


def _seed_pool(db: Session) -> dict[str, object]:
    """Seed one org with a job and four candidates returning context.

    Scores: must-review (82), consider (55), lower (20), no-eval (None).
    """
    org = _make_org(db, "Pool Org")
    user = _make_user(db, org)
    job = _make_job(db, org, user)
    job_profile = _make_job_profile(db, job, user)

    score_82_candidate = _make_candidate(db, org, "Ava High", "ava@example.com")
    score_55_candidate = _make_candidate(db, org, "Bo Mid", "bo@example.com")
    score_20_candidate = _make_candidate(db, org, "Cy Low", "cy@example.com")
    no_eval_candidate = _make_candidate(db, org, "Dee None", "dee@example.com")

    app_high = _make_application(
        db,
        org,
        job,
        score_82_candidate,
        _make_resume(db, score_82_candidate),
    )
    app_mid = _make_application(
        db,
        org,
        job,
        score_55_candidate,
        _make_resume(db, score_55_candidate),
    )
    app_low = _make_application(
        db,
        org,
        job,
        score_20_candidate,
        _make_resume(db, score_20_candidate),
    )
    app_none = _make_application(
        db,
        org,
        job,
        no_eval_candidate,
        _make_resume(db, no_eval_candidate),
    )

    _make_evaluation(
        db,
        app_high,
        job_profile,
        _make_candidate_profile(db, app_high.resume),
        Decimal("82"),
    )
    _make_evaluation(
        db,
        app_mid,
        job_profile,
        _make_candidate_profile(db, app_mid.resume),
        Decimal("55"),
    )
    _make_evaluation(
        db,
        app_low,
        job_profile,
        _make_candidate_profile(db, app_low.resume),
        Decimal("20"),
    )

    _make_decision(db, app_high, user, "advance")
    _make_decision(db, app_mid, user, "hold")

    db.commit()

    return {
        "org": org,
        "user": user,
        "job": job,
        "score_82_candidate": score_82_candidate,
        "score_55_candidate": score_55_candidate,
        "score_20_candidate": score_20_candidate,
        "no_eval_candidate": no_eval_candidate,
        "app_high": app_high,
        "app_mid": app_mid,
        "app_low": app_low,
        "app_none": app_none,
    }


def test_assign_group_boundaries() -> None:
    assert assign_group(Decimal("70")) == GROUP_MUST_REVIEW
    assert assign_group(Decimal("69.99")) == GROUP_CONSIDER
    assert assign_group(Decimal("40")) == GROUP_CONSIDER
    assert assign_group(Decimal("39.99")) == GROUP_LOWER_PRIORITY
    assert assign_group(None) == GROUP_LOWER_PRIORITY


def test_ranks_by_score_descending_and_includes_no_eval(db_session: Session) -> None:
    ctx = _seed_pool(db_session)
    job: Job = ctx["job"]
    org: Organization = ctx["org"]

    entries = CandidatePoolService().list_ranked_candidates(
        db_session, job_id=job.id, organization_id=org.id
    )

    ids = [entry.candidate.id for entry in entries]
    assert ids == [
        ctx["score_82_candidate"].id,
        ctx["score_55_candidate"].id,
        ctx["score_20_candidate"].id,
        ctx["no_eval_candidate"].id,
    ]

    by_id = {entry.candidate.id: entry for entry in entries}
    assert by_id[ctx["score_82_candidate"].id].group == GROUP_MUST_REVIEW
    assert by_id[ctx["score_55_candidate"].id].group == GROUP_CONSIDER
    assert by_id[ctx["score_20_candidate"].id].group == GROUP_LOWER_PRIORITY
    assert by_id[ctx["no_eval_candidate"].id].group == GROUP_LOWER_PRIORITY


def test_group_filter_does_not_hide_candidates(db_session: Session) -> None:
    ctx = _seed_pool(db_session)
    job: Job = ctx["job"]
    org: Organization = ctx["org"]

    service = CandidatePoolService()

    must_review = service.list_ranked_candidates(
        db_session, job_id=job.id, organization_id=org.id, group=GROUP_MUST_REVIEW
    )
    assert [entry.candidate.id for entry in must_review] == [ctx["score_82_candidate"].id]

    consider = service.list_ranked_candidates(
        db_session, job_id=job.id, organization_id=org.id, group=GROUP_CONSIDER
    )
    assert [entry.candidate.id for entry in consider] == [ctx["score_55_candidate"].id]

    lower = service.list_ranked_candidates(
        db_session, job_id=job.id, organization_id=org.id, group=GROUP_LOWER_PRIORITY
    )
    assert {entry.candidate.id for entry in lower} == {
        ctx["score_20_candidate"].id,
        ctx["no_eval_candidate"].id,
    }


def test_status_filter(db_session: Session) -> None:
    ctx = _seed_pool(db_session)
    job: Job = ctx["job"]
    org: Organization = ctx["org"]

    entries = CandidatePoolService().list_ranked_candidates(
        db_session, job_id=job.id, organization_id=org.id, status="ready_for_review"
    )
    assert len(entries) == 4


def test_decision_filter(db_session: Session) -> None:
    ctx = _seed_pool(db_session)
    job: Job = ctx["job"]
    org: Organization = ctx["org"]

    entries = CandidatePoolService().list_ranked_candidates(
        db_session, job_id=job.id, organization_id=org.id, decision="advance"
    )
    assert [entry.candidate.id for entry in entries] == [ctx["score_82_candidate"].id]

    hold = CandidatePoolService().list_ranked_candidates(
        db_session, job_id=job.id, organization_id=org.id, decision="hold"
    )
    assert [entry.candidate.id for entry in hold] == [ctx["score_55_candidate"].id]


def test_decision_filter_never_excludes_missing_decision_by_default(db_session: Session) -> None:
    ctx = _seed_pool(db_session)
    job: Job = ctx["job"]
    org: Organization = ctx["org"]

    entries = CandidatePoolService().list_ranked_candidates(
        db_session, job_id=job.id, organization_id=org.id
    )
    assert len(entries) == 4


def test_min_max_score_filter(db_session: Session) -> None:
    ctx = _seed_pool(db_session)
    job: Job = ctx["job"]
    org: Organization = ctx["org"]

    service = CandidatePoolService()

    over_50 = service.list_ranked_candidates(
        db_session, job_id=job.id, organization_id=org.id, min_score=Decimal("40")
    )
    assert {entry.candidate.id for entry in over_50} == {
        ctx["score_82_candidate"].id,
        ctx["score_55_candidate"].id,
    }

    between = service.list_ranked_candidates(
        db_session,
        job_id=job.id,
        organization_id=org.id,
        min_score=Decimal("40"),
        max_score=Decimal("70"),
    )
    assert {entry.candidate.id for entry in between} == {ctx["score_55_candidate"].id}


def test_search_filter_on_name_and_email(db_session: Session) -> None:
    ctx = _seed_pool(db_session)
    job: Job = ctx["job"]
    org: Organization = ctx["org"]

    service = CandidatePoolService()

    by_name = service.list_ranked_candidates(
        db_session, job_id=job.id, organization_id=org.id, search="Ava"
    )
    assert {entry.candidate.id for entry in by_name} == {ctx["score_82_candidate"].id}

    by_email = service.list_ranked_candidates(
        db_session, job_id=job.id, organization_id=org.id, search="dee@example"
    )
    assert {entry.candidate.id for entry in by_email} == {ctx["no_eval_candidate"].id}


def test_cross_org_job_raises_validation_error(db_session: Session) -> None:
    ctx = _seed_pool(db_session)
    other_org = _make_org(db_session, "Other Org")
    db_session.commit()
    job: Job = ctx["job"]

    with pytest.raises((ValidationError, NotFoundError)):
        CandidatePoolService().list_ranked_candidates(
            db_session, job_id=job.id, organization_id=other_org.id
        )


def test_nonexistent_job_raises_not_found(db_session: Session) -> None:
    org = _make_org(db_session, "Pool Org")
    db_session.commit()

    with pytest.raises(NotFoundError):
        CandidatePoolService().list_ranked_candidates(
            db_session, job_id=uuid.uuid4(), organization_id=org.id
        )


def test_does_not_leak_other_jobs_candidates(db_session: Session) -> None:
    ctx = _seed_pool(db_session)
    org: Organization = ctx["org"]
    user: User = ctx["user"]
    other_job = _make_job(db_session, org, user)
    other_candidate = _make_candidate(db_session, org, "Zed Other", "zed@example.com")
    other_resume = _make_resume(db_session, other_candidate)
    other_app = _make_application(db_session, org, other_job, other_candidate, other_resume)
    other_job_profile = _make_job_profile(db_session, other_job, user)
    other_candidate_profile = _make_candidate_profile(db_session, other_resume)
    _make_evaluation(
        db_session,
        other_app,
        other_job_profile,
        other_candidate_profile,
        Decimal("99"),
    )
    db_session.commit()

    entries = CandidatePoolService().list_ranked_candidates(
        db_session, job_id=other_job.id, organization_id=org.id
    )
    assert [entry.candidate.id for entry in entries] == [other_candidate.id]


def test_uses_latest_decision_when_multiple(db_session: Session) -> None:
    ctx = _seed_pool(db_session)
    job: Job = ctx["job"]
    org: Organization = ctx["org"]
    user: User = ctx["user"]

    later = datetime.now(UTC) + timedelta(seconds=30)
    _make_decision(db_session, ctx["app_high"], user, "reject", created_at=later)
    db_session.commit()

    entries = CandidatePoolService().list_ranked_candidates(
        db_session, job_id=job.id, organization_id=org.id, decision="reject"
    )
    assert [entry.candidate.id for entry in entries] == [ctx["score_82_candidate"].id]
