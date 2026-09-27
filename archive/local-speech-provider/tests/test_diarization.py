import unittest

from backend.app.diarization import assign_speakers


class SpeakerAssignmentTest(unittest.TestCase):
    def test_words_are_grouped_into_attributed_turns(self) -> None:
        transcription = {
            "turns": [],
            "words": [
                {"start_ms": 100, "end_ms": 400, "text": " Hello"},
                {"start_ms": 450, "end_ms": 700, "text": " there"},
                {"start_ms": 900, "end_ms": 1100, "text": " Hi"},
                {"start_ms": 1150, "end_ms": 1350, "text": "!"},
            ],
        }
        diarization = {
            "speakers": ["SPEAKER_00", "SPEAKER_01"],
            "segments": [
                {"start_ms": 0, "end_ms": 800, "speaker_id": "SPEAKER_00"},
                {"start_ms": 850, "end_ms": 1500, "speaker_id": "SPEAKER_01"},
            ],
        }

        result = assign_speakers(transcription, diarization)

        self.assertEqual([turn["speaker_id"] for turn in result["turns"]], ["SPEAKER_00", "SPEAKER_01"])
        self.assertEqual([turn["text"] for turn in result["turns"]], ["Hello there", "Hi!"])

    def test_segment_fallback_uses_largest_overlap(self) -> None:
        transcription = {
            "words": [],
            "turns": [{"id": "turn_001", "start_ms": 500, "end_ms": 1800, "text": "Test"}],
        }
        diarization = {
            "speakers": ["SPEAKER_00", "SPEAKER_01"],
            "segments": [
                {"start_ms": 0, "end_ms": 700, "speaker_id": "SPEAKER_00"},
                {"start_ms": 700, "end_ms": 2000, "speaker_id": "SPEAKER_01"},
            ],
        }

        result = assign_speakers(transcription, diarization)

        self.assertEqual(result["turns"][0]["speaker_id"], "SPEAKER_01")


if __name__ == "__main__":
    unittest.main()

