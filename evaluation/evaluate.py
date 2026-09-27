from __future__ import annotations

import argparse
import itertools
import json
import re
from pathlib import Path
from typing import Any


def normalize_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for row, expected in enumerate(reference, start=1):
        current = [row]
        for column, actual in enumerate(hypothesis, start=1):
            current.append(min(
                current[-1] + 1,
                previous[column] + 1,
                previous[column - 1] + (expected != actual),
            ))
        previous = current
    return previous[-1]


def turns_from(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("analysis"), dict):
        payload = payload["analysis"]
    turns = payload.get("turns", [])
    result = []
    for item in turns:
        start = item.get("start_ms", item.get("startMs"))
        end = item.get("end_ms", item.get("endMs"))
        speaker = item.get("speaker_id", item.get("speakerId", item.get("speaker")))
        result.append({
            "id": item.get("id"),
            "speaker_id": str(speaker) if speaker is not None else "UNKNOWN",
            "start_ms": int(start) if start is not None else None,
            "end_ms": int(end) if end is not None else None,
            "text": str(item.get("text", "")),
        })
    return result


def calculate_wer(reference: list[dict[str, Any]], prediction: list[dict[str, Any]]) -> dict[str, Any]:
    expected = normalize_words(" ".join(turn["text"] for turn in reference))
    actual = normalize_words(" ".join(turn["text"] for turn in prediction))
    edits = edit_distance(expected, actual)
    return {
        "wer": round(edits / max(1, len(expected)), 4),
        "word_edits": edits,
        "reference_words": len(expected),
        "predicted_words": len(actual),
    }


def active_speaker(turns: list[dict[str, Any]], timestamp_ms: int) -> str | None:
    for turn in turns:
        if turn["start_ms"] is not None and turn["end_ms"] is not None and turn["start_ms"] <= timestamp_ms < turn["end_ms"]:
            return turn["speaker_id"]
    return None


def best_speaker_mapping(reference: list[dict[str, Any]], prediction: list[dict[str, Any]], frame_ms: int) -> dict[str, str]:
    reference_speakers = sorted({turn["speaker_id"] for turn in reference})
    predicted_speakers = sorted({turn["speaker_id"] for turn in prediction})
    if not reference_speakers or not predicted_speakers or len(predicted_speakers) > 8:
        return {}
    end_ms = max([turn["end_ms"] or 0 for turn in reference + prediction], default=0)
    scores = {(predicted, expected): 0 for predicted in predicted_speakers for expected in reference_speakers}
    for timestamp in range(0, end_ms, frame_ms):
        expected = active_speaker(reference, timestamp)
        predicted = active_speaker(prediction, timestamp)
        if expected is not None and predicted is not None:
            scores[(predicted, expected)] += 1
    best_score = -1
    best: dict[str, str] = {}
    candidates = []
    if len(predicted_speakers) <= len(reference_speakers):
        candidates = [
            dict(zip(predicted_speakers, assigned))
            for assigned in itertools.permutations(reference_speakers, len(predicted_speakers))
        ]
    else:
        for selected in itertools.combinations(predicted_speakers, len(reference_speakers)):
            for assigned in itertools.permutations(reference_speakers):
                candidates.append(dict(zip(selected, assigned)))
    for mapping in candidates:
        score = sum(scores[(predicted, expected)] for predicted, expected in mapping.items())
        if score > best_score:
            best_score = score
            best = mapping
    return best


def calculate_diarization(reference: list[dict[str, Any]], prediction: list[dict[str, Any]], frame_ms: int = 100) -> dict[str, Any] | None:
    if not reference or not prediction or any(turn["start_ms"] is None or turn["end_ms"] is None for turn in reference + prediction):
        return None
    predicted_speakers = {turn["speaker_id"].upper() for turn in prediction}
    if predicted_speakers <= {"UNKNOWN", "SPEAKER_UNKNOWN"}:
        return None
    mapping = best_speaker_mapping(reference, prediction, frame_ms)
    end_ms = max([turn["end_ms"] or 0 for turn in reference + prediction], default=0)
    reference_frames = missed = false_alarm = confused = correct = 0
    for timestamp in range(0, end_ms, frame_ms):
        expected = active_speaker(reference, timestamp)
        predicted = active_speaker(prediction, timestamp)
        if expected is not None:
            reference_frames += 1
        if expected is not None and predicted is None:
            missed += 1
        elif expected is None and predicted is not None:
            false_alarm += 1
        elif expected is not None and predicted is not None:
            if mapping.get(predicted, predicted) == expected:
                correct += 1
            else:
                confused += 1
    errors = missed + false_alarm + confused
    return {
        "der": round(errors / max(1, reference_frames), 4),
        "speaker_frame_accuracy": round(correct / max(1, reference_frames), 4),
        "missed_speech_ms": missed * frame_ms,
        "false_alarm_ms": false_alarm * frame_ms,
        "speaker_confusion_ms": confused * frame_ms,
        "frame_ms": frame_ms,
        "speaker_mapping": mapping,
        "note": "MVP frame scorer; overlapping speech is represented by one active speaker per frame.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Beyond Words ASR and speaker diarization output.")
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--prediction", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    reference_payload = json.loads(args.reference.read_text(encoding="utf-8"))
    prediction_payload = json.loads(args.prediction.read_text(encoding="utf-8"))
    reference = turns_from(reference_payload)
    prediction = turns_from(prediction_payload)
    result = {
        "reference": str(args.reference.resolve()),
        "prediction": str(args.prediction.resolve()),
        "transcription": calculate_wer(reference, prediction),
        "diarization": calculate_diarization(reference, prediction),
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
