from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models import AiGeneration, User
from ..speech.tts import QwenTtsProvider
from .storage import get_storage


TTS_PROMPT_VERSION = "qwen-tts-2026-09-27.1"


def normalize_tts_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def tts_input_hash(text: str, language: str = "English") -> str:
    payload = {
        "model": settings.qwen_tts_model,
        "voice": settings.qwen_tts_voice,
        "language_type": language,
        "text": text,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cached(db: Session, owner_id: str, input_hash: str) -> AiGeneration | None:
    return db.scalar(select(AiGeneration).where(
        AiGeneration.owner_id == owner_id,
        AiGeneration.task_type == "practice_tts",
        AiGeneration.input_hash == input_hash,
        AiGeneration.prompt_version == TTS_PROMPT_VERSION,
        AiGeneration.status == "complete",
    ))


def _read_cached(generation: AiGeneration) -> tuple[bytes, dict[str, Any], bool] | None:
    output = generation.output_json or {}
    object_key = output.get("object_key")
    if not isinstance(object_key, str) or not object_key.startswith("tts/"):
        return None
    try:
        audio = get_storage().get(object_key)
    except Exception:
        return None
    return audio, output, True


def synthesize_practice_text(db: Session, user: User, raw_text: str, language: str = "English") -> tuple[bytes, dict[str, Any], bool]:
    text = normalize_tts_text(raw_text)
    if not text:
        raise HTTPException(422, "练习文本不能为空")
    input_hash = tts_input_hash(text, language)
    existing = _cached(db, user.id, input_hash)
    if existing:
        cached = _read_cached(existing)
        if cached:
            return cached
        db.execute(delete(AiGeneration).where(AiGeneration.id == existing.id))
        db.commit()

    since = datetime.now(timezone.utc) - timedelta(days=1)
    generated_count = db.scalar(select(func.count(AiGeneration.id)).where(
        AiGeneration.owner_id == user.id,
        AiGeneration.task_type == "practice_tts",
        AiGeneration.created_at >= since,
        AiGeneration.status == "complete",
    )) or 0
    if generated_count >= settings.qwen_tts_generations_per_day:
        raise HTTPException(429, {
            "code": "TTS_DAILY_LIMIT_REACHED",
            "message": "今天的新语音生成次数已用完，已生成过的题目仍可继续播放。",
            "retryable": False,
        })

    result = QwenTtsProvider().synthesize(text, language)
    extension = "mp3" if result.content_type in {"audio/mpeg", "audio/mp3"} else "wav"
    object_key = f"tts/{user.id}/{input_hash}.{extension}"
    get_storage().put(object_key, result.audio, result.content_type)
    output = {
        "object_key": object_key,
        "content_type": result.content_type,
        "voice": settings.qwen_tts_voice,
        "language_type": language,
        "size_bytes": len(result.audio),
        "retry_count": result.retry_count,
    }
    generation = AiGeneration(
        owner_id=user.id,
        task_type="practice_tts",
        provider="qwen",
        model=settings.qwen_tts_model,
        prompt_version=TTS_PROMPT_VERSION,
        input_hash=input_hash,
        status="complete",
        output_json=output,
        usage_json=result.usage,
        latency_ms=result.latency_ms,
        finish_reason="synthesized",
    )
    db.add(generation)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        winner = _cached(db, user.id, input_hash)
        if winner:
            cached = _read_cached(winner)
            if cached:
                return cached
        raise
    return result.audio, output, False


def delete_user_tts_objects(db: Session, user_id: str) -> None:
    generations = list(db.scalars(select(AiGeneration).where(
        AiGeneration.owner_id == user_id,
        AiGeneration.task_type == "practice_tts",
    )))
    if not generations:
        return
    storage = get_storage()
    for generation in generations:
        object_key = (generation.output_json or {}).get("object_key")
        if isinstance(object_key, str) and object_key.startswith("tts/"):
            storage.delete(object_key)
