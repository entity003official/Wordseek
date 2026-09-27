"""Optional paid smoke test. It never prints the API key or conversation content."""
from backend.app.ai.deepseek import DeepSeekClient
from backend.app.ai.schemas import AIReview
from backend.app.ai.service import REVIEW_PROMPT, _known_evidence


def main() -> None:
    turns = [
        {"id": "turn_1", "speaker_id": "SPEAKER_00", "start_ms": 0, "end_ms": 2200, "text": "What do you think about joining the study group?"},
        {"id": "turn_2", "speaker_id": "SPEAKER_01", "start_ms": 2300, "end_ms": 4100, "text": "I like the idea because we can practise together."},
    ]
    result = DeepSeekClient().complete_json(
        user_id="live-smoke-test",
        system_prompt=REVIEW_PROMPT,
        input_payload={"scenario_hint": "日常交流", "learning_goal": "延续话题", "user_speaker_id": "SPEAKER_01", "turns": turns},
        max_tokens=900,
    )
    review = AIReview.model_validate(result.payload)
    _known_evidence(review, {turn["id"] for turn in turns})
    print(f"DeepSeek 实时验收通过：summary/scene/events 均已校验；finish_reason={result.finish_reason}")


if __name__ == "__main__":
    main()
