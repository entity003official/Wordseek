from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from redis import Redis

from ..ai.deepseek import deepseek_status
from ..core.config import settings
from ..db import get_db
from ..services.storage import get_storage
from ..speech import QwenSpeechProvider


router = APIRouter(tags=["运行状态"])


@router.get("/health/live")
def live() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
def ready(db: Session = Depends(get_db)) -> dict:
    dependencies = {"database": "ok", "queue": "eager" if settings.celery_eager else "ok", "storage": "ok"}
    try:
        db.execute(text("SELECT 1"))
        if not settings.celery_eager:
            Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2).ping()
        get_storage()
    except Exception as error:
        raise HTTPException(503, "数据库、任务队列或对象存储尚未就绪") from error
    if not QwenSpeechProvider().available:
        raise HTTPException(503, "千问语音服务尚未配置")
    return {"status": "ready", **dependencies}


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    qwen = QwenSpeechProvider()
    qwen_available = qwen.available
    return {
        "status": "ok",
        "analysis_mode": "qwen_cloud" if qwen_available else "unconfigured",
        "speech": {
            "default_backend": settings.speech_backend,
            "qwen": {
                "available": qwen_available,
                "model": settings.qwen_file_model,
                "short_model": settings.qwen_short_model,
                "tts_model": settings.qwen_tts_model,
                "tts_voice": settings.qwen_tts_voice,
                "region": "cn-beijing",
                "workspace_domain": bool(settings.read_qwen_workspace_id()),
                "audio_url_mode": settings.qwen_audio_url_mode,
            },
        },
        "semantic": deepseek_status(),
        "storage": settings.storage_backend,
        "queue": "eager" if settings.celery_eager else "celery",
        "database": "postgresql" if settings.database_url.startswith("postgresql") else "sqlite-development",
    }
