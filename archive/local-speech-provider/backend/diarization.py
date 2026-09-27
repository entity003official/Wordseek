import importlib.util
import os
import re
import threading
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parents[2] / ".env")
except ImportError:
    pass


DIARIZATION_MODE = os.getenv("BEYOND_WORDS_DIARIZATION_MODE", "auto").lower()
DIARIZATION_MODEL = os.getenv(
    "BEYOND_WORDS_DIARIZATION_MODEL", "pyannote/speaker-diarization-community-1"
)
DIARIZATION_DEVICE = os.getenv("BEYOND_WORDS_DIARIZATION_DEVICE", "auto").lower()
DIARIZATION_MIN_SPEAKERS = int(os.getenv("BEYOND_WORDS_DIARIZATION_MIN_SPEAKERS", "1"))
DIARIZATION_MAX_SPEAKERS = int(os.getenv("BEYOND_WORDS_DIARIZATION_MAX_SPEAKERS", "8"))

_pipeline: Any | None = None
_pipeline_lock = threading.Lock()


def _access_token() -> str | None:
    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
    if token:
        return token
    try:
        from huggingface_hub import get_token

        return get_token()
    except (ImportError, OSError):
        return None


def _is_local_model() -> bool:
    return Path(DIARIZATION_MODEL).expanduser().exists()


def _resolved_device() -> str:
    if DIARIZATION_DEVICE in {"cpu", "cuda"}:
        return DIARIZATION_DEVICE
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def diarization_status() -> dict:
    package_available = importlib.util.find_spec("pyannote") is not None
    has_access = _is_local_model() or bool(_access_token())
    enabled = DIARIZATION_MODE not in {"off", "mock", "disabled"}
    available = enabled and package_available and has_access
    if not enabled:
        reason = "disabled"
    elif not package_available:
        reason = "package_missing"
    elif not has_access:
        reason = "access_token_or_local_model_missing"
    else:
        reason = None
    return {
        "available": available,
        "model": DIARIZATION_MODEL,
        "device": _resolved_device(),
        "min_speakers": DIARIZATION_MIN_SPEAKERS,
        "max_speakers": DIARIZATION_MAX_SPEAKERS,
        "reason": reason,
    }


def load_pipeline() -> Any:
    global _pipeline
    status = diarization_status()
    if not status["available"]:
        raise RuntimeError(f"Speaker diarization is unavailable: {status['reason']}")
    if _pipeline is not None:
        return _pipeline
    with _pipeline_lock:
        if _pipeline is not None:
            return _pipeline
        import torch
        from pyannote.audio import Pipeline

        kwargs = {}
        if not _is_local_model():
            kwargs["token"] = _access_token()
        _pipeline = Pipeline.from_pretrained(DIARIZATION_MODEL, **kwargs)
        _pipeline.to(torch.device(_resolved_device()))
        return _pipeline


def diarize_audio(path: Path, speaker_policy: dict | None = None) -> dict:
    pipeline = load_pipeline()
    policy = speaker_policy or {}
    expected = policy.get("expected_count")
    options = (
        {"num_speakers": int(expected)}
        if expected
        else {
            "min_speakers": int(policy.get("min_count", DIARIZATION_MIN_SPEAKERS)),
            "max_speakers": int(policy.get("max_count", DIARIZATION_MAX_SPEAKERS)),
        }
    )
    try:
        output = pipeline(str(path), **options)
    except Exception:
        if _resolved_device() != "cuda":
            raise
        import torch

        # Community-1 can exceed the VRAM available on some laptop GPUs.
        # Retrying on CPU is slower but preserves the private local workflow.
        pipeline.to(torch.device("cpu"))
        output = pipeline(str(path), **options)
    annotation = getattr(output, "exclusive_speaker_diarization", None)
    if annotation is None:
        annotation = output.speaker_diarization
    raw_segments = [
        {
            "start_ms": round(float(turn.start) * 1000),
            "end_ms": round(float(turn.end) * 1000),
            "speaker_id": str(speaker),
        }
        for turn, speaker in annotation
    ]
    segments = _canonicalize_speakers(raw_segments)
    return {
        "model": DIARIZATION_MODEL,
        "segments": segments,
        "speakers": sorted({segment["speaker_id"] for segment in segments}),
    }


def _canonicalize_speakers(segments: list[dict]) -> list[dict]:
    first_seen: dict[str, str] = {}
    result = []
    for segment in sorted(segments, key=lambda item: (item["start_ms"], item["end_ms"])):
        source_id = segment["speaker_id"]
        if source_id not in first_seen:
            first_seen[source_id] = f"SPEAKER_{len(first_seen):02d}"
        result.append({**segment, "speaker_id": first_seen[source_id]})
    return result


def _overlap_ms(start_ms: int, end_ms: int, segment: dict) -> int:
    return max(0, min(end_ms, segment["end_ms"]) - max(start_ms, segment["start_ms"]))


def _speaker_for_range(start_ms: int, end_ms: int, segments: list[dict]) -> str:
    overlaps: dict[str, int] = {}
    for segment in segments:
        overlap = _overlap_ms(start_ms, end_ms, segment)
        if overlap:
            speaker_id = segment["speaker_id"]
            overlaps[speaker_id] = overlaps.get(speaker_id, 0) + overlap
    if overlaps:
        return max(overlaps.items(), key=lambda item: item[1])[0]
    if not segments:
        return "SPEAKER_UNKNOWN"
    midpoint = (start_ms + end_ms) / 2
    nearest = min(
        segments,
        key=lambda segment: abs(midpoint - (segment["start_ms"] + segment["end_ms"]) / 2),
    )
    return nearest["speaker_id"]


def _clean_text(parts: list[str]) -> str:
    text = " ".join(part.strip() for part in parts if part.strip())
    return re.sub(r"\s+([,.!?;:])", r"\1", text).strip()


def assign_speakers(transcription: dict, diarization: dict) -> dict:
    segments = diarization["segments"]
    words = transcription.get("words") or []
    if not words:
        turns = [
            {
                **turn,
                "speaker_id": _speaker_for_range(turn["start_ms"], turn["end_ms"], segments),
            }
            for turn in transcription.get("turns", [])
        ]
        return {**transcription, "turns": turns, "speakers": diarization["speakers"]}

    attributed_words = [
        {
            **word,
            "speaker_id": _speaker_for_range(word["start_ms"], word["end_ms"], segments),
        }
        for word in words
    ]
    groups: list[dict] = []
    for word in attributed_words:
        previous = groups[-1] if groups else None
        starts_new_turn = (
            previous is None
            or previous["speaker_id"] != word["speaker_id"]
            or word["start_ms"] - previous["end_ms"] > 1200
        )
        if starts_new_turn:
            groups.append({
                "speaker_id": word["speaker_id"],
                "start_ms": word["start_ms"],
                "end_ms": word["end_ms"],
                "parts": [word["text"]],
            })
        else:
            previous["end_ms"] = word["end_ms"]
            previous["parts"].append(word["text"])

    turns = [
        {
            "id": f"turn_{index + 1:03d}",
            "speaker_id": group["speaker_id"],
            "start_ms": group["start_ms"],
            "end_ms": group["end_ms"],
            "text": _clean_text(group["parts"]),
        }
        for index, group in enumerate(groups)
        if _clean_text(group["parts"])
    ]
    return {
        **transcription,
        "turns": turns,
        "words": attributed_words,
        "speakers": diarization["speakers"],
    }

