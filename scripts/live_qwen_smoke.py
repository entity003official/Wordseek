"""Optional paid Qwen Flash smoke test.

The command prints metadata only. It never prints the API key or transcript text.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

from backend.app.speech import QwenSpeechProvider


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a paid Qwen short-audio smoke test.")
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--seconds", type=float, default=12.0)
    args = parser.parse_args()
    if not args.audio.is_file():
        raise SystemExit(f"Audio file not found: {args.audio}")

    with tempfile.TemporaryDirectory(prefix="beyond-words-qwen-") as directory:
        clip = Path(directory) / "short.flac"
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-ss", str(args.start), "-t", str(args.seconds), "-i", str(args.audio.resolve()),
                "-vn", "-ac", "1", "-ar", "16000", "-c:a", "flac", str(clip),
            ],
            check=True,
            timeout=120,
        )
        started = time.perf_counter()
        result = QwenSpeechProvider().transcribe_short(clip, "audio/flac", ["en"])
        latency_ms = round((time.perf_counter() - started) * 1000)

    payload = {
        "audio_path": str(args.audio.resolve()),
        "clip_start_seconds": args.start,
        "clip_duration_seconds": args.seconds,
        "provider": result.get("provider"),
        "model": result.get("model"),
        "language": result.get("language"),
        "text": result.get("text"),
        "execution": {
            "latency_ms": latency_ms,
            "retry_count": result.get("retry_count", 0),
            "usage": result.get("usage") or {},
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "Qwen short-audio smoke passed: "
        f"model={payload['model']}, text_chars={len(payload['text'] or '')}, "
        f"latency_ms={latency_ms}, retry_count={payload['execution']['retry_count']}, "
        f"output={args.output}"
    )


if __name__ == "__main__":
    main()
