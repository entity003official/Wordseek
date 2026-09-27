from __future__ import annotations

from datetime import datetime, timezone
import base64
import binascii
from pydantic import BaseModel, Field
from ..services.auth import public_user

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..ai.service import delete_user_ai_content
from ..db import get_db
from ..core.security import verify_password
from ..models import AiGeneration, AnalysisJob, ConversationSession, Practice, PracticeAttempt, PracticeConversation, UserPreference, TutorConversation, WeeklyEntry
from ..repositories.sessions import SessionRepository
from ..services.storage import get_storage
from ..services.tts import delete_user_tts_objects
from .deps import AuthContext, current_context
from .schemas import AccountDeleteRequest, PreferenceRequest


router = APIRouter(prefix="/me", tags=["我的"])


def preference_payload(item: UserPreference) -> dict:
    return {
        "goal": item.goal,
        "date_format": item.date_format,
        "native_language": item.native_language,
        "target_language": item.target_language,
        "ai_enabled": item.ai_enabled,
        "ai_consent_version": item.ai_consent_version,
        "ai_consent_at": item.ai_consent_at,
        "pii_aliases": item.pii_aliases or [],
    }


@router.get("/preferences")
def get_preferences(context: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> dict:
    item = db.get(UserPreference, context.user.id)
    return preference_payload(item)


@router.put("/preferences")
def update_preferences(payload: PreferenceRequest, context: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> dict:
    item = db.get(UserPreference, context.user.id)
    if payload.date_format is not None:
        item.date_format = payload.date_format
    if payload.goal is not None:
        item.goal = payload.goal.strip()
    if payload.native_language is not None:
        item.native_language = payload.native_language
    if payload.target_language is not None:
        item.target_language = payload.target_language
    if payload.pii_aliases is not None:
        item.pii_aliases = [alias.strip() for alias in payload.pii_aliases if alias.strip()]
    if payload.ai_enabled is not None:
        item.ai_enabled = payload.ai_enabled
        if payload.ai_enabled:
            item.ai_consent_version = payload.consent_version or "2026-09-26.1"
            item.ai_consent_at = datetime.now(timezone.utc)
    db.commit()
    return preference_payload(item)


@router.delete("/ai-content", status_code=204)
def delete_ai_content(context: AuthContext = Depends(current_context), db: Session = Depends(get_db)):
    db.execute(delete(TutorConversation).where(TutorConversation.owner_id == context.user.id))
    db.execute(delete(PracticeConversation).where(PracticeConversation.owner_id == context.user.id))
    delete_user_ai_content(db, context.user.id)


@router.get("/export")
def export_data(context: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> dict:
    sessions = SessionRepository(db, context.user.id).list()
    practices = list(db.scalars(select(Practice).where(Practice.owner_id == context.user.id).order_by(Practice.created_at.desc())))
    attempts = list(db.scalars(select(PracticeAttempt).where(PracticeAttempt.owner_id == context.user.id).order_by(PracticeAttempt.created_at.desc())))
    generations = list(db.scalars(select(AiGeneration).where(AiGeneration.owner_id == context.user.id).order_by(AiGeneration.created_at.desc())))
    return {
        "weekly_entries": [{"id": e.id, "week": e.week, "kind": e.kind, "text": e.text, "note": e.note} for e in db.scalars(select(WeeklyEntry).where(WeeklyEntry.owner_id == context.user.id))],
        "tutor_conversations": [{"session_id": c.session_id, "messages": c.messages} for c in db.scalars(select(TutorConversation).where(TutorConversation.owner_id == context.user.id))],
        "practice_conversations": [{"scene_id": c.scene_id, "target_language": c.target_language, "messages": c.messages, "version": c.version} for c in db.scalars(select(PracticeConversation).where(PracticeConversation.owner_id == context.user.id))],
        "voiceprint": {k: v for k, v in (context.user.voiceprint_json or {}).items() if k != "embedding"},
        "exported_at": datetime.now(timezone.utc),
        "user": {"email": context.user.email, "display_name": context.user.display_name, "avatar": context.user.avatar},
        "preferences": preference_payload(db.get(UserPreference, context.user.id)),
        "sessions": [{"id": item.id, "title": item.title, "scenario": item.scenario, "is_favorite": item.is_favorite, "created_at": item.created_at, "duration_ms": item.duration_ms, "analysis": item.analysis_json} for item in sessions],
        "practices": [{"id": item.id, "session_id": item.session_id, "event_id": item.event_id, "title": item.title, "prompt": item.prompt, "hint": item.hint, "rubric": item.rubric_json, "source": item.source} for item in practices],
        "attempts": [{"id": item.id, "practice_id": item.practice_id, "response": item.response, "feedback": item.feedback_json, "created_at": item.created_at} for item in attempts],
        "ai_generations": [{"id": item.id, "session_id": item.session_id, "task_type": item.task_type, "provider": item.provider, "model": item.model, "output": item.output_json, "created_at": item.created_at} for item in generations],
    }


@router.delete("/data", status_code=204)
def delete_all_data(context: AuthContext = Depends(current_context), db: Session = Depends(get_db)):
    sessions = SessionRepository(db, context.user.id).list()
    keys = [item.audio_object_key for item in sessions if item.audio_object_key]
    delete_user_tts_objects(db, context.user.id)
    db.execute(delete(PracticeConversation).where(PracticeConversation.owner_id == context.user.id))
    db.execute(delete(PracticeAttempt).where(PracticeAttempt.owner_id == context.user.id))
    db.execute(delete(Practice).where(Practice.owner_id == context.user.id))
    db.execute(delete(AiGeneration).where(AiGeneration.owner_id == context.user.id))
    db.execute(delete(AnalysisJob).where(AnalysisJob.owner_id == context.user.id))
    db.execute(delete(ConversationSession).where(ConversationSession.owner_id == context.user.id))
    db.execute(delete(WeeklyEntry).where(WeeklyEntry.owner_id == context.user.id))
    context.user.voiceprint_json = None
    preference = db.get(UserPreference, context.user.id)
    if preference:
        preference.date_format = "auto"
        preference.goal = "延续话题"
        preference.ai_enabled = False
        preference.ai_consent_version = None
        preference.ai_consent_at = None
        preference.pii_aliases = []
    db.commit()
    for key in keys:
        get_storage().delete(key)


@router.delete("/account", status_code=204)
def delete_account(payload: AccountDeleteRequest, response: Response, context: AuthContext = Depends(current_context), db: Session = Depends(get_db)):
    if context.user.password_hash and (not payload.password or not verify_password(context.user.password_hash, payload.password)):
        raise HTTPException(400, "密码不正确")
    keys = [item.audio_object_key for item in SessionRepository(db, context.user.id).list() if item.audio_object_key]
    delete_user_tts_objects(db, context.user.id)
    db.delete(context.user)
    db.commit()
    response.delete_cookie("bw_session", path="/")
    response.delete_cookie("bw_csrf", path="/")
    for key in keys:
        get_storage().delete(key)


class ProfileEditRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    avatar: str | None = Field(default=None, max_length=200000)


@router.put("/profile")
def edit_profile(payload: ProfileEditRequest, context: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> dict:
    name = payload.display_name.strip()
    if not name:
        raise HTTPException(422, "昵称不能为空")
    if payload.avatar:
        try:
            prefix, encoded = payload.avatar.split(",", 1)
            data = base64.b64decode(encoded, validate=True)
            if prefix != "data:image/png;base64" or not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError()
        except (ValueError, binascii.Error):
            raise HTTPException(422, "头像格式不正确")
    context.user.display_name = name
    context.user.avatar = payload.avatar
    db.commit()
    return public_user(context.user)


@router.get("/voiceprint")
def voiceprint_status(context: AuthContext = Depends(current_context)) -> dict:
    from ..services.voiceprint import MODEL_PATH
    item = context.user.voiceprint_json or {}
    return {"enrolled": bool(item), "available": MODEL_PATH.is_file() and MODEL_PATH.with_suffix(".ready").is_file(), "created_at": item.get("created_at")}


@router.delete("/voiceprint", status_code=204)
def remove_voiceprint(context: AuthContext = Depends(current_context), db: Session = Depends(get_db)):
    context.user.voiceprint_json = None
    db.commit()


from datetime import date, timedelta
from typing import Literal

class WeeklyEntryRequest(BaseModel):
    week: date
    kind: Literal["word", "sentence"]
    text: str = Field(min_length=1, max_length=1000)
    note: str = Field(default="", max_length=500)

def entry_payload(entry: WeeklyEntry):
    return {"id": entry.id, "week": entry.week, "kind": entry.kind, "text": entry.text, "note": entry.note}

@router.get("/weekly-entries")
def weekly_entries(week: date, context: AuthContext = Depends(current_context), db: Session = Depends(get_db)):
    monday = (week - timedelta(days=week.weekday())).isoformat()
    return [entry_payload(e) for e in db.scalars(select(WeeklyEntry).where(WeeklyEntry.owner_id == context.user.id, WeeklyEntry.week == monday).order_by(WeeklyEntry.created_at, WeeklyEntry.id))]

@router.post("/weekly-entries", status_code=201)
def add_weekly_entry(payload: WeeklyEntryRequest, context: AuthContext = Depends(current_context), db: Session = Depends(get_db)):
    if not payload.text.strip():
        raise HTTPException(422, "请输入单词或句子")
    entry = WeeklyEntry(owner_id=context.user.id, week=(payload.week - timedelta(days=payload.week.weekday())).isoformat(), kind=payload.kind, text=payload.text.strip(), note=payload.note.strip())
    db.add(entry)
    db.commit()
    return entry_payload(entry)

@router.delete("/weekly-entries/{entry_id}", status_code=204)
def remove_weekly_entry(entry_id: str, context: AuthContext = Depends(current_context), db: Session = Depends(get_db)):
    entry = db.scalar(select(WeeklyEntry).where(WeeklyEntry.id == entry_id, WeeklyEntry.owner_id == context.user.id))
    if not entry:
        raise HTTPException(404, "未找到该条记录")
    db.delete(entry)
    db.commit()


class WeeklyJournalRequest(BaseModel):
    week: date
    timezone_offset: int = Field(default=0, ge=-840, le=840)
    session_ids: list[str] | None = Field(default=None, max_length=100)

@router.get("/weekly-journal")
def get_weekly_journal(week: date, context: AuthContext = Depends(current_context), db: Session = Depends(get_db)):
    monday = (week - timedelta(days=week.weekday())).isoformat()
    saved = db.scalar(select(AiGeneration).where(AiGeneration.owner_id == context.user.id, AiGeneration.task_type == "weekly_journal", AiGeneration.input_hash == monday, AiGeneration.prompt_version == "weekly-extract-v1"))
    return saved.output_json if saved else None

@router.post("/weekly-journal")
def generate_weekly_journal(payload: WeeklyJournalRequest, context: AuthContext = Depends(current_context), db: Session = Depends(get_db)):
    from sqlalchemy.exc import IntegrityError
    monday = payload.week - timedelta(days=payload.week.weekday())
    # JS offset is UTC minus local time; use local Monday boundaries.
    begin = datetime.combine(monday, datetime.min.time(), tzinfo=timezone.utc) + timedelta(minutes=payload.timezone_offset)
    query = select(ConversationSession).where(ConversationSession.owner_id == context.user.id)
    if payload.session_ids is None:
        query = query.where(ConversationSession.created_at >= begin, ConversationSession.created_at < begin + timedelta(days=7))
    else:
        if not payload.session_ids:
            raise HTTPException(422, "请至少选择一条复盘")
        query = query.where(ConversationSession.id.in_(payload.session_ids))
    records = list(db.scalars(query.order_by(ConversationSession.created_at.desc())))
    if payload.session_ids is not None and len(records) != len(set(payload.session_ids)):
        raise HTTPException(404, "部分复盘已不存在，请重新选择")
    if not records:
        raise HTTPException(409, "本周还没有复盘记录")
    words, sentences, sources = [], [], []
    seen_words, seen_sentences = set(), set()
    skipped = 0
    for record in records:
        points = ((record.analysis_json or {}).get("ai_review") or {}).get("learning_points") or []
        if not points:
            skipped += 1
            continue
        sources.append({"id": record.id, "title": record.title})
        for point in points:
            original = str(point.get("original") or "").strip()
            explanation = str(point.get("explanation") or "").strip()
            if point.get("kind") in ("vocabulary", "synonym") and original:
                key = original.casefold()
                if key not in seen_words:
                    seen_words.add(key)
                    words.append({"text": original, "note": explanation, "source_id": record.id})
            sentence = str(point.get("alternative") if point.get("kind") == "natural_expression" else point.get("example") or "").strip()
            if sentence and sentence != "None" and sentence.casefold() not in seen_sentences:
                seen_sentences.add(sentence.casefold())
                sentences.append({"text": sentence, "note": str(point.get("usage_note") or ""), "source_id": record.id})
    if not words and not sentences:
        raise HTTPException(409, "所选记录还没有语言学习复盘，请先在复盘详情中生成")
    output = {"week": monday.isoformat(), "words": words[:8], "sentences": sentences[:6], "sources": sources, "skipped": skipped, "generated_at": datetime.now(timezone.utc).isoformat()}
    def existing():
        return db.scalar(select(AiGeneration).where(AiGeneration.owner_id == context.user.id, AiGeneration.task_type == "weekly_journal", AiGeneration.input_hash == monday.isoformat(), AiGeneration.prompt_version == "weekly-extract-v1"))
    saved = existing()
    if saved:
        saved.output_json = output
    else:
        db.add(AiGeneration(owner_id=context.user.id, task_type="weekly_journal", provider="local", model="review-extraction", prompt_version="weekly-extract-v1", input_hash=monday.isoformat(), output_json=output, usage_json={}))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        saved = existing()
        if not saved:
            raise
        saved.output_json = output
        db.commit()
    return output
