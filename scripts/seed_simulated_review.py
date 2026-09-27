"""Create one persistent, clearly labelled review fixture and run DeepSeek on it.

The script attaches the fixture to the user with the most recently active login
session. It sends only the synthetic English transcript to DeepSeek and never
uploads audio or prints model output, API keys, or private account data.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from backend.app.ai.service import PROMPT_VERSION
from backend.app.db import SessionLocal
from backend.app.models import AiGeneration, AnalysisJob, AuthSession, ConversationSession, User, UserPreference
from backend.app.services.speech import conversation_metrics, conversation_summary, interaction_events
from backend.app.workers.tasks import process_ai_job_now


FIXTURE_ID = "synthetic-project-delivery-review-v1"
FIXTURE_TITLE = "模拟项目交付沟通（含错误）"
FIXTURE_NOTICE = "这是用于验收的模拟英文对话，不来自真实录音；只有模拟文字发送给 DeepSeek。"


def fixture_turns() -> list[dict]:
    lines = [
        ("SPEAKER_01", 0, 4200, "What did the client say about the delivery date?"),
        ("SPEAKER_00", 4400, 9300, "Yesterday I go to the client meeting, but I don't understood their main concern."),
        ("SPEAKER_01", 9600, 14100, "Did you confirm Friday, or did you say it was only a possibility?"),
        ("SPEAKER_00", 14400, 19100, "They wants the delivery on Friday, and I say we can maybe finish."),
        ("SPEAKER_01", 19400, 24300, "Moving it earlier may not be realistic. We still need two days for testing."),
        ("SPEAKER_00", 24600, 30500, "The testing is not finish yet. I think we should make the deadline more earlier."),
        ("SPEAKER_01", 30800, 35800, "Tell them Friday is only a target and that we will confirm after testing."),
        ("SPEAKER_00", 36100, 40700, "Can you explain me again what should I tell to the client?"),
        ("SPEAKER_01", 41000, 45600, "Please say Friday is a target, and ask whether Monday would work as a backup."),
        ("SPEAKER_00", 45900, 49600, "Okay, I will tell them we finish Friday."),
    ]
    return [
        {
            "id": f"turn_{index}",
            "speaker_id": speaker_id,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "text": text,
        }
        for index, (speaker_id, start_ms, end_ms, text) in enumerate(lines, start=1)
    ]


def current_user(db) -> User:
    user = db.scalar(
        select(User)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(User.status == "active")
        .order_by(AuthSession.last_seen_at.desc())
        .limit(1)
    )
    if user:
        return user
    user = db.scalar(select(User).where(User.status == "active").order_by(User.last_login_at.desc()).limit(1))
    if not user:
        raise RuntimeError("没有可用于验收的已注册账号")
    return user


def create_fixture(db, user: User) -> ConversationSession:
    existing = db.scalar(
        select(ConversationSession)
        .where(
            ConversationSession.owner_id == user.id,
            ConversationSession.title == FIXTURE_TITLE,
        )
        .order_by(ConversationSession.created_at.desc())
    )
    if existing and (existing.analysis_json or {}).get("fixture_id") == FIXTURE_ID:
        analysis = dict(existing.analysis_json or {})
        summary = dict(analysis.get("summary") or {})
        summary.update({
            "title": "项目交付时间沟通",
            "description": "验收用模拟对话，共 10 个话轮；刻意包含语法错误、信息表达不清和过度承诺。",
        })
        analysis["summary"] = summary
        analysis["notice"] = FIXTURE_NOTICE
        existing.analysis_json = analysis
        db.commit()
        return existing

    turns = fixture_turns()
    conversation = ConversationSession(
        owner_id=user.id,
        title=FIXTURE_TITLE,
        scenario="工作会议",
        duration_ms=50_000,
        processing_status="ready",
        user_speaker_id="SPEAKER_00",
        transcript_version=1,
    )
    db.add(conversation)
    db.flush()
    analysis = {
        "schema_version": "speech-analysis.v2",
        "mode": "real",
        "fixture_id": FIXTURE_ID,
        "notice": FIXTURE_NOTICE,
        "asr": {"model": "synthetic-fixture", "language": "en", "engine": "manual"},
        "diarization": {"status": "complete", "speaker_count": 2, "model": "synthetic-fixture", "reason": "acceptance_fixture"},
        "speakers": [
            {"id": "SPEAKER_00", "user_confirmed_identity": True},
            {"id": "SPEAKER_01", "user_confirmed_identity": False},
        ],
        "turns": turns,
        "events": [],
        "markers": [],
        "semantic_provider": "local-rules",
    }
    analysis["summary"] = conversation_summary(conversation, turns)
    analysis["summary"].update({
        "title": "项目交付时间沟通",
        "description": "验收用模拟对话，共 10 个话轮；刻意包含语法错误、信息表达不清和过度承诺。",
    })
    analysis["metrics"] = conversation_metrics(turns, "SPEAKER_00")
    analysis["events"] = interaction_events(analysis, "SPEAKER_00", [])
    conversation.analysis_json = analysis
    db.commit()
    db.refresh(conversation)
    return conversation


def enable_ai_for_test(db, user: User) -> None:
    preference = db.get(UserPreference, user.id)
    if not preference:
        preference = UserPreference(user_id=user.id)
        db.add(preference)
    preference.ai_enabled = True
    preference.ai_consent_version = "review-test-v1"
    preference.ai_consent_at = datetime.now(timezone.utc)
    db.commit()


def print_result(db, conversation: ConversationSession, job_id: str, *, cached: bool) -> None:
    review = (conversation.analysis_json or {}).get("ai_review")
    if not review:
        raise RuntimeError("DeepSeek 任务完成，但复盘结果未写入对话")
    generation = db.scalar(
        select(AiGeneration)
        .where(
            AiGeneration.session_id == conversation.id,
            AiGeneration.task_type == "review",
            AiGeneration.prompt_version == PROMPT_VERSION,
        )
        .order_by(AiGeneration.created_at.desc())
    )
    usage = (generation.usage_json or {}) if generation else {}
    print(
        "模拟复盘验收通过："
        f"session_id={conversation.id}; job_id={job_id}; provider=deepseek; "
        f"model={generation.model if generation else 'unknown'}; "
        f"latency_ms={generation.latency_ms if generation else 'unknown'}; "
        f"prompt_tokens={usage.get('prompt_tokens', 'unknown')}; "
        f"completion_tokens={usage.get('completion_tokens', 'unknown')}; "
        f"events={len(review.get('events') or [])}; cached={str(cached).lower()}; output_saved=true"
    )


def main() -> None:
    db = SessionLocal()
    try:
        user = current_user(db)
        enable_ai_for_test(db, user)
        conversation = create_fixture(db, user)
        analysis = conversation.analysis_json or {}
        current_generation = db.scalar(
            select(AiGeneration)
            .where(
                AiGeneration.session_id == conversation.id,
                AiGeneration.task_type == "review",
                AiGeneration.prompt_version == PROMPT_VERSION,
            )
            .order_by(AiGeneration.created_at.desc())
        )
        if analysis.get("ai_review") and current_generation:
            previous_job = db.scalar(select(AnalysisJob).where(
                AnalysisJob.session_id == conversation.id,
                AnalysisJob.kind == "ai_review",
                AnalysisJob.status == "complete",
            ).order_by(AnalysisJob.created_at.desc()))
            print_result(db, conversation, previous_job.id if previous_job else "cached", cached=True)
            return
        job = AnalysisJob(
            owner_id=user.id,
            session_id=conversation.id,
            kind="ai_review",
            status="queued",
            payload_json={"force": False, "fixture_id": FIXTURE_ID},
            requested_backend="deepseek",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id
        session_id = conversation.id
    finally:
        db.close()

    result = process_ai_job_now(job_id)
    if result.get("status") != "complete":
        raise RuntimeError(f"DeepSeek 复盘失败：job_id={job_id}; error_code={result.get('error_code')}")

    db = SessionLocal()
    try:
        conversation = db.get(ConversationSession, session_id)
        if not conversation:
            raise RuntimeError("DeepSeek 任务完成，但对话记录不存在")
        print_result(db, conversation, job_id, cached=False)
    finally:
        db.close()


if __name__ == "__main__":
    main()
