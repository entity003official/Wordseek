from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from redis import Redis
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from ..ai.deepseek import deepseek_status
from ..core.config import settings
from ..db import get_db
from ..models import AiGeneration, AnalysisJob, AuditLog, AuthSession, ConversationSession, User, utcnow
from ..services.auth import audit, public_user, revoke_all_sessions
from ..services.speech import process_speech_job
from ..services.storage import get_storage
from ..speech import QwenSpeechProvider
from ..workers.celery_app import celery_app
from ..workers.tasks import process_ai, process_ai_job_now, process_speech
from .deps import AuthContext, current_admin
from .schemas import AdminStatusRequest


router = APIRouter(prefix="/admin", tags=["管理"])
WINDOWS = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}
SAFE_AUDIT_METADATA = {"status", "source_job_id", "new_job_id", "kind"}
ERROR_MESSAGES = {
    "CLOUD_AUDIO_CONSENT_REQUIRED": "缺少本次录音的云端处理授权",
    "QWEN_NOT_CONFIGURED": "千问语音服务尚未配置",
    "QWEN_AUTH_FAILED": "千问服务鉴权失败，需要管理员检查配置",
    "QWEN_PERMISSION_DENIED": "千问账号没有所需模型权限",
    "QWEN_RATE_LIMITED": "千问服务触发限流，可稍后重试",
    "QWEN_PROVIDER_ERROR": "千问服务暂时异常，可稍后重试",
    "QWEN_TASK_TERMINATED": "千问任务已终止，需要重新提交",
    "AI_NOT_CONFIGURED": "DeepSeek服务尚未配置",
    "AI_AUTH_FAILED": "DeepSeek鉴权失败，需要管理员检查配置",
    "AI_BALANCE_EXHAUSTED": "DeepSeek账户余额不足",
    "AI_PROVIDER_RATE_LIMITED": "DeepSeek服务触发限流，可稍后重试",
    "AI_PROVIDER_OVERLOADED": "DeepSeek服务繁忙，可稍后重试",
    "AI_INVALID_RESPONSE": "模型结果未通过结构校验，可稍后重试",
    "SPEECH_PIPELINE_FAILED": "语音任务处理失败，请查看脱敏后的服务日志",
    "AI_JOB_FAILED": "AI任务处理失败，请查看脱敏后的服务日志",
}


def aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def window_start(value: str) -> datetime:
    return utcnow() - WINDOWS[value]


def ratio(part: int, total: int) -> float:
    return round(part / total, 4) if total else 0


def average(values: list[int | float]) -> int:
    return round(sum(values) / len(values)) if values else 0


def numeric(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def bucket_start(value: datetime, window: str) -> datetime:
    normalized = aware(value) or utcnow()
    if window == "24h":
        return normalized.replace(minute=0, second=0, microsecond=0)
    return normalized.replace(hour=0, minute=0, second=0, microsecond=0)


def empty_buckets(window: str) -> dict[datetime, dict]:
    now = bucket_start(utcnow(), window)
    count = 24 if window == "24h" else 7 if window == "7d" else 30
    step = timedelta(hours=1) if window == "24h" else timedelta(days=1)
    return {
        now - step * offset: {
            "bucket_start": now - step * offset,
            "sessions": 0,
            "jobs_complete": 0,
            "jobs_failed": 0,
            "qwen_calls": 0,
            "deepseek_calls": 0,
            "qwen_audio_minutes": 0.0,
            "deepseek_input_tokens": 0,
            "deepseek_output_tokens": 0,
        }
        for offset in reversed(range(count))
    }


def job_duration_ms(job: AnalysisJob) -> int | None:
    started = aware(job.started_at)
    finished = aware(job.finished_at)
    if not started:
        return None
    return max(0, round(((finished or utcnow()) - started).total_seconds() * 1000))


def job_provider(job: AnalysisJob) -> str:
    return job.provider or ("qwen" if job.kind == "speech" else "deepseek")


def job_model(job: AnalysisJob) -> str | None:
    return job.provider_model or (settings.qwen_file_model if job.kind == "speech" else settings.deepseek_model)


def serialize_job(job: AnalysisJob, owner: User) -> dict:
    return {
        "id": job.id,
        "owner": {"id": owner.id, "display_name": owner.display_name, "email": owner.email},
        "session_id": job.session_id,
        "kind": job.kind,
        "status": job.status,
        "progress": job.progress,
        "provider": job_provider(job),
        "model": job_model(job),
        "attempt_count": job.attempt_count,
        "retryable": bool((job.result_json or {}).get("retryable")),
        "retry_of_job_id": job.retry_of_job_id,
        "error_code": job.error_code,
        "error_summary": ERROR_MESSAGES.get(job.error_code or "", "任务处理失败，请查看脱敏后的服务日志") if job.error_code else None,
        "duration_ms": job_duration_ms(job),
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }


def model_usage(db: Session, window: str) -> dict:
    cutoff = window_start(window)
    buckets = empty_buckets(window)
    qwen_jobs = list(db.scalars(
        select(AnalysisJob)
        .where(AnalysisJob.created_at >= cutoff, or_(AnalysisJob.kind == "speech", AnalysisJob.provider == "qwen"))
        .order_by(AnalysisJob.created_at)
    ))
    generations = list(db.scalars(select(AiGeneration).where(AiGeneration.created_at >= cutoff).order_by(AiGeneration.created_at)))
    qwen_tts_generations = [item for item in generations if item.provider == "qwen" and item.task_type == "practice_tts"]
    deepseek_generations = [item for item in generations if item.provider == "deepseek"]
    ai_failed_jobs = list(db.scalars(select(AnalysisJob).where(
        AnalysisJob.created_at >= cutoff,
        AnalysisJob.kind.in_(["ai_review", "practice_set"]),
        AnalysisJob.status == "failed",
    ).order_by(AnalysisJob.created_at)))

    qwen_complete = [job for job in qwen_jobs if job.status == "complete"]
    qwen_failed = [job for job in qwen_jobs if job.status == "failed"]
    qwen_latencies: list[int] = []
    qwen_audio_ms = qwen_input = qwen_output = 0
    for job in qwen_jobs:
        execution = (job.result_json or {}).get("execution") or {}
        usage = execution.get("usage") or {}
        audio_ms = numeric(execution.get("audio_duration_ms"))
        qwen_audio_ms += audio_ms
        qwen_input += numeric(usage.get("input_tokens"))
        qwen_output += numeric(usage.get("output_tokens"))
        if execution.get("latency_ms") is not None:
            qwen_latencies.append(numeric(execution.get("latency_ms")))
        key = bucket_start(job.created_at, window)
        if key in buckets:
            buckets[key]["qwen_calls"] += 1
            buckets[key]["qwen_audio_minutes"] += round(audio_ms / 60000, 3)
    for generation in qwen_tts_generations:
        usage = generation.usage_json or {}
        qwen_input += numeric(usage.get("input_tokens"))
        qwen_output += numeric(usage.get("output_tokens"))
        if generation.latency_ms is not None:
            qwen_latencies.append(generation.latency_ms)
        key = bucket_start(generation.created_at, window)
        if key in buckets:
            buckets[key]["qwen_calls"] += 1

    deepseek_input = deepseek_output = 0
    deepseek_latencies: list[int] = []
    by_type: dict[str, int] = defaultdict(int)
    for generation in deepseek_generations:
        usage = generation.usage_json or {}
        input_tokens = numeric(usage.get("prompt_tokens") or usage.get("input_tokens"))
        output_tokens = numeric(usage.get("completion_tokens") or usage.get("output_tokens"))
        deepseek_input += input_tokens
        deepseek_output += output_tokens
        by_type[generation.task_type] += 1
        if generation.latency_ms is not None:
            deepseek_latencies.append(generation.latency_ms)
        key = bucket_start(generation.created_at, window)
        if key in buckets:
            buckets[key]["deepseek_calls"] += 1
            buckets[key]["deepseek_input_tokens"] += input_tokens
            buckets[key]["deepseek_output_tokens"] += output_tokens

    qwen_successful = len(qwen_complete) + len(qwen_tts_generations)
    qwen_finished = qwen_successful + len(qwen_failed)
    deepseek_finished = len(deepseek_generations) + len(ai_failed_jobs)
    qwen_available = QwenSpeechProvider().available
    deepseek_configured = bool(deepseek_status()["configured"])
    return {
        "range": window,
        "generated_at": utcnow(),
        "providers": [
            {
                "provider": "qwen", "model": f"{settings.qwen_file_model} + {settings.qwen_tts_model}", "configured": qwen_available,
                "calls": len(qwen_jobs) + len(qwen_tts_generations), "successful_calls": qwen_successful, "failed_calls": len(qwen_failed),
                "success_rate": ratio(qwen_successful, qwen_finished), "average_latency_ms": average(qwen_latencies),
                "audio_minutes": round(qwen_audio_ms / 60000, 2), "input_tokens": qwen_input, "output_tokens": qwen_output,
                "last_success_at": max(
                    [aware(job.finished_at) for job in qwen_complete if job.finished_at]
                    + [aware(item.created_at) for item in qwen_tts_generations if item.created_at],
                    default=None,
                ),
                "last_error_code": next((job.error_code for job in reversed(qwen_jobs) if job.status == "failed"), None),
                "task_types": {"speech": len(qwen_jobs), "practice_tts": len(qwen_tts_generations)},
            },
            {
                "provider": "deepseek", "model": settings.deepseek_model, "configured": deepseek_configured,
                "calls": deepseek_finished, "successful_calls": len(deepseek_generations), "failed_calls": len(ai_failed_jobs),
                "success_rate": ratio(len(deepseek_generations), deepseek_finished), "average_latency_ms": average(deepseek_latencies),
                "audio_minutes": 0, "input_tokens": deepseek_input, "output_tokens": deepseek_output,
                "last_success_at": max((item.created_at for item in deepseek_generations), default=None),
                "last_error_code": next((job.error_code for job in reversed(ai_failed_jobs)), None),
                "task_types": dict(by_type),
            },
        ],
        "series": list(buckets.values()),
        "billing_notice": "这里显示应用记录的调用用量，不是供应商结算账单。",
    }


@router.get("/overview")
def overview(
    range_value: Literal["24h", "7d", "30d"] = Query("7d", alias="range"),
    context: AuthContext = Depends(current_admin),
    db: Session = Depends(get_db),
) -> dict:
    cutoff = window_start(range_value)
    jobs = list(db.scalars(select(AnalysisJob).where(AnalysisJob.created_at >= cutoff).order_by(AnalysisJob.created_at)))
    sessions = list(db.scalars(select(ConversationSession).where(ConversationSession.created_at >= cutoff)))
    buckets = empty_buckets(range_value)
    for item in sessions:
        key = bucket_start(item.created_at, range_value)
        if key in buckets:
            buckets[key]["sessions"] += 1
    for job in jobs:
        key = bucket_start(job.created_at, range_value)
        if key in buckets and job.status == "complete":
            buckets[key]["jobs_complete"] += 1
        elif key in buckets and job.status == "failed":
            buckets[key]["jobs_failed"] += 1

    complete = sum(job.status == "complete" for job in jobs)
    failed = sum(job.status == "failed" for job in jobs)
    pending = sum(job.status in {"queued", "running"} for job in jobs)
    now = utcnow()
    usage = model_usage(db, range_value)
    return {
        "range": range_value,
        "generated_at": now,
        "totals": {
            "users": db.scalar(select(func.count(User.id))) or 0,
            "active_users": db.scalar(select(func.count(User.id)).where(User.last_login_at >= cutoff)) or 0,
            "active_sessions": db.scalar(select(func.count(AuthSession.id)).where(AuthSession.idle_expires_at > now, AuthSession.absolute_expires_at > now)) or 0,
            "sessions": db.scalar(select(func.count(ConversationSession.id))) or 0,
            "jobs": len(jobs),
            "pending_jobs": pending,
        },
        "job_health": {"complete": complete, "failed": failed, "success_rate": ratio(complete, complete + failed)},
        "providers": usage["providers"],
        "series": list(buckets.values()),
    }


@router.get("/users")
def list_users(
    query: str | None = Query(None, max_length=120),
    role: str | None = Query(None, pattern="^(user|admin)$"),
    account_status: str | None = Query(None, alias="status", pattern="^(active|disabled)$"),
    page: int | None = Query(None, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    context: AuthContext = Depends(current_admin),
    db: Session = Depends(get_db),
) -> list[dict] | dict:
    statement = select(User)
    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(or_(User.email.ilike(pattern), User.display_name.ilike(pattern)))
    if role:
        statement = statement.where(User.role == role)
    if account_status:
        statement = statement.where(User.status == account_status)
    statement = statement.order_by(User.created_at.desc(), User.id)
    if page is None and not any((query, role, account_status)):
        return [public_user(user) for user in db.scalars(statement)]
    selected_page = page or 1
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    items = list(db.scalars(statement.offset((selected_page - 1) * page_size).limit(page_size)))
    return {"items": [public_user(user) for user in items], "total": total, "page": selected_page, "page_size": page_size}


@router.patch("/users/{user_id}/status")
def set_user_status(user_id: str, payload: AdminStatusRequest, context: AuthContext = Depends(current_admin), db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "未找到账号")
    if user.id == context.user.id and payload.status == "disabled":
        raise HTTPException(409, "不能冻结当前管理员账号")
    user.status = payload.status
    if payload.status == "disabled":
        revoke_all_sessions(db, user.id)
    audit(db, context.user.id, "admin.user_status_changed", "user", user.id, {"status": payload.status})
    db.commit()
    return public_user(user)


@router.post("/users/{user_id}/revoke-sessions", status_code=204)
def revoke_user_sessions(user_id: str, context: AuthContext = Depends(current_admin), db: Session = Depends(get_db)):
    if not db.get(User, user_id):
        raise HTTPException(404, "未找到账号")
    revoke_all_sessions(db, user_id)
    audit(db, context.user.id, "admin.sessions_revoked", "user", user_id)
    db.commit()


@router.get("/jobs")
def list_jobs(
    kind: str | None = Query(None, pattern="^(speech|ai_review|practice_set)$"),
    status_value: str | None = Query(None, alias="status", pattern="^(queued|running|complete|failed)$"),
    provider: str | None = Query(None, pattern="^(qwen|deepseek)$"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    context: AuthContext = Depends(current_admin),
    db: Session = Depends(get_db),
) -> dict:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "起始日期不能晚于结束日期")
    filters = []
    if kind:
        filters.append(AnalysisJob.kind == kind)
    if status_value:
        filters.append(AnalysisJob.status == status_value)
    if provider == "qwen":
        filters.append(or_(AnalysisJob.provider == "qwen", AnalysisJob.kind == "speech"))
    elif provider == "deepseek":
        filters.append(or_(AnalysisJob.provider == "deepseek", AnalysisJob.kind.in_(["ai_review", "practice_set"])))
    if date_from:
        filters.append(AnalysisJob.created_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to:
        filters.append(AnalysisJob.created_at < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc))
    total = db.scalar(select(func.count(AnalysisJob.id)).where(*filters)) or 0
    rows = db.execute(
        select(AnalysisJob, User).join(User, User.id == AnalysisJob.owner_id).where(*filters)
        .order_by(AnalysisJob.created_at.desc(), AnalysisJob.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"items": [serialize_job(job, owner) for job, owner in rows], "total": total, "page": page, "page_size": page_size}


@router.post("/jobs/{job_id}/retry", status_code=202)
def retry_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    context: AuthContext = Depends(current_admin),
    db: Session = Depends(get_db),
) -> dict:
    source = db.get(AnalysisJob, job_id)
    if not source:
        raise HTTPException(404, "未找到任务")
    if source.status != "failed" or not bool((source.result_json or {}).get("retryable")):
        raise HTTPException(409, "该任务当前不可重试")
    if source.kind not in {"speech", "ai_review", "practice_set"}:
        raise HTTPException(409, "不支持重试这种任务")
    active = db.scalar(select(AnalysisJob.id).where(
        AnalysisJob.session_id == source.session_id,
        AnalysisJob.kind == source.kind,
        AnalysisJob.status.in_(["queued", "running"]),
    ))
    if active:
        raise HTTPException(409, "同类任务已经在处理中")
    conversation = db.get(ConversationSession, source.session_id)
    owner = db.get(User, source.owner_id)
    if not conversation or not owner:
        raise HTTPException(409, "任务关联的数据已经不存在")
    if source.kind == "speech" and not conversation.audio_object_key:
        raise HTTPException(409, "原始录音已经不存在，无法重试")
    if source.kind != "speech" and (not owner.preference or not owner.preference.ai_enabled):
        raise HTTPException(409, "用户已经关闭DeepSeek分析授权，不能重试")

    new_job = AnalysisJob(
        owner_id=source.owner_id,
        session_id=source.session_id,
        kind=source.kind,
        payload_json=dict(source.payload_json or {}),
        requested_backend="qwen" if source.kind == "speech" else None,
        provider=job_provider(source),
        provider_model=job_model(source),
        provider_task_id=source.provider_task_id if source.kind == "speech" else None,
        retry_of_job_id=source.id,
    )
    db.add(new_job)
    db.flush()
    if source.kind == "speech":
        conversation.processing_status = "transcribing"
        conversation.failure_reason = None
    audit(db, context.user.id, "admin.job_retried", "analysis_job", source.id, {
        "source_job_id": source.id, "new_job_id": new_job.id, "kind": source.kind,
    })
    db.commit()
    db.refresh(new_job)
    if settings.celery_eager:
        background_tasks.add_task(process_speech_job if source.kind == "speech" else process_ai_job_now, new_job.id)
    elif source.kind == "speech":
        process_speech.delay(new_job.id)
    else:
        process_ai.delay(new_job.id)
    return {"source_job_id": source.id, "job_id": new_job.id, "status": "queued"}


@router.get("/model-usage")
def get_model_usage(
    range_value: Literal["24h", "7d", "30d"] = Query("7d", alias="range"),
    context: AuthContext = Depends(current_admin),
    db: Session = Depends(get_db),
) -> dict:
    return model_usage(db, range_value)


@router.get("/audit-logs")
def list_audit_logs(
    action: str | None = Query(None, max_length=100),
    actor_id: str | None = Query(None, max_length=36),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    context: AuthContext = Depends(current_admin),
    db: Session = Depends(get_db),
) -> dict:
    filters = []
    if action:
        filters.append(AuditLog.action == action)
    if actor_id:
        filters.append(AuditLog.actor_id == actor_id)
    total = db.scalar(select(func.count(AuditLog.id)).where(*filters)) or 0
    rows = db.execute(
        select(AuditLog, User).outerjoin(User, User.id == AuditLog.actor_id).where(*filters)
        .order_by(AuditLog.created_at.desc(), AuditLog.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = []
    for entry, actor in rows:
        metadata = {key: value for key, value in (entry.metadata_json or {}).items() if key in SAFE_AUDIT_METADATA}
        items.append({
            "id": entry.id,
            "actor": None if not actor else {"id": actor.id, "display_name": actor.display_name, "email": actor.email},
            "action": entry.action,
            "target_type": entry.target_type,
            "target_id": entry.target_id,
            "metadata": metadata,
            "created_at": entry.created_at,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/system-health")
def system_health(context: AuthContext = Depends(current_admin), db: Session = Depends(get_db)) -> dict:
    qwen_available = QwenSpeechProvider().available
    deepseek_configured = bool(deepseek_status()["configured"])
    checks: dict[str, dict] = {
        "api": {"status": "ok", "detail": "API正在响应"},
        "database": {"status": "unknown", "detail": "尚未检查"},
        "redis": {"status": "not_applicable" if settings.celery_eager else "unknown", "detail": "开发环境使用同步任务" if settings.celery_eager else "尚未检查"},
        "storage": {"status": "unknown", "detail": "尚未检查"},
        "worker_default": {"status": "not_applicable" if settings.celery_eager else "unknown", "detail": "开发环境使用同步任务" if settings.celery_eager else "尚未检查"},
        "worker_speech": {"status": "not_applicable" if settings.celery_eager else "unknown", "detail": "开发环境使用同步任务" if settings.celery_eager else "尚未检查"},
        "qwen": {"status": "ok" if qwen_available else "error", "detail": "千问语音配置已就绪" if qwen_available else "千问语音尚未配置"},
        "deepseek": {"status": "ok" if deepseek_configured else "error", "detail": "DeepSeek配置已就绪" if deepseek_configured else "DeepSeek尚未配置"},
    }
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok", "detail": "PostgreSQL连接正常" if settings.database_url.startswith("postgresql") else "SQLite开发数据库连接正常"}
    except Exception:
        checks["database"] = {"status": "error", "detail": "数据库连接失败"}
    try:
        checks["storage"] = {"status": "ok", "detail": "对象存储连接正常"} if get_storage().healthcheck() else {"status": "error", "detail": "对象存储不可用"}
    except Exception:
        checks["storage"] = {"status": "error", "detail": "对象存储连接失败"}

    queues = {"default": 0, "speech": 0}
    if not settings.celery_eager:
        try:
            redis = Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
            redis.ping()
            queues = {"default": redis.llen("default"), "speech": redis.llen("speech")}
            redis.close()
            checks["redis"] = {"status": "ok", "detail": "Redis连接正常"}
        except Exception:
            checks["redis"] = {"status": "error", "detail": "Redis连接失败"}
        try:
            active_queues = celery_app.control.inspect(timeout=1).active_queues() or {}
            default_workers = sum(any(queue.get("name") == "default" for queue in queues_) for queues_ in active_queues.values())
            speech_workers = sum(any(queue.get("name") == "speech" for queue in queues_) for queues_ in active_queues.values())
            checks["worker_default"] = {"status": "ok" if default_workers else "error", "detail": f"{default_workers}个普通AI Worker在线" if default_workers else "未发现普通AI Worker"}
            checks["worker_speech"] = {"status": "ok" if speech_workers else "error", "detail": f"{speech_workers}个千问Worker在线" if speech_workers else "未发现千问Worker"}
        except Exception:
            checks["worker_default"] = {"status": "error", "detail": "无法读取普通AI Worker状态"}
            checks["worker_speech"] = {"status": "error", "detail": "无法读取千问Worker状态"}
    overall = "ok" if all(item["status"] in {"ok", "not_applicable"} for item in checks.values()) else "degraded"
    return {"status": overall, "checked_at": utcnow(), "checks": checks, "queues": queues, "grafana_url": settings.grafana_url or None}


@router.get("/metrics")
def metrics(context: AuthContext = Depends(current_admin), db: Session = Depends(get_db)) -> dict:
    return {
        "users": db.scalar(select(func.count(User.id))) or 0,
        "active_sessions": db.scalar(select(func.count(AuthSession.id))) or 0,
        "ai_generations": db.scalar(select(func.count(AiGeneration.id))) or 0,
        "ai_failures": db.scalar(select(func.count(AnalysisJob.id)).where(
            AnalysisJob.kind.in_(["ai_review", "practice_set"]), AnalysisJob.status == "failed",
        )) or 0,
    }
