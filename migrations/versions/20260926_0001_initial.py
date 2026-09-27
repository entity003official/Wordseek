"""Initial account-isolated application schema.

Revision ID: 20260926_0001
Revises: None
"""
import sqlalchemy as sa
from alembic import op


revision = "20260926_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(512)),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("oidc_subject", sa.String(512), unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_status", "users", ["status"])

    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("goal", sa.String(80), nullable=False),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False),
        sa.Column("ai_consent_version", sa.String(20)),
        sa.Column("ai_consent_at", sa.DateTime(timezone=True)),
        sa.Column("pii_aliases", sa.JSON(), nullable=False),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_hash", sa.String(64)),
        sa.Column("user_agent", sa.String(300)),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"], unique=True)
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"], unique=True)

    op.create_table(
        "conversation_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("scenario", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("processing_status", sa.String(24), nullable=False),
        sa.Column("audio_object_key", sa.String(512)),
        sa.Column("audio_content_type", sa.String(100)),
        sa.Column("audio_size", sa.Integer()),
        sa.Column("analysis_json", sa.JSON()),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("user_speaker_id", sa.String(80)),
        sa.Column("transcript_version", sa.Integer(), nullable=False),
    )
    op.create_index("ix_conversation_sessions_owner_id", "conversation_sessions", ["owner_id"])
    op.create_index("ix_conversation_sessions_created_at", "conversation_sessions", ["created_at"])
    op.create_index("ix_conversation_sessions_processing_status", "conversation_sessions", ["processing_status"])
    op.create_index("ix_sessions_owner_created", "conversation_sessions", ["owner_id", "created_at"])
    op.create_table(
        "markers_v1",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("conversation_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp_ms", sa.Integer(), nullable=False),
    )
    op.create_index("ix_markers_v1_session_id", "markers_v1", ["session_id"])
    op.create_table(
        "analysis_jobs_v1",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("conversation_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message", sa.Text()),
    )
    op.create_index("ix_analysis_jobs_v1_owner_id", "analysis_jobs_v1", ["owner_id"])
    op.create_index("ix_analysis_jobs_v1_session_id", "analysis_jobs_v1", ["session_id"])
    op.create_index("ix_analysis_jobs_v1_status", "analysis_jobs_v1", ["status"])
    op.create_table(
        "ai_generations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("conversation_sessions.id", ondelete="CASCADE")),
        sa.Column("task_type", sa.String(40), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("prompt_version", sa.String(30), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("output_json", sa.JSON(), nullable=False),
        sa.Column("usage_json", sa.JSON(), nullable=False),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("finish_reason", sa.String(60)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "task_type", "input_hash", "prompt_version", name="uq_ai_input_version"),
    )
    for name, columns in (
        ("ix_ai_generations_owner_id", ["owner_id"]),
        ("ix_ai_generations_session_id", ["session_id"]),
        ("ix_ai_generations_task_type", ["task_type"]),
        ("ix_ai_generations_input_hash", ["input_hash"]),
        ("ix_ai_generations_created_at", ["created_at"]),
    ):
        op.create_index(name, "ai_generations", columns)

    op.create_table(
        "practices_v1",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("conversation_sessions.id", ondelete="CASCADE")),
        sa.Column("event_id", sa.String(80)),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("hint", sa.Text(), nullable=False),
        sa.Column("rubric_json", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_practices_v1_owner_id", "practices_v1", ["owner_id"])
    op.create_index("ix_practices_owner_created", "practices_v1", ["owner_id", "created_at"])
    op.create_table(
        "practice_attempts_v1",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("practice_id", sa.String(36), sa.ForeignKey("practices_v1.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", sa.String(80), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("feedback_json", sa.JSON(), nullable=False),
        sa.Column("feedback_source", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_practice_attempts_v1_owner_id", "practice_attempts_v1", ["owner_id"])
    op.create_index("ix_practice_attempts_v1_practice_id", "practice_attempts_v1", ["practice_id"])
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(60)),
        sa.Column("target_id", sa.String(80)),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    for table in (
        "audit_logs",
        "practice_attempts_v1",
        "practices_v1",
        "ai_generations",
        "analysis_jobs_v1",
        "markers_v1",
        "conversation_sessions",
        "password_reset_tokens",
        "auth_sessions",
        "user_preferences",
        "users",
    ):
        op.drop_table(table)
