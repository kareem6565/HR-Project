"""Schemas for authentication endpoints (Prompt 2)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    email: str
    password: str
    organization_id: uuid.UUID | None = None


class HRSsoExchangeRequest(BaseModel):
    assertion: str = Field(min_length=1, max_length=8192)


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: str
    roles: list[str] = Field(validation_alias="effective_roles")
    organization_id: uuid.UUID
    is_active: bool
    status: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfileResponse
