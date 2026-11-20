from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.contracts.distribution import DistributionPostSuggestion
from app.ai.providers.base import StructuredGenerationRequest
from app.api.v1.schemas.job_distributions import JobDistributionCreate, JobDistributionUpdate
from app.models import Job, JobApplication, JobDistribution, JobDistributionView, JobProfile
from app.services.errors import InvalidStateError, NotFoundError, ValidationError

CHANNEL_MEDIUM = {
    "linkedin": "social",
    "facebook": "social",
    "wuzzuf": "job_board",
    "other": "external",
}


class JobDistributionService:
    @staticmethod
    def _get_job(db: Session, *, job_id: uuid.UUID, organization_id: uuid.UUID) -> Job:
        job = db.get(Job, job_id)
        if job is None or job.organization_id != organization_id:
            raise NotFoundError("Job was not found.")
        return job

    @staticmethod
    def _get_distributable_profile(db: Session, job: Job) -> JobProfile:
        if job.status != "active" or job.publication_status != "published":
            raise InvalidStateError("Publish an active job before preparing a distribution.")
        profile = (
            db.get(JobProfile, job.published_job_profile_id)
            if job.published_job_profile_id
            else None
        )
        if profile is None or profile.status != "approved" or profile.job_id != job.id:
            raise InvalidStateError("The published job must have its approved profile attached.")
        return profile

    def create(
        self,
        db: Session,
        *,
        job_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        body: JobDistributionCreate,
    ) -> JobDistribution:
        job = self._get_job(db, job_id=job_id, organization_id=organization_id)
        profile = self._get_distributable_profile(db, job)
        name = " ".join(body.campaign_name.split())
        if not name:
            raise ValidationError("Enter a name for this campaign.")
        item = JobDistribution(
            organization_id=organization_id,
            job_id=job.id,
            approved_profile_id=profile.id,
            created_by_user_id=user_id,
            channel=body.channel,
            campaign_name=name,
        )
        db.add(item)
        db.flush()
        return item

    def list_for_job(
        self, db: Session, *, job_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[JobDistribution]:
        self._get_job(db, job_id=job_id, organization_id=organization_id)
        return list(
            db.scalars(
                select(JobDistribution)
                .where(
                    JobDistribution.job_id == job_id,
                    JobDistribution.organization_id == organization_id,
                )
                .order_by(JobDistribution.created_at.desc())
            ).all()
        )

    @staticmethod
    def _get_distribution(
        db: Session, *, distribution_id: uuid.UUID, organization_id: uuid.UUID
    ) -> JobDistribution:
        item = db.get(JobDistribution, distribution_id)
        if item is None or item.organization_id != organization_id:
            raise NotFoundError("Distribution was not found.")
        return item

    def update(
        self,
        db: Session,
        *,
        distribution_id: uuid.UUID,
        organization_id: uuid.UUID,
        body: JobDistributionUpdate,
    ) -> JobDistribution:
        item = self._get_distribution(
            db, distribution_id=distribution_id, organization_id=organization_id
        )
        if item.status != "draft":
            raise InvalidStateError(
                "A shared campaign cannot be edited. Create a new campaign version."
            )
        if body.campaign_name is not None:
            name = " ".join(body.campaign_name.split())
            if not name:
                raise ValidationError("Enter a name for this campaign.")
            item.campaign_name = name
        if body.post_text is not None:
            item.post_text = body.post_text.strip()
        db.flush()
        return item

    def generate_post(
        self,
        db: Session,
        *,
        distribution_id: uuid.UUID,
        organization_id: uuid.UUID,
        company_name: str | None = None,
    ) -> JobDistribution:
        item = self._get_distribution(
            db, distribution_id=distribution_id, organization_id=organization_id
        )
        if item.status != "draft":
            raise InvalidStateError("A shared campaign cannot be regenerated.")
        job = self._get_job(db, job_id=item.job_id, organization_id=organization_id)
        profile = self._get_distributable_profile(db, job)
        if profile.id != item.approved_profile_id:
            raise InvalidStateError(
                "The approved profile changed. Create a new distribution draft."
            )

        profile_data = profile.profile_data or {}
        requirements = [
            requirement
            for requirement in profile_data.get("requirements", [])
            if isinstance(requirement, dict)
            and isinstance(requirement.get("key"), str)
            and isinstance(requirement.get("text"), str)
        ]
        trusted_role = {
            "title": job.title,
            "company": company_name,
            "location": job.location,
            "workplace_type": job.work_mode,
            "employment_type": job.job_type,
            "approved_summary": profile_data.get("summary"),
            "approved_requirements": [
                {
                    "key": req["key"],
                    "text": req["text"],
                    "category": req.get("category"),
                    "dimension": req.get("dimension"),
                }
                for req in requirements
            ],
        }
        instructions = {
            "task": (
                "Write a short opening for a recruitment post and select approved requirement keys."
            ),
            "platform": item.channel,
            "rules": [
                "Use only the supplied approved profile and job fields.",
                (
                    "Do not invent salary, benefits, company facts, workplace arrangements, "
                    "or qualifications."
                ),
                "Do not rewrite or change the meaning or priority of requirements.",
                "Select only keys from approved_requirements; HERA will insert their exact text.",
                "Do not include an application URL; HERA adds its own tracked link separately.",
                "This is an HR-reviewed draft and must never be published automatically.",
            ],
            "approved_job": trusted_role,
        }

        from app.ai.providers import get_provider
        from app.ai.providers.factory import resolve_ai_config
        from app.core.config import settings

        if resolve_ai_config(settings)["is_fake"]:
            first_keys = [
                req["key"]
                for req in requirements
                if req.get("category") in {"must_have", "nice_to_have"}
            ][:4]
            payload = {
                "opening": (
                    f"Explore this {job.title} opportunity at {company_name}."
                    if company_name
                    else f"Explore this {job.title} opportunity."
                ),
                "highlighted_requirement_keys": first_keys,
            }
            provider = get_provider(
                settings,
                provider="fake",
                model="fake-job-distribution",
                structured_payload=payload,
            )
        else:
            provider = get_provider(settings)
        result = provider.generate_structured(
            StructuredGenerationRequest(
                input=json.dumps(instructions, ensure_ascii=False),
                output_schema=DistributionPostSuggestion,
                schema_version="1.0",
                metadata={"workflow": "job_distribution_copy", "channel": item.channel},
            )
        )
        try:
            suggestion = DistributionPostSuggestion.model_validate(result.data)
        except Exception as exc:
            raise ValidationError(
                "The AI could not prepare a valid recruitment post draft."
            ) from exc

        by_key = {req["key"]: req for req in requirements}
        selected_keys = list(dict.fromkeys(suggestion.highlighted_requirement_keys))
        if any(key not in by_key for key in selected_keys):
            raise ValidationError("The AI selected a qualification outside the approved profile.")
        if len(selected_keys) > 6:
            raise ValidationError("The AI selected too many job requirements.")

        sections = [suggestion.opening.strip(), f"We're hiring: {job.title}"]
        metadata = [
            value for value in (company_name, job.location, job.work_mode, job.job_type) if value
        ]
        if metadata:
            sections.append(" · ".join(metadata))
        summary = profile_data.get("summary")
        if isinstance(summary, str) and summary.strip():
            sections.append(summary.strip())
        exact_items = [by_key[key] for key in selected_keys]
        required = [item for item in exact_items if item.get("category") == "must_have"]
        preferred = [item for item in exact_items if item.get("category") == "nice_to_have"]
        responsibilities = [
            item for item in exact_items if item.get("dimension") == "responsibility"
        ]
        if responsibilities:
            sections.append(
                "Role responsibilities:\n" + "\n".join(f"• {r['text']}" for r in responsibilities)
            )
        if required:
            sections.append("Required:\n" + "\n".join(f"• {r['text']}" for r in required))
        if preferred:
            sections.append("Preferred:\n" + "\n".join(f"• {r['text']}" for r in preferred))
        sections.append("See the full job details and apply using the tracked HERA link below.")
        post_text = "\n\n".join(sections)
        if len(post_text) > 5000:
            post_text = post_text[:4997].rstrip() + "…"
        item.post_text = post_text
        item.ai_generated = True
        db.flush()
        return item

    def mark_shared(
        self,
        db: Session,
        *,
        distribution_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        external_post_url: str | None,
    ) -> JobDistribution:
        item = self._get_distribution(
            db, distribution_id=distribution_id, organization_id=organization_id
        )
        if item.status == "shared":
            return item
        if not item.post_text.strip():
            raise InvalidStateError("Save the post text before marking this campaign as shared.")
        job = self._get_job(db, job_id=item.job_id, organization_id=organization_id)
        profile = self._get_distributable_profile(db, job)
        if profile.id != item.approved_profile_id:
            raise InvalidStateError(
                "The approved profile changed. Review a new draft before sharing."
            )
        now = datetime.now(UTC)
        item.status = "shared"
        item.hr_reviewed_by_user_id = user_id
        item.hr_reviewed_at = now
        item.shared_at = now
        item.external_post_url = external_post_url
        db.flush()
        return item

    def record_view(self, db: Session, *, public_id: str, tracking_key: str | None) -> None:
        if not tracking_key:
            return
        item = db.scalar(
            select(JobDistribution)
            .join(Job, Job.id == JobDistribution.job_id)
            .where(
                Job.public_id == public_id,
                Job.publication_status == "published",
                Job.status == "active",
                JobDistribution.tracking_key == tracking_key,
            )
        )
        if item is None:
            return
        db.add(JobDistributionView(distribution_id=item.id))
        db.flush()

    def analytics(self, db: Session, *, organization_id: uuid.UUID, range_days: int) -> dict:
        since = datetime.now(UTC) - timedelta(days=range_days)
        campaigns = list(
            db.scalars(
                select(JobDistribution)
                .where(JobDistribution.organization_id == organization_id)
                .order_by(JobDistribution.created_at.desc())
            ).all()
        )
        output_campaigns = []
        for item in campaigns:
            job = db.get(Job, item.job_id)
            views = int(
                db.scalar(
                    select(func.count(JobDistributionView.id)).where(
                        JobDistributionView.distribution_id == item.id,
                        JobDistributionView.created_at >= since,
                    )
                )
                or 0
            )
            applications = int(
                db.scalar(
                    select(func.count(JobApplication.id)).where(
                        JobApplication.organization_id == organization_id,
                        JobApplication.job_id == item.job_id,
                        JobApplication.source_campaign == item.tracking_key,
                        JobApplication.created_at >= since,
                    )
                )
                or 0
            )
            output_campaigns.append(
                {
                    "distribution_id": item.id,
                    "job_id": item.job_id,
                    "job_title": job.title if job else "Unavailable job",
                    "channel": item.channel,
                    "campaign_name": item.campaign_name,
                    "status": item.status,
                    "views": views,
                    "applications": applications,
                    "conversion_percent": round(applications * 100 / views, 1) if views else None,
                }
            )

        source_rows = db.execute(
            select(
                JobApplication.source,
                JobApplication.source_medium,
                func.count(JobApplication.id),
            )
            .where(
                JobApplication.organization_id == organization_id,
                JobApplication.created_at >= since,
            )
            .group_by(JobApplication.source, JobApplication.source_medium)
            .order_by(func.count(JobApplication.id).desc())
        ).all()
        return {
            "range_days": range_days,
            "campaigns": output_campaigns,
            "sources": [
                {
                    "source": source or "Unspecified",
                    "medium": medium,
                    "applications": int(count),
                }
                for source, medium, count in source_rows
            ],
        }
