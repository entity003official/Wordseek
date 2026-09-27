"""Archived local-only evaluation entry point.

Restore ``asr.py`` to ``backend/app/asr.py`` before running this historical
benchmark. Active evaluation uses Qwen only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.app.asr import transcribe_audio


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the archived local ASR provider.")
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = transcribe_audio(args.audio.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
