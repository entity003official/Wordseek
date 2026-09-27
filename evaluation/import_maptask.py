from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw" / "maptask"
DERIVED = ROOT / "derived" / "hcrc-maptask-q1ec1"


def main() -> None:
    transcript = RAW / "q1ec1.txt"
    audio = RAW / "q1ec1.mix.wav"
    if not transcript.is_file() or not audio.is_file() or audio.stat().st_size < 20_000_000:
        raise SystemExit("Map Task sample is missing. Run evaluation/download_maptask_sample.ps1 first.")
    turns = []
    for raw_line in transcript.read_text(encoding="utf-8", errors="replace").splitlines():
        if "\t" not in raw_line:
            continue
        speaker, text = raw_line.split("\t", 1)
        if speaker not in {"g", "f"} or not text.strip():
            continue
        turns.append({
            "id": f"ref_{len(turns) + 1:04d}",
            "speaker_id": "GIVER" if speaker == "g" else "FOLLOWER",
            "text": text.strip(),
        })
    DERIVED.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "dataset_id": "hcrc-maptask-q1ec1",
        "session_id": "q1ec1",
        "audio_path": str(audio.resolve()),
        "license": "CC-BY-4.0",
        "source_url": "https://groups.inf.ed.ac.uk/maptask/",
        "speakers": ["GIVER", "FOLLOWER"],
        "turns": turns,
    }
    destination = DERIVED / "reference.json"
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Imported {len(turns)} real dialogue turns: {destination}")


if __name__ == "__main__":
    main()
