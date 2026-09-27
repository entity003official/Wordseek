import importlib.util
import os
import threading
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parents[2] / ".env")
except ImportError:
    pass


MODEL_NAME = os.getenv("BEYOND_WORDS_ASR_MODEL", "small.en")
MODEL_DIR = Path(
    os.getenv("BEYOND_WORDS_ASR_MODEL_DIR", Path(__file__).parents[1] / "data" / "models")
).resolve()
ASR_MODE = os.getenv("BEYOND_WORDS_ASR_MODE", "auto").lower()
ASR_ENGINE = os.getenv("BEYOND_WORDS_ASR_ENGINE", "auto").lower()
ASR_DEVICE = os.getenv("BEYOND_WORDS_ASR_DEVICE", "auto").lower()
ASR_COMPUTE_TYPE = os.getenv("BEYOND_WORDS_ASR_COMPUTE_TYPE", "auto").lower()

_model: Any | None = None
_model_engine: str | None = None
_model_device: str | None = None
_model_lock = threading.Lock()


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _legacy_model_name() -> str:
    requested = MODEL_DIR / f"{MODEL_NAME}.pt"
    if requested.is_file():
        return MODEL_NAME
    tiny = MODEL_DIR / "tiny.en.pt"
    return "tiny.en" if tiny.is_file() else MODEL_NAME


def model_path() -> Path:
    return MODEL_DIR / f"{_legacy_model_name()}.pt"


def selected_engine() -> str | None:
    if ASR_MODE == "mock":
        return None
    if ASR_ENGINE in {"faster-whisper", "faster_whisper"}:
        return "faster-whisper" if _module_available("faster_whisper") else None
    if ASR_ENGINE in {"openai-whisper", "openai_whisper", "whisper"}:
        return "openai-whisper" if _module_available("whisper") and model_path().is_file() else None
    if _module_available("faster_whisper"):
        return "faster-whisper"
    if _module_available("whisper") and model_path().is_file():
        return "openai-whisper"
    return None


def _resolved_device() -> str:
    if ASR_DEVICE in {"cpu", "cuda"}:
        return ASR_DEVICE
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def _resolved_compute_type(device: str) -> str:
    if ASR_COMPUTE_TYPE != "auto":
        return ASR_COMPUTE_TYPE
    return "float16" if device == "cuda" else "int8"


def asr_status() -> dict:
    engine = selected_engine()
    device = _resolved_device()
    return {
        "available": engine is not None,
        "engine": engine,
        "model": MODEL_NAME if engine == "faster-whisper" else _legacy_model_name(),
        "device": device,
        "compute_type": _resolved_compute_type(device),
    }


def local_asr_available() -> bool:
    return selected_engine() is not None


def load_model(force_device: str | None = None) -> Any:
    global _model, _model_device, _model_engine
    engine = selected_engine()
    if not engine:
        raise RuntimeError("Local ASR model is not available")
    device = force_device or _resolved_device()
    if _model is not None and _model_engine == engine and _model_device == device:
        return _model
    with _model_lock:
        if _model is not None and _model_engine == engine and _model_device == device:
            return _model
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        if engine == "faster-whisper":
            from faster_whisper import WhisperModel

            _model = WhisperModel(
                MODEL_NAME,
                device=device,
                compute_type=_resolved_compute_type(device),
                download_root=str(MODEL_DIR),
            )
        else:
            import whisper

            _model = whisper.load_model(_legacy_model_name(), download_root=str(MODEL_DIR), device=device)
        _model_engine = engine
        _model_device = device
        return _model


def _transcribe_with_faster_whisper(path: Path, device: str) -> dict:
    model = load_model(device)
    segments_iter, info = model.transcribe(
        str(path),
        language="en",
        beam_size=5,
        vad_filter=True,
        word_timestamps=True,
        condition_on_previous_text=False,
    )
    segments = list(segments_iter)
    turns = []
    words = []
    for index, segment in enumerate(segments):
        text = str(segment.text).strip()
        if text:
            turns.append({
                "id": f"turn_{index + 1:03d}",
                "speaker_id": "SPEAKER_UNKNOWN",
                "start_ms": round(float(segment.start) * 1000),
                "end_ms": round(float(segment.end) * 1000),
                "text": text,
            })
        for word in segment.words or []:
            if word.start is None or word.end is None or not str(word.word).strip():
                continue
            words.append({
                "start_ms": round(float(word.start) * 1000),
                "end_ms": round(float(word.end) * 1000),
                "text": str(word.word),
            })
    return {
        "engine": "faster-whisper",
        "model": f"faster-whisper/{MODEL_NAME}",
        "language": getattr(info, "language", "en"),
        "turns": turns,
        "words": words,
    }


def _transcribe_with_openai_whisper(path: Path, device: str) -> dict:
    model = load_model(device)
    result = model.transcribe(
        str(path), language="en", task="transcribe", fp16=device == "cuda", word_timestamps=True
    )
    turns = []
    words = []
    for index, segment in enumerate(result.get("segments", [])):
        text = str(segment.get("text", "")).strip()
        if text:
            turns.append({
                "id": f"turn_{index + 1:03d}",
                "speaker_id": "SPEAKER_UNKNOWN",
                "start_ms": round(float(segment["start"]) * 1000),
                "end_ms": round(float(segment["end"]) * 1000),
                "text": text,
            })
        for word in segment.get("words", []):
            if word.get("start") is None or word.get("end") is None or not str(word.get("word", "")).strip():
                continue
            words.append({
                "start_ms": round(float(word["start"]) * 1000),
                "end_ms": round(float(word["end"]) * 1000),
                "text": str(word["word"]),
            })
    return {
        "engine": "openai-whisper",
        "model": f"openai-whisper/{_legacy_model_name()}",
        "language": result.get("language", "en"),
        "turns": turns,
        "words": words,
    }


def transcribe_audio(path: Path) -> dict:
    engine = selected_engine()
    if not engine:
        raise RuntimeError("Local ASR model is not available")
    device = _resolved_device()
    try:
        if engine == "faster-whisper":
            return _transcribe_with_faster_whisper(path, device)
        return _transcribe_with_openai_whisper(path, device)
    except Exception:
        if device != "cuda":
            raise
        # A CPU retry keeps the local MVP usable if CTranslate2 and the CUDA
        # runtime installed on Windows do not match.
        if engine == "faster-whisper":
            return _transcribe_with_faster_whisper(path, "cpu")
        return _transcribe_with_openai_whisper(path, "cpu")

