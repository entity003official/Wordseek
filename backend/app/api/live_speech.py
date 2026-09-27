from __future__ import annotations

import asyncio
import hmac
import json
import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from websockets.asyncio.client import connect

from ..core.config import settings
from ..core.security import token_hash
from ..db import SessionLocal
from ..models import ConversationSession
from ..services.auth import SESSION_COOKIE, resolve_session
from ..services.speech import real_payload
from ..speech import QwenSpeechProvider

router = APIRouter(tags=["实时语音"])
_active: set[str] = set()


@router.websocket("/sessions/{session_id}/live")
async def live_speech(socket: WebSocket, session_id: str):
    # WebSocket requests do not pass through HTTP CSRF middleware.
    if socket.headers.get("origin") not in settings.cors_origins:
        await socket.close(code=1008)
        return
    with SessionLocal() as db:
        resolved = resolve_session(db, socket.cookies.get(SESSION_COOKIE))
        item = db.get(ConversationSession, session_id)
        if not resolved or not item or item.owner_id != resolved[0].id or item.audio_object_key:
            await socket.close(code=1008)
            return
        owner_id, csrf_hash = resolved[0].id, resolved[1].csrf_hash
        language_hints = list(dict.fromkeys([item.target_language, resolved[0].preference.native_language]))
    await socket.accept()
    sentences: dict[int, dict] = {}
    task_id = uuid.uuid4().hex
    claimed = False
    finished = False
    tasks: list[asyncio.Task] = []
    try:
        hello = await asyncio.wait_for(socket.receive_json(), 10)
        if hello.get("consent") is not True or not hmac.compare_digest(token_hash(str(hello.get("csrf", ""))), csrf_hash):
            await socket.close(code=1008)
            return
        if owner_id in _active:
            await socket.send_json({"type": "error", "message": "已有实时录音正在进行，请先结束。"})
            return
        _active.add(owner_id)
        claimed = True
        key = settings.read_qwen_api_key()
        if not key:
            raise ValueError("missing key")
        host = urlparse(settings.qwen_api_base_url).netloc
        async with connect(f"wss://{host}/api-ws/v1/inference", additional_headers={"Authorization": f"Bearer {key}"}, open_timeout=12, close_timeout=3, max_size=2**20) as upstream:
            await upstream.send(json.dumps({"header": {"action": "run-task", "task_id": task_id, "streaming": "duplex"}, "payload": {"task_group": "audio", "task": "asr", "function": "recognition", "model": "qwen-audio-3.1-asr-flash-streaming", "parameters": {"format": "pcm", "sample_rate": 16000, "language_hints": language_hints}, "input": {}}}))
            started = json.loads(await asyncio.wait_for(upstream.recv(), 15))
            if started.get("header", {}).get("event") != "task-started":
                raise ValueError("upstream start rejected")
            await socket.send_json({"type": "ready"})

            async def send_audio():
                total = 0
                while True:
                    message = await asyncio.wait_for(socket.receive(), 45)
                    if message["type"] == "websocket.disconnect":
                        raise WebSocketDisconnect()
                    data = message.get("bytes")
                    if data is not None:
                        total += len(data)
                        if len(data) > 65536 or len(data) % 2 or total > 16000 * 2 * 3600:
                            raise ValueError("audio limit")
                        await upstream.send(data)
                    elif json.loads(message.get("text") or "{}").get("type") == "finish":
                        await upstream.send(json.dumps({"header": {"action": "finish-task", "task_id": task_id, "streaming": "duplex"}, "payload": {"input": {}}}))
                        return

            async def receive_results():
                nonlocal finished
                async for raw in upstream:
                    event = json.loads(raw)
                    kind = event.get("header", {}).get("event")
                    if kind == "task-failed":
                        raise ValueError("upstream recognition failed")
                    if kind == "task-finished":
                        finished = True
                        return
                    sentence = event.get("payload", {}).get("output", {}).get("sentence") or {}
                    if kind == "result-generated" and sentence.get("text") and not sentence.get("heartbeat"):
                        sid = int(sentence.get("sentence_id") or sentence.get("begin_time") or 0)
                        if sentence.get("sentence_end"):
                            sentences[sid] = sentence
                        await socket.send_json({"type": "sentence", "id": sid, "text": sentence["text"], "start_ms": sentence.get("begin_time") or 0, "end_ms": sentence.get("end_time") or 0, "final": bool(sentence.get("sentence_end"))})

            sender = asyncio.create_task(send_audio())
            receiver = asyncio.create_task(receive_results())
            tasks = [sender, receiver]
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED, timeout=3600)
            if not done:
                raise TimeoutError()
            for task in done:
                task.result()
            if sender in done and not receiver.done():
                await asyncio.wait_for(receiver, 15)
            if not finished:
                raise ValueError("incomplete stream")
    except (Exception, WebSocketDisconnect):
        try:
            await socket.send_json({"type": "error", "message": "实时转写已中断，录音仍在本机继续，结束后可重新转写。"})
        except Exception:
            pass
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if claimed:
            try:
                # Save only provider-final sentences, never client-supplied text.
                if sentences:
                    with SessionLocal() as db:
                        item = db.get(ConversationSession, session_id)
                        if item and item.owner_id == owner_id and not item.analysis_json:
                            result = QwenSpeechProvider._normalize({"transcripts": [{"sentences": list(sentences.values())}]}, {})
                            result["model"] = "qwen-audio-3.1-asr-flash-streaming"
                            result["diarization"] = {"status": "unavailable", "reason": "streaming_pending_diarization"}
                            item.analysis_json = real_payload(item, result, [], {"provider": "qwen", "model": result["model"], "processing_route": "streaming", "stream_complete": finished})
                            item.transcript_version += 1
                            db.commit()
            finally:
                _active.discard(owner_id)
        try:
            if finished:
                await socket.send_json({"type": "finished"})
            await socket.close()
        except Exception:
            pass
