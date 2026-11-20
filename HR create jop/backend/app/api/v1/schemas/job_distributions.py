from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

DistributionChannel = Literal["linkedin", "facebook", "wuzzuf", "other"]


class JobDistributionCreate(BaseModel):
    channel: DistributionChannel
    campaign_name: str = Field(min_length=1, max_length=120)


class JobDistributionUpdate(BaseModel):
    campaign_name: str | None = Field(default=None, min_length=1, max_length=120)
    post_text: str | None = Field(default=None, max_length=5000)


class JobDistributionShare(BaseModel):
    hr_reviewed: Literal[True]
    external_post_url: AnyHttpUrl | None = Field(default=None, max_length=1000)


class DistributionPostResponse(BaseModel):
    post_text: str
    ai_generated: bool = True


class JobDistributionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    approved_profile_id: UUID
    channel: DistributionChannel
    campaign_name: str
    tracking_key: str
    post_text: str
    ai_generated: bool
    status: Literal["draft", "shared"]
    external_post_url: str | None
    hr_reviewed_at: datetime | None
    shared_at: datetime | None
    created_at: datetime
    updated_at: datetime


class JobDistributionCampaignMetric(BaseModel):
    distribution_id: UUID
    job_id: UUID
    job_title: str
    channel: DistributionChannel
    campaign_name: str
    status: Literal["draft", "shared"]
    views: int
    applications: int
    conversion_percent: float | None


class JobDistributionSourceMetric(BaseModel):
    source: str
    medium: str | None
    applications: int


class JobDistributionAnalyticsResponse(BaseModel):
    range_days: Literal[30, 90]
    campaigns: list[JobDistributionCampaignMetric]
    sources: list[JobDistributionSourceMetric]
