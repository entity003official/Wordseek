from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def uuid_string() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(512), nullable=True)
    display_name: Mapped[str] = mapped_column(String(80), default="英语学习者")
    voiceprint_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="user", index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    oidc_subject: Mapped[str | None] = mapped_column(String(512), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    preference: Mapped["UserPreference"] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)


class UserPreference(Base):
    __tablename__ = "user_preferences"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    goal: Mapped[str] = mapped_column(String(80), default="延续话题")
    date_format: Mapped[str] = mapped_column(String(8), default="auto", server_default="auto")
    native_language: Mapped[str] = mapped_column(String(8), default="zh", server_default="zh")
    target_language: Mapped[str] = mapped_column(String(8), default="en", server_default="en")
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_consent_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ai_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pii_aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    user: Mapped[User] = relationship(back_populates="preference")


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConversationSession(Base):
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    target_language: Mapped[str] = mapped_column(String(8), default="en", server_default="en")
    __tablename__ = "conversation_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(800))
    scenario: Mapped[str] = mapped_column(String(80), default="日常交流")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    processing_status: Mapped[str] = mapped_column(String(24), default="saved", index=True)
    audio_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    audio_content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    audio_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    analysis_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_speaker_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    transcript_version: Mapped[int] = mapped_column(Integer, default=0)


class Marker(Base):
    __tablename__ = "markers_v1"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_string)
    session_id: Mapped[str] = mapped_column(ForeignKey("conversation_sessions.id", ondelete="CASCADE"), index=True)
    timestamp_ms: Mapped[int] = mapped_column(Integer)


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs_v1"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("conversation_sessions.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="speech")
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    requested_backend: Mapped[str | None] = mapped_column(String(20), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    provider_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_task_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    retry_of_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)


class AiGeneration(Base):
    __tablename__ = "ai_generations"
    __table_args__ = (UniqueConstraint("owner_id", "task_type", "input_hash", "prompt_version", name="uq_ai_input_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("conversation_sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    task_type: Mapped[str] = mapped_column(String(40), index=True)
    provider: Mapped[str] = mapped_column(String(30), default="deepseek")
    model: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(30))
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(24), default="complete")
    output_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    usage_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    finish_reason: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Practice(Base):
    __tablename__ = "practices_v1"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey("conversation_sessions.id", ondelete="CASCADE"), nullable=True)
    event_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    title: Mapped[str] = mapped_column(String(120))
    prompt: Mapped[str] = mapped_column(Text)
    target_language: Mapped[str] = mapped_column(String(8), default="en", server_default="en")
    hint: Mapped[str] = mapped_column(Text)
    rubric_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(30), default="local")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PracticeAttempt(Base):
    __tablename__ = "practice_attempts_v1"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    practice_id: Mapped[str] = mapped_column(ForeignKey("practices_v1.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[str] = mapped_column(String(80))
    response: Mapped[str] = mapped_column(Text)
    feedback_json: Mapped[Any] = mapped_column(JSON)
    feedback_source: Mapped[str] = mapped_column(String(30), default="local-rules")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PracticeConversation(Base):
    __tablename__ = "practice_conversations"
    __table_args__ = (
        UniqueConstraint("owner_id", "scene_id", "target_language", name="uq_practice_conversation_scene"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    practice_id: Mapped[str] = mapped_column(ForeignKey("practices_v1.id", ondelete="CASCADE"), index=True)
    scene_id: Mapped[str] = mapped_column(String(160), index=True)
    target_language: Mapped[str] = mapped_column(String(8))
    messages: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    target_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


Index("ix_sessions_owner_created", ConversationSession.owner_id, ConversationSession.created_at)
Index("ix_practices_owner_created", Practice.owner_id, Practice.created_at)
Index("ix_jobs_status_created", AnalysisJob.status, AnalysisJob.created_at)
Index("ix_jobs_kind_created", AnalysisJob.kind, AnalysisJob.created_at)
Index("ix_jobs_provider_created", AnalysisJob.provider, AnalysisJob.created_at)
Index("ix_jobs_created_at", AnalysisJob.created_at)


class TutorConversation(Base):
    __tablename__ = "tutor_conversations"
    session_id: Mapped[str] = mapped_column(ForeignKey("conversation_sessions.id", ondelete="CASCADE"), primary_key=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    messages: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=0)


class WeeklyEntry(Base):
    __tablename__ = "weekly_entries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    week: Mapped[str] = mapped_column(String(10), index=True)
    kind: Mapped[str] = mapped_column(String(12))
    text: Mapped[str] = mapped_column(String(1000))
    note: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
