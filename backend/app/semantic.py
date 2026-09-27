from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


SEMANTIC_MODE = os.getenv("BEYOND_WORDS_SEMANTIC_MODE", "rules").lower()
SEMANTIC_BASE_URL = os.getenv("BEYOND_WORDS_SEMANTIC_BASE_URL", "").rstrip("/")
SEMANTIC_API_KEY = os.getenv("BEYOND_WORDS_SEMANTIC_API_KEY", "")
SEMANTIC_MODEL = os.getenv("BEYOND_WORDS_SEMANTIC_MODEL", "")
ALLOWED_EVENT_TYPES = {"TOPIC_DEVELOPMENT", "FOLLOW_UP_QUESTION", "TURN_BALANCE", "CLARIFICATION"}


def semantic_status() -> dict[str, Any]:
    configured = bool(SEMANTIC_BASE_URL and SEMANTIC_MODEL and SEMANTIC_API_KEY)
    return {
        "mode": SEMANTIC_MODE,
        "configured": configured,
        "provider": "openai-compatible" if configured else "local-rules",
        "model": SEMANTIC_MODEL or None,
        "audio_shared": False,
    }


def _extract_json(content: str) -> dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return json.loads(content)


def _validate_events(payload: dict[str, Any], turns: list[dict], marker_ids: list[str]) -> list[dict]:
    turn_by_id = {turn["id"]: turn for turn in turns}
    result = []
    for item in payload.get("events", [])[:5]:
        event_type = item.get("type")
        evidence_ids = [turn_id for turn_id in item.get("evidence_turn_ids", []) if turn_id in turn_by_id]
        if event_type not in ALLOWED_EVENT_TYPES or not evidence_ids:
            continue
        evidence = [turn_by_id[turn_id] for turn_id in evidence_ids]
        fields = {name: str(item.get(name, "")).strip() for name in ("observation", "context", "suggestion", "example")}
        if any(not value for value in fields.values()):
            continue
        result.append({
            "id": f"semantic_{len(result) + 1:03d}",
            "type": event_type,
            "start_ms": min(turn["start_ms"] for turn in evidence),
            "end_ms": max(turn["end_ms"] for turn in evidence),
            "turn_ids": evidence_ids,
            "marker_ids": marker_ids[:1],
            "confidence": max(0.0, min(1.0, float(item.get("confidence", 0.5)))),
            "insight": {**fields, "evidence_turn_ids": evidence_ids},
        })
    return result


def analyze_semantics(turns: list[dict], user_speaker_id: str, marker_ids: list[str]) -> list[dict] | None:
    status = semantic_status()
    if SEMANTIC_MODE not in {"auto", "openai-compatible"} or not status["configured"]:
        return None
    compact_turns = [
        {"id": turn["id"], "speaker": "USER" if turn.get("speaker_id") == user_speaker_id else "PARTNER", "text": turn.get("text", "")}
        for turn in turns
    ]
    system = (
        "You analyze dyadic English-learning conversations. Return JSON only with an events array. "
        "Allowed types: TOPIC_DEVELOPMENT, FOLLOW_UP_QUESTION, TURN_BALANCE, CLARIFICATION. "
        "Every claim must cite one or more supplied turn ids in evidence_turn_ids. Avoid personality, intent, "
        "proficiency, emotion, or clinical inferences. Write observation, context, suggestion, and example in concise Chinese."
    )
    body = json.dumps({
        "model": SEMANTIC_MODEL,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps({"turns": compact_turns}, ensure_ascii=False)},
        ],
    }).encode("utf-8")
    request = urllib.request.Request(
        f"{SEMANTIC_BASE_URL}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {SEMANTIC_API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            reply = json.loads(response.read().decode("utf-8"))
        content = reply["choices"][0]["message"]["content"]
        events = _validate_events(_extract_json(content), turns, marker_ids)
        return events or None
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, urllib.error.URLError):
        return None
