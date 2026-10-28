from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ConsentLinkResponse(BaseModel):
    token: str
    expires_at: datetime


class ConsentLinkPreviewRequest(BaseModel):
    token: str = Field(min_length=32, max_length=128)


class ConsentLinkPreviewResponse(BaseModel):
    organization_name: str
    consent_text: str
    consent_version: str
    link_expires_at: datetime


class ConsentLinkDecisionRequest(ConsentLinkPreviewRequest):
    decision: Literal["accepted", "declined"]
    self_attested: Literal[True]


class ConsentLinkDecisionResponse(BaseModel):
    decision: Literal["accepted", "declined"]
    consent_expires_at: datetime | None = None


class ConsentWithdrawalRequest(BaseModel):
    candidate_requested: Literal[True]
