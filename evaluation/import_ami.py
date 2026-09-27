from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw" / "ami"
DERIVED = ROOT / "derived" / "ami-es2002a"
MEETING_ID = "ES2002a"


def parse_words(path: Path) -> list[dict]:
    speaker_match = re.search(rf"{MEETING_ID}\.([A-Z])\.words\.xml$", path.name)
    if not speaker_match:
        return []
    speaker_id = speaker_match.group(1)
    words = []
    for element in ET.parse(path).getroot().iter():
        if not element.tag.endswith("w"):
            continue
        start = element.attrib.get("starttime")
        end = element.attrib.get("endtime")
        text = "".join(element.itertext()).strip()
        if start is None or end is None or not text:
            continue
        words.append({
            "speaker_id": speaker_id,
            "start_ms": round(float(start) * 1000),
            "end_ms": round(float(end) * 1000),
            "text": text,
        })
    return words


def group_turns(words: list[dict]) -> list[dict]:
    turns: list[dict] = []
    for word in sorted(words, key=lambda item: (item["start_ms"], item["end_ms"])):
        previous = turns[-1] if turns else None
        if (
            previous is None
            or previous["speaker_id"] != word["speaker_id"]
            or word["start_ms"] - previous["end_ms"] > 800
        ):
            turns.append({
                "id": f"ref_{len(turns) + 1:05d}",
                "speaker_id": word["speaker_id"],
                "start_ms": word["start_ms"],
                "end_ms": word["end_ms"],
                "parts": [word["text"]],
            })
        else:
            previous["end_ms"] = max(previous["end_ms"], word["end_ms"])
            previous["parts"].append(word["text"])
    return [
        {
            "id": turn["id"],
            "speaker_id": turn["speaker_id"],
            "start_ms": turn["start_ms"],
            "end_ms": turn["end_ms"],
            "text": re.sub(r"\s+([,.!?;:])", r"\1", " ".join(turn["parts"])),
        }
        for turn in turns
    ]


def main() -> None:
    annotation_root = RAW / "annotations"
    word_files = list(annotation_root.rglob(f"{MEETING_ID}.*.words.xml"))
    if not word_files:
        raise SystemExit("AMI annotations are missing. Run evaluation/download_ami_sample.ps1 first.")
    words = [word for path in word_files for word in parse_words(path)]
    turns = group_turns(words)
    DERIVED.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "dataset_id": "ami-es2002a",
        "session_id": MEETING_ID,
        "audio_path": str((RAW / f"{MEETING_ID}.Mix-Headset.wav").resolve()),
        "license": "CC-BY-4.0",
        "source_url": "https://groups.inf.ed.ac.uk/ami/corpus/",
        "speakers": sorted({word["speaker_id"] for word in words}),
        "turns": turns,
    }
    destination = DERIVED / "reference.json"
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Imported {len(words)} words into {len(turns)} reference turns: {destination}")


if __name__ == "__main__":
    main()
