"""Schemas for the AI-settings management endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class AISettingsResponse(BaseModel):
    provider: str
    model: str
    api_key_source: str
    has_api_key: bool


class SetApiKeyRequest(BaseModel):
    api_key: str


class VerifyApiKeyRequest(BaseModel):
    api_key: str | None = None


class VerifyApiKeyResponse(BaseModel):
    ok: bool
    message: str
    model: str
