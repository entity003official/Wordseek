import unittest
from unittest.mock import Mock, patch

from backend.app.ai.deepseek import DeepSeekClient, DeepSeekResult
from backend.app.ai.schemas import AIReview
from backend.app.ai.service import _complete_validated, _known_evidence, _user_grounded_review
from backend.app.services.redaction import redact_text


class DeepSeekContractTest(unittest.TestCase):
    def test_official_flash_json_request_shape(self) -> None:
        response = Mock(status_code=200)
        response.json.return_value = {
            "choices": [{"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        }
        client = DeepSeekClient()
        client.api_key = "test-secret"
        with patch("backend.app.ai.deepseek.httpx.post", return_value=response) as post:
            result = client.complete_json(user_id="user-1", system_prompt="Return JSON only.", input_payload={"test": True}, max_tokens=80)
        self.assertTrue(result.payload["ok"])
        request = post.call_args.kwargs
        self.assertEqual(request["json"]["model"], "deepseek-flash")
        self.assertEqual(request["json"]["thinking"], {"type": "disabled"})
        self.assertEqual(request["json"]["response_format"], {"type": "json_object"})
        self.assertNotIn("test-secret", str(request["json"]))

    def test_rejects_invented_review_evidence(self) -> None:
        review = AIReview.model_validate({
            "summary": {"title": "x", "summary": "x", "topics": [], "evidence_turn_ids": ["invented"], "limitations": []},
            "scene": {"scene_type": "other", "communication_goal": "x", "context_notes": [], "evidence_turn_ids": ["turn_1"], "confidence": 0.5},
            "events": [],
            "learning_points": [],
        })
        with self.assertRaises(ValueError):
            _known_evidence(review, {"turn_1"})

    def test_rejects_event_grounded_only_in_partner_turn(self) -> None:
        review = AIReview.model_validate({
            "summary": {"title": "x", "summary": "x", "topics": [], "evidence_turn_ids": ["turn_1"], "limitations": []},
            "scene": {"scene_type": "meeting", "communication_goal": "x", "context_notes": [], "evidence_turn_ids": ["turn_1"], "confidence": 0.8},
            "events": [{
                "type": "FOLLOW_UP_QUESTION",
                "observation": "Partner asked a question.",
                "context": "x",
                "suggestion": "x",
                "example": "Could you clarify?",
                "evidence_turn_ids": ["turn_2"],
                "confidence": 0.8,
            }],
            "learning_points": [],
        })
        turns = [
            {"id": "turn_1", "speaker_id": "SPEAKER_00"},
            {"id": "turn_2", "speaker_id": "SPEAKER_01"},
        ]
        with self.assertRaises(ValueError):
            _user_grounded_review(review, turns, "SPEAKER_00")

    def test_schema_failure_gets_one_strict_correction_attempt(self) -> None:
        valid = {
            "summary": {"title": "x", "summary": "x", "topics": [], "evidence_turn_ids": ["turn_1"], "limitations": []},
            "scene": {"scene_type": "other", "communication_goal": "x", "context_notes": [], "evidence_turn_ids": ["turn_1"], "confidence": 0.5},
            "events": [],
            "learning_points": [],
        }
        client = Mock()
        client.complete_json.side_effect = [
            DeepSeekResult(payload={}, usage={}, latency_ms=1, finish_reason="stop"),
            DeepSeekResult(payload=valid, usage={}, latency_ms=1, finish_reason="stop"),
        ]
        with patch("backend.app.ai.service.DeepSeekClient", return_value=client):
            _, review = _complete_validated(
                user_id="user-1",
                system_prompt="Return JSON.",
                input_payload={"turns": [{"id": "turn_1"}]},
                max_tokens=100,
                model_type=AIReview,
                evidence_check=lambda value: _known_evidence(value, {"turn_1"}),
            )
        self.assertEqual(review.summary.evidence_turn_ids, ["turn_1"])
        self.assertEqual(client.complete_json.call_count, 2)

    def test_redacts_common_identifiers_and_aliases(self) -> None:
        source = "Alice wrote alice@example.com and called +86 138 0013 8000. See https://example.com"
        output = redact_text(source, ["Alice"])
        self.assertNotIn("Alice", output)
        self.assertNotIn("alice@example.com", output)
        self.assertNotIn("138 0013 8000", output)
        self.assertNotIn("example.com", output)


if __name__ == "__main__":
    unittest.main()
