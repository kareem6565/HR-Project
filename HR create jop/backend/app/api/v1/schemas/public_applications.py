from pydantic import BaseModel


class PublicApplicationConfigResponse(BaseModel):
    notice_available: bool
    privacy_notice_text: str | None = None
    privacy_notice_version: str | None = None
    turnstile_required: bool = False
    turnstile_server_configured: bool = False
    max_upload_bytes: int


class PublicApplicationResponse(BaseModel):
    success: bool = True
    application_reference: str
    message: str
