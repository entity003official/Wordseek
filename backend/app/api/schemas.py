from __future__ import annotations

from typing import Any

from pydantic import BaseModel, EmailStr, Field
from typing import Literal
from ..languages import Language


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=300)
    new_password: str = Field(min_length=12, max_length=128)


class SessionCreateRequest(BaseModel):
    target_language: Language = "en"
    title: str = Field(min_length=1, max_length=120)
    scenario: str = Field(default="日常交流", min_length=1, max_length=80)


class SessionPatchRequest(BaseModel):
    is_favorite: bool | None = None
    title: str | None = Field(default=None, min_length=1, max_length=120)
    scenario: str | None = Field(default=None, min_length=1, max_length=80)


class MarkerRequest(BaseModel):
    id: str | None = Field(default=None, max_length=64)
    timestamp_ms: int = Field(ge=0)


class SpeakerRequest(BaseModel):
    user_speaker_id: str = Field(min_length=1, max_length=80)


class TurnPatchRequest(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=5000)
    speaker_id: str | None = Field(default=None, max_length=80)


class SpeakerPolicy(BaseModel):
    mode: Literal["auto", "expected"] = "auto"
    min_count: int = Field(default=1, ge=1, le=8)
    max_count: int = Field(default=8, ge=1, le=8)
    expected_count: int | None = Field(default=None, ge=1, le=8)


class CloudAudioConsent(BaseModel):
    accepted: bool = False
    version: str = Field(default="2026-09-26.1", max_length=30)


class AnalyzeRequest(BaseModel):
    language_hints: list[str] = Field(default_factory=lambda: ["en", "zh"], max_length=4)
    speaker_policy: SpeakerPolicy = Field(default_factory=SpeakerPolicy)
    cloud_audio_consent: CloudAudioConsent = Field(default_factory=CloudAudioConsent)


class PreferenceRequest(BaseModel):
    date_format: Literal["auto", "zh", "ymd", "dmy", "mdy", "iso"] | None = None
    native_language: Language | None = None
    target_language: Language | None = None
    goal: str | None = Field(default=None, min_length=1, max_length=80)
    ai_enabled: bool | None = None
    consent_version: str | None = Field(default=None, max_length=20)
    pii_aliases: list[str] | None = Field(default=None, max_length=20)


class PracticeCreateRequest(BaseModel):
    target_language: Language = "en"
    session_id: str | None = None
    event_id: str | None = None
    title: str = Field(min_length=1, max_length=800)
    prompt: str = Field(min_length=1, max_length=1000)
    hint: str = Field(min_length=1, max_length=1000)


class PracticeAttemptRequest(BaseModel):
    response: str = Field(min_length=1, max_length=5000)


class PracticeTtsRequest(BaseModel):
    language: Language = "en"
    text: str = Field(min_length=1, max_length=500)


class AdminStatusRequest(BaseModel):
    status: str = Field(pattern="^(active|disabled)$")


class AccountDeleteRequest(BaseModel):
    confirmation: str = Field(pattern="^DELETE$")
    password: str | None = Field(default=None, max_length=128)


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    retryable: bool = False


class ErrorResponse(BaseModel):
    error: ErrorBody


JsonObject = dict[str, Any]
