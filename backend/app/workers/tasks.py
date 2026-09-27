import time

from .celery_app import celery_app
from fastapi import HTTPException

from ..ai.service import generate_practice_set, generate_review
from ..core.config import settings
from ..db import SessionLocal
from ..models import AnalysisJob, ConversationSession, User
from ..models import utcnow
from ..core.observability import record_task_attempt
from ..services.speech import process_speech_job


@celery_app.task(
    bind=True,
    name="beyond_words.process_speech",
    queue="speech",
    autoretry_for=(),
    acks_late=True,
    max_retries=3,
)
def process_speech(self, job_id: str) -> None:
    started = time.perf_counter()
    result = process_speech_job(job_id)
    execution = result.get("execution") or {}
    record_task_attempt(
        kind="speech",
        status=str(result.get("status") or "failed"),
        provider="qwen",
        duration_seconds=time.perf_counter() - started,
        error_code=result.get("error_code"),
        provider_latency_ms=execution.get("latency_ms"),
    )
    if result.get("retryable") and self.request.retries < self.max_retries:
        db = SessionLocal()
        try:
            job = db.get(AnalysisJob, job_id)
            if job:
                job.status = "queued"
                job.progress = 0.1
                conversation = db.get(ConversationSession, job.session_id)
                if conversation:
                    conversation.processing_status = "transcribing"
                    conversation.failure_reason = None
                db.commit()
        finally:
            db.close()
        raise self.retry(countdown=2 ** self.request.retries)


def process_ai_job_now(job_id: str) -> dict:
    db = SessionLocal()
    try:
        job = db.get(AnalysisJob, job_id)
        if not job:
            return {"status": "missing", "provider": "deepseek"}
        user = db.get(User, job.owner_id)
        conversation = db.get(ConversationSession, job.session_id)
        if not user or not conversation:
            raise RuntimeError("任务关联的数据不存在")
        job.status = "running"
        job.progress = 0.15
        job.started_at = utcnow()
        job.attempt_count += 1
        job.provider = "deepseek"
        job.provider_model = settings.deepseek_model
        db.commit()
        if job.kind == "ai_review":
            result = generate_review(db, user, conversation, force=bool(job.payload_json.get("force")))
            job.result_json = {"review": result}
        elif job.kind == "practice_set":
            items = generate_practice_set(db, user, conversation, job.payload_json.get("event_id"))
            job.result_json = {"practice_ids": [item.id for item in items]}
        else:
            raise RuntimeError("不支持的 AI 任务类型")
        job.status = "complete"
        job.progress = 1
        job.finished_at = utcnow()
        db.commit()
        return {"status": "complete", "provider": "deepseek"}
    except Exception as error:
        db.rollback()
        job = db.get(AnalysisJob, job_id)
        if job:
            detail = error.detail if isinstance(error, HTTPException) else None
            retryable = bool(detail.get("retryable")) if isinstance(detail, dict) else False
            job.status = "failed"
            job.error_code = detail.get("code", "AI_JOB_FAILED") if isinstance(detail, dict) else "AI_JOB_FAILED"
            job.error_message = (detail.get("message") if isinstance(detail, dict) else str(error))[:1000]
            job.result_json = {"retryable": retryable, "attempt_count": job.attempt_count}
            job.finished_at = utcnow()
            db.commit()
        return {
            "status": "failed",
            "provider": "deepseek",
            "error_code": job.error_code if job else "AI_JOB_FAILED",
        }
    finally:
        db.close()


@celery_app.task(name="beyond_words.process_ai", queue="default", autoretry_for=(), acks_late=True)
def process_ai(job_id: str) -> None:
    started = time.perf_counter()
    result = process_ai_job_now(job_id)
    record_task_attempt(
        kind="ai",
        status=str(result.get("status") or "failed"),
        provider="deepseek",
        duration_seconds=time.perf_counter() - started,
        error_code=result.get("error_code"),
    )
