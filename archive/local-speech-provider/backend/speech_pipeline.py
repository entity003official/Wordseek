from pathlib import Path

from .asr import transcribe_audio
from .diarization import assign_speakers, diarization_status, diarize_audio


def analyze_audio(path: Path, speaker_policy: dict | None = None) -> dict:
    transcription = transcribe_audio(path)
    status = diarization_status()
    if not status["available"]:
        return {
            **transcription,
            "speakers": ["SPEAKER_UNKNOWN"],
            "diarization": {**status, "status": "unavailable"},
        }
    try:
        diarization = diarize_audio(path, speaker_policy=speaker_policy)
        attributed = assign_speakers(transcription, diarization)
        return {
            **attributed,
            "diarization": {
                **status,
                "status": "complete",
                "speaker_count": len(diarization["speakers"]),
            },
        }
    except Exception as error:
        return {
            **transcription,
            "speakers": ["SPEAKER_UNKNOWN"],
            "diarization": {
                **status,
                "status": "failed",
                "reason": str(error),
            },
        }

