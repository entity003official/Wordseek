from __future__ import annotations

import re


PATTERNS = (
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "[邮箱]"),
    (re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)"), "[电话]"),
    (re.compile(r"https?://\S+|www\.\S+", re.I), "[网址]"),
    (re.compile(r"(?<!\d)\d{15,18}[0-9Xx]?(?!\d)"), "[身份标识]"),
)


def redact_text(text: str, aliases: list[str] | None = None) -> str:
    redacted = text
    for pattern, replacement in PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    for alias in sorted((item.strip() for item in aliases or [] if item.strip()), key=len, reverse=True):
        redacted = re.sub(re.escape(alias), "[姓名]", redacted, flags=re.I)
    return redacted


def redact_turns(turns: list[dict], aliases: list[str] | None = None) -> list[dict]:
    return [
        {
            "id": turn.get("id"),
            "speaker_id": turn.get("speaker_id"),
            "start_ms": turn.get("start_ms"),
            "end_ms": turn.get("end_ms"),
            "text": redact_text(str(turn.get("text", "")), aliases),
        }
        for turn in turns
    ]
