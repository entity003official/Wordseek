from __future__ import annotations

import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from ..core.config import settings
from ..db import SessionLocal
from ..models import AnalysisJob, ConversationSession, Marker, UserPreference, User
from ..speech import QwenSpeechProvider, SpeechProviderError, prepare_cloud_audio
from .storage import get_storage
from .localized_insights import localize_insight



def conversation_summary(conversation: ConversationSession, turns: list[dict]) -> dict:
    stop_words = {
        "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "be", "to", "of",
        "in", "on", "at", "for", "with", "it", "that", "this", "i", "you", "we", "they", "he",
        "she", "do", "does", "did", "have", "has", "had", "so", "well", "yeah", "yes", "no",
    }
    counts: dict[str, int] = {}
    word_count = 0
    for turn in turns:
        for token in re.findall(r"[A-Za-z']+", turn.get("text", "").lower()):
            word_count += 1
            if len(token) > 2 and token not in stop_words:
                counts[token] = counts.get(token, 0) + 1
    keywords = [word for word, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:4]]
    speakers = {turn.get("speaker_id") for turn in turns if turn.get("speaker_id") != "SPEAKER_UNKNOWN"}
    return {
        "title": f"{conversation.scenario}复盘",
        "description": f"真实录音共识别出 {len(turns)} 个话轮、约 {word_count} 个英文词。" + (
            f"当前检测到 {len(speakers)} 位说话人。" if speakers else "说话人身份仍待确认。"
        ),
        "keywords": keywords,
    }


def conversation_metrics(turns: list[dict], user_speaker_id: str) -> dict:
    user_turns = [turn for turn in turns if turn.get("speaker_id") == user_speaker_id]
    user_ms = sum(max(0, turn["end_ms"] - turn["start_ms"]) for turn in user_turns)
    all_ms = sum(max(0, turn["end_ms"] - turn["start_ms"]) for turn in turns)
    return {
        "user_speaking_ms": user_ms,
        "speaking_share": round(user_ms / all_ms, 4) if all_ms else 0,
        "user_turn_count": len(user_turns),
        "total_turn_count": len(turns),
    }


def interaction_events(analysis: dict, user_speaker_id: str, marker_ids: list[str], native: str = "zh", target: str = "en") -> list[dict]:
    turns = analysis.get("turns", [])
    events: list[dict] = []
    used: set[tuple[str, str]] = set()

    def append(event_type: str, evidence: list[dict], confidence: float, insight: dict) -> None:
        if not evidence:
            return
        key = (event_type, evidence[-1]["id"])
        if key in used or len(events) >= 5:
            return
        used.add(key)
        ids = [item["id"] for item in evidence]
        events.append({
            "id": f"{event_type.lower()}_{len(events) + 1:03d}",
            "type": event_type,
            "start_ms": evidence[0]["start_ms"],
            "end_ms": evidence[-1]["end_ms"],
            "turn_ids": ids,
            "marker_ids": marker_ids[:1],
            "confidence": confidence,
            "insight": {**localize_insight(insight, event_type, native, target), "evidence_turn_ids": ids},
        })

    for index, turn in enumerate(turns):
        if turn.get("speaker_id") != user_speaker_id:
            continue
        text = str(turn.get("text", ""))
        words = text.split()
        previous = turns[index - 1] if index else None
        following = turns[index + 1] if index + 1 < len(turns) else None
        partner_before = previous and previous.get("speaker_id") != user_speaker_id
        context = [item for item in (previous, turn, following) if item and (item is turn or item.get("speaker_id") != user_speaker_id)]
        if partner_before and (len(words) <= 7 if target == "en" else len(text.strip()) <= 14):
            append("TOPIC_DEVELOPMENT", context, 0.58, {
                "observation": "对方说完后，你给出了一个较简短的回应。",
                "context": "简短回应可能完全合适；如果想主动延续话题，可以再补充一个细节。",
                "suggestion": "补充一个理由、例子或自然的追问。",
                "example": "I think that could work because everyone can join. How about you?",
            })
        if re.search(r"[?？]|どう|いかが|ですか|ますか|吗|呢|\b(what|why|how|when|where|who|do you|could you)\b", text, re.I):
            append("FOLLOW_UP_QUESTION", [turn] + ([following] if following and following.get("speaker_id") != user_speaker_id else []), 0.72, {
                "observation": "你用问题把发言机会交还给了对方。",
                "context": "自然的追问能让双方继续围绕同一主题交换信息。",
                "suggestion": "先简短回应对方，再提出具体追问。",
                "example": "That sounds interesting. What made you decide to try it?",
            })
        if (len(words) >= 45 if target == "en" else len(text.strip()) >= 90) or max(0, turn["end_ms"] - turn["start_ms"]) >= 20000:
            append("TURN_BALANCE", [turn] + ([following] if following and following.get("speaker_id") != user_speaker_id else []), 0.64, {
                "observation": "这一轮持续时间较长，包含较多信息。",
                "context": "长回答并不一定有问题，也可以留一个明确入口让对方加入。",
                "suggestion": "在完整观点后暂停，并邀请对方回应。",
                "example": "That is how I see it. What has your experience been like?",
            })
        if re.search(r"もう一度|聞き取れ|どういう意味|什么意思|没听清|再说一遍|\b(could you repeat|what do you mean|do you mean|sorry|i didn't catch|can you explain)\b", text, re.I):
            append("CLARIFICATION", ([previous] if previous else []) + [turn], 0.78, {
                "observation": "你主动指出了没有听清或需要澄清的部分。",
                "context": "请求澄清可以减少误解。",
                "suggestion": "具体指出需要重复或解释的词句。",
                "example": "Sorry, I didn't catch the last part. Could you say that again?",
            })
    return events



def real_payload(conversation: ConversationSession, transcription: dict, markers: list[Marker], execution: dict) -> dict:
    diarization = transcription.get("diarization", {"status": "unavailable"})
    complete = diarization.get("status") == "complete"
    turns = transcription["turns"]
    return {
        "schema_version": "speech-analysis.v2",
        "mode": "real",
        "notice": "转写和说话人时间线来自真实录音。请确认哪位说话人是你。" if complete else "转写来自真实录音；当前无法可靠区分说话人。",
        "summary": conversation_summary(conversation, turns),
        "asr": {"model": transcription.get("model"), "language": transcription.get("language"), "engine": transcription.get("engine")},
        "diarization": diarization,
        "speakers": [{"id": speaker_id, "user_confirmed_identity": None} for speaker_id in transcription.get("speakers") or ["SPEAKER_UNKNOWN"]],
        "turns": turns,
        "events": [],
        "markers": [{"id": item.id, "timestamp_ms": item.timestamp_ms} for item in markers],
        "execution": execution,
    }


def process_speech_job(job_id: str) -> dict:
    db = SessionLocal()
    temp_path: Path | None = None
    cloud_path: Path | None = None
    cloud_object_key: str | None = None
    retryable = False
    try:
        job = db.get(AnalysisJob, job_id)
        if not job:
            return {"status": "missing", "retryable": False}
        conversation = db.get(ConversationSession, job.session_id)
        if not conversation or not conversation.audio_object_key:
            raise RuntimeError("没有可分析的录音")
        payload = dict(job.payload_json or {})
        job.requested_backend = "qwen"
        job.status = "running"
        job.progress = 0.1
        job.started_at = datetime.now(timezone.utc)
        job.attempt_count += 1
        conversation.processing_status = "transcribing"
        db.commit()

        cloud_consent = bool((payload.get("cloud_audio_consent") or {}).get("accepted"))
        if not cloud_consent:
            raise SpeechProviderError(
                "CLOUD_AUDIO_CONSENT_REQUIRED",
                "使用千问语音服务前必须单独同意上传本次录音。",
                retryable=False,
            )
        provider = QwenSpeechProvider()
        if not provider.available:
            raise SpeechProviderError("QWEN_NOT_CONFIGURED", "尚未配置千问 API Key。", retryable=False)
        job.provider = provider.name
        job.provider_model = provider.model
        existing_task_id = job.provider_task_id
        db.commit()

        markers = list(db.query(Marker).filter(Marker.session_id == conversation.id).order_by(Marker.timestamp_ms))
        audio = get_storage().get(conversation.audio_object_key)
        suffix = Path(conversation.audio_object_key).suffix or ".webm"
        fd, name = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        temp_path = Path(name)
        temp_path.write_bytes(audio)
        language_hints = list(payload.get("language_hints") or ["en", "zh"])
        speaker_policy = dict(payload.get("speaker_policy") or {"mode": "auto", "min_count": 1, "max_count": 8})
        started = time.perf_counter()

        def remember_task(task_id: str) -> None:
            current = db.get(AnalysisJob, job_id)
            if current:
                current.provider_task_id = task_id
                current.progress = 0.3
                db.commit()

        provider_path = temp_path
        audio_url = None
        preparation_ms = 0
        if not existing_task_id:
            cloud_path = prepare_cloud_audio(temp_path)
            provider_path = cloud_path
            preparation_ms = round((time.perf_counter() - started) * 1000)
            if settings.qwen_audio_url_mode == "presigned" and provider.fast_audio_duration(cloud_path, speaker_policy) is None:
                cloud_object_key = f"provider-temp/qwen/{job.id}.flac"
                storage = get_storage()
                storage.put(cloud_object_key, cloud_path.read_bytes(), "audio/flac")
                audio_url = storage.presigned_get(cloud_object_key, expires_minutes=60)
        provider_started = time.perf_counter()
        transcription = provider.analyze(
            provider_path,
            language_hints=language_hints,
            speaker_policy=speaker_policy,
            audio_url=audio_url,
            existing_task_id=existing_task_id,
            on_task_submitted=remember_task,
        )
        latency_ms = round((time.perf_counter() - started) * 1000)
        execution = {
            "provider": "qwen",
            "model": transcription.get("model") or job.provider_model,
            "provider_task_id": job.provider_task_id,
            "latency_ms": latency_ms,
            "preparation_ms": preparation_ms,
            "provider_ms": round((time.perf_counter() - provider_started) * 1000),
            "processing_route": transcription.get("processing_route", "file-task"),
            "audio_duration_ms": transcription.get("audio_duration_ms") or conversation.duration_ms,
            "retry_count": max(0, job.attempt_count - 1) + int(transcription.get("provider_retry_count") or 0),
            "resumed_existing_task": bool(transcription.get("resumed_existing_task")),
            "usage": transcription.get("provider_usage") or {
                "input_tokens": None,
                "output_tokens": None,
                "estimated_cost_cny": None,
            },
        }
        analysis = real_payload(conversation, transcription, markers, execution)
        conversation.analysis_json = analysis
        owner = db.get(User, conversation.owner_id)
        if owner and owner.voiceprint_json:
            try:
                from .voiceprint import match
                enrolled_at = owner.voiceprint_json.get("created_at")
                identity = match(conversation, owner.voiceprint_json)
                db.refresh(owner)
                if not owner.voiceprint_json or owner.voiceprint_json.get("created_at") != enrolled_at:
                    identity = {"status": "not_enrolled"}
                analysis["voiceprint_match"] = identity
                if identity.get("status") == "matched":
                    conversation.user_speaker_id = identity["speaker_id"]
                    analysis["identity_source"] = "voiceprint"
                    analysis["user_speaker_id"] = identity["speaker_id"]
                    analysis["metrics"] = conversation_metrics(analysis.get("turns", []), conversation.user_speaker_id)
                    analysis["events"] = interaction_events(analysis, conversation.user_speaker_id, [marker.id for marker in markers], owner.preference.native_language, conversation.target_language)
                    analysis["notice"] = "已通过声纹匹配你的发言，可随时手动更正。"
            except Exception:
                analysis["voiceprint_match"] = {"status": "unavailable"}
            conversation.analysis_json = dict(analysis)
        conversation.transcript_version += 1
        conversation.processing_status = "ready"
        conversation.failure_reason = None
        job.status = "complete"
        job.progress = 1
        job.error_code = None
        job.error_message = None
        job.result_json = {"execution": execution}
        job.finished_at = datetime.now(timezone.utc)
        preference = db.get(UserPreference, conversation.owner_id)
        review_job = None
        if preference and preference.ai_enabled and analysis.get("turns"):
            review_job = AnalysisJob(owner_id=conversation.owner_id, session_id=conversation.id, kind="ai_review", payload_json={"force": False})
            db.add(review_job)
        db.commit()
        if review_job:
            try:
                from ..workers.tasks import process_ai, process_ai_job_now
                if settings.celery_eager:
                    process_ai_job_now(review_job.id)
                else:
                    process_ai.delay(review_job.id)
            except Exception:
                db.rollback()
                review_job.status = "failed"
                review_job.error_message = "复盘生成未能启动，请重试"
                db.commit()
        return {"status": "complete", "retryable": False, "execution": execution}
    except Exception as error:
        db.rollback()
        retryable = isinstance(error, SpeechProviderError) and error.retryable
        job = db.get(AnalysisJob, job_id)
        if job:
            job.status = "failed"
            job.error_code = error.code if isinstance(error, SpeechProviderError) else "SPEECH_PIPELINE_FAILED"
            job.error_message = str(error)[:1000]
            job.result_json = {"retryable": retryable, "attempt_count": job.attempt_count}
            job.finished_at = datetime.now(timezone.utc)
            if isinstance(error, SpeechProviderError) and error.code == "QWEN_TASK_TERMINATED":
                job.provider_task_id = None
            conversation = db.get(ConversationSession, job.session_id)
            if conversation:
                conversation.processing_status = "failed"
                conversation.failure_reason = str(error)[:1000]
            db.commit()
        return {
            "status": "failed",
            "retryable": retryable,
            "error_code": error.code if isinstance(error, SpeechProviderError) else "SPEECH_PIPELINE_FAILED",
            "error": str(error),
        }
    finally:
        if cloud_object_key:
            try:
                get_storage().delete(cloud_object_key)
            except Exception:
                pass
        if cloud_path:
            cloud_path.unlink(missing_ok=True)
        if temp_path:
            temp_path.unlink(missing_ok=True)
        db.close()
