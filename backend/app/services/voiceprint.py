"""Local speaker embeddings; only explicitly enrolled owners can be matched."""
from __future__ import annotations
import os
import subprocess
import tempfile
import threading
from functools import lru_cache
from pathlib import Path
import numpy as np
from fastapi import HTTPException
from ..core.config import ROOT_DIR
from ..speech.providers import resolve_ffmpeg
from .storage import get_storage

MODEL_ID = "3dspeaker-eres2net-base-v1"
MODEL_PATH = Path(os.getenv("BEYOND_WORDS_VOICEPRINT_MODEL", ROOT_DIR / "models/voiceprint/3dspeaker.onnx"))
_lock = threading.Lock()

@lru_cache(maxsize=1)
def extractor():
    import sherpa_onnx
    if not MODEL_PATH.is_file() or not MODEL_PATH.with_suffix(".ready").is_file():
        raise HTTPException(503, "声纹模型尚未安装，请先手动确认")
    config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(MODEL_PATH), num_threads=2, provider="cpu")
    if not config.validate():
        raise HTTPException(503, "声纹模型无法加载，请先手动确认")
    return sherpa_onnx.SpeakerEmbeddingExtractor(config)

def embedding(conversation, speaker_id: str, minimum_seconds: float):
    turns = (conversation.analysis_json or {}).get("turns", [])
    if not conversation.audio_object_key:
        raise HTTPException(409, "原始录音不存在，无法识别声纹")
    # Exclude overlapping speech: mixed voices must never become the enrollment template.
    ranges = []
    for turn in turns:
        start, end = turn.get("start_ms", 0), turn.get("end_ms", 0)
        if turn.get("speaker_id") != speaker_id or end - start < 1000:
            continue
        if any(other.get("speaker_id") != speaker_id and other.get("start_ms", 0) < end and other.get("end_ms", 0) > start for other in turns):
            continue
        ranges.append((start / 1000, (end - start) / 1000))
    ranges.sort(key=lambda item: item[1], reverse=True)
    if sum(duration for _, duration in ranges) < minimum_seconds:
        raise HTTPException(409, "清晰独立发言太短，请使用至少 8 秒的本人发言录入声纹")
    chunks = []
    seconds = 0.0
    suffix = Path(conversation.audio_object_key).suffix
    with tempfile.TemporaryDirectory(prefix="bw-voiceprint-") as folder:
        source = Path(folder) / ("audio" + suffix)
        source.write_bytes(get_storage().get(conversation.audio_object_key))
        for start, duration in ranges[:12]:
            duration = min(duration, 30 - seconds)
            if duration < 1:
                break
            try:
                result = subprocess.run([resolve_ffmpeg(), "-nostdin", "-v", "error", "-ss", str(start), "-i", str(source), "-t", str(duration), "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "pipe:1"], capture_output=True, check=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except (OSError, subprocess.SubprocessError):
                raise HTTPException(422, "无法读取录音，请换一段清晰录音")
            samples = np.frombuffer(result.stdout, dtype=np.float32).copy()
            if samples.size and np.isfinite(samples).all() and float(np.sqrt(np.mean(samples ** 2))) > 0.003:
                chunks.append(samples)
                seconds += samples.size / 16000
    if seconds < minimum_seconds:
        raise HTTPException(409, "有效声音不足，请换一段清晰录音")
    with _lock:
        model = extractor()
        stream = model.create_stream()
        stream.accept_waveform(sample_rate=16000, waveform=np.concatenate(chunks))
        stream.input_finished()
        if not model.is_ready(stream):
            raise HTTPException(422, "无法提取声纹，请换一段录音")
        vector = np.asarray(model.compute(stream), dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(vector).all() or norm < 1e-8:
        raise HTTPException(422, "声纹提取失败，请换一段录音")
    return (vector / norm).tolist(), round(seconds, 1)

def match(conversation, template):
    if not template or template.get("model") != MODEL_ID:
        return {"status": "not_enrolled"}
    reference = np.asarray(template["embedding"], dtype=np.float32)
    scores = []
    speakers = (conversation.analysis_json or {}).get("speakers", [])
    for speaker in speakers[:12]:
        if speaker["id"] == "SPEAKER_UNKNOWN":
            continue
        try:
            vector, _ = embedding(conversation, speaker["id"], 4)
            score = float(np.dot(reference, vector))
            scores.append((score, speaker["id"]))
        except HTTPException as error:
            if error.status_code == 503:
                return {"status": "unavailable"}
    if len(scores) != len([s for s in speakers if s["id"] != "SPEAKER_UNKNOWN"]):
        return {"status": "uncertain"}
    scores.sort(reverse=True)
    # Conservative heuristic, not a probability or an authentication guarantee.
    if not scores or scores[0][0] < 0.75 or (len(scores) > 1 and scores[0][0] - scores[1][0] < 0.15):
        return {"status": "uncertain"}
    return {"status": "matched", "speaker_id": scores[0][1]}
