import unittest

from evaluation.evaluate import calculate_diarization, calculate_wer


class EvaluationTest(unittest.TestCase):
    def test_wer_is_zero_for_case_and_punctuation_only_changes(self) -> None:
        reference = [{"text": "Hello, how are you?"}]
        prediction = [{"text": "hello how are you"}]
        self.assertEqual(calculate_wer(reference, prediction)["wer"], 0)

    def test_diarization_maps_anonymous_speakers(self) -> None:
        reference = [
            {"speaker_id": "A", "start_ms": 0, "end_ms": 1000, "text": "Hello"},
            {"speaker_id": "B", "start_ms": 1000, "end_ms": 2000, "text": "Hi"},
        ]
        prediction = [
            {"speaker_id": "SPEAKER_01", "start_ms": 0, "end_ms": 1000, "text": "Hello"},
            {"speaker_id": "SPEAKER_00", "start_ms": 1000, "end_ms": 2000, "text": "Hi"},
        ]
        result = calculate_diarization(reference, prediction)
        self.assertIsNotNone(result)
        self.assertEqual(result["der"], 0)
        self.assertEqual(result["speaker_mapping"], {"SPEAKER_00": "B", "SPEAKER_01": "A"})

    def test_diarization_is_skipped_without_predicted_speakers(self) -> None:
        reference = [{"speaker_id": "A", "start_ms": 0, "end_ms": 1000, "text": "Hello"}]
        prediction = [{"speaker_id": "SPEAKER_UNKNOWN", "start_ms": 0, "end_ms": 1000, "text": "Hello"}]
        self.assertIsNone(calculate_diarization(reference, prediction))


if __name__ == "__main__":
    unittest.main()
