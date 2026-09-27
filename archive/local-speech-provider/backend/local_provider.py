"""Archived local provider adapter.

This module is not imported by the active application. Restore the adjacent
ASR/diarization modules into ``backend.app`` before re-enabling it.
"""

from pathlib import Path
from typing import Any

from .speech_pipeline import analyze_audio


class LocalSpeechProvider:
    name = "local"
    model = "faster-whisper+pyannote"

    def analyze(
        self,
        path: Path,
        *,
        language_hints: list[str],
        speaker_policy: dict[str, Any],
        audio_url: str | None = None,
        existing_task_id: str | None = None,
        on_task_submitted=None,
    ) -> dict[str, Any]:
        del language_hints, audio_url, existing_task_id, on_task_submitted
        return analyze_audio(path, speaker_policy=speaker_policy)
