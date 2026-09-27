from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.speech import QwenSpeechProvider, prepare_cloud_audio


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Qwen speech analysis on an evaluation audio file.")
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--language", action="append", default=[])
    parser.add_argument("--expected-speakers", type=int, choices=range(1, 9))
    parser.add_argument("--task-state", type=Path, help="Qwen task checkpoint used to resume polling without resubmitting.")
    args = parser.parse_args()
    if not args.audio.is_file():
        raise SystemExit(f"Audio file not found: {args.audio}")

    started = time.perf_counter()
    state_path = args.task_state or args.output.with_suffix(".qwen-task.json")
    provider_task_id = None
    if state_path.is_file():
        provider_task_id = json.loads(state_path.read_text(encoding="utf-8")).get("task_id")

    def checkpoint(task_id: str) -> None:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"task_id": task_id}, indent=2), encoding="utf-8")

    cloud_audio = prepare_cloud_audio(args.audio.resolve())
    provider = QwenSpeechProvider()
    try:
        result = provider.analyze(
            cloud_audio,
            language_hints=args.language or ["en"],
            speaker_policy={
                "mode": "expected" if args.expected_speakers else "auto",
                "min_count": 1,
                "max_count": 8,
                "expected_count": args.expected_speakers,
            },
            existing_task_id=provider_task_id,
            on_task_submitted=checkpoint,
        )
    finally:
        cloud_audio.unlink(missing_ok=True)
    provider_task_id = json.loads(state_path.read_text(encoding="utf-8"))["task_id"]

    payload = {
        "audio_path": str(args.audio.resolve()),
        "engine": result.get("engine"),
        "model": result.get("model"),
        "language": result.get("language"),
        "turns": result.get("turns", []),
        "speakers": result.get("speakers", []),
        "diarization": result.get("diarization"),
        "execution": {
            "provider": "qwen",
            "model": result.get("model"),
            "provider_task_id": provider_task_id,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "audio_duration_ms": result.get("audio_duration_ms"),
            "retry_count": result.get("provider_retry_count", 0),
            "resumed_existing_task": result.get("resumed_existing_task", False),
            "usage": result.get("provider_usage", {}),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Transcribed {len(payload['turns'])} segments with {payload['model']}: {args.output}")


if __name__ == "__main__":
    main()
