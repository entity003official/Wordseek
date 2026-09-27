from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.config import settings
from ..languages import language_context
from ..models import AiGeneration, ConversationSession, Practice, PracticeAttempt, User, UserPreference
from ..services.redaction import redact_turns
from ..services.tts import delete_user_tts_objects
from .deepseek import DeepSeekClient, DeepSeekError
from .schemas import AIReview, PracticeFeedback, PracticeSet


PROMPT_VERSION = "2026-09-27.language-learning.3"

REVIEW_PROMPT = """You analyse conversations in target_language for reflective learning. Return one JSON object only.
Required top-level keys: summary, scene, events, learning_points.
Your primary purpose is LANGUAGE LEARNING, not participation statistics.
Prioritize practical expressions that support learning_goal, without forcing unsupported issues.
learning_points is the main output: select up to 8 useful, non-repetitive points from the actual
transcript, covering vocabulary, synonym and natural_expression where the content supports them.
For each point, original MUST be an exact contiguous quote from one cited turn. explanation gives
the contextual meaning (vocabulary), meaning/register difference (synonym), or the precise benefit
of a more natural expression (natural_expression), in native_language. alternative is a useful
collocation for vocabulary, a context-appropriate near-synonym for synonym, or a natural rewrite
for natural_expression, in target_language. usage_note explains when to use it and any change of
meaning/politeness/formality in native_language. example is a short new target_language sentence
using the alternative. Explain words in context, not dictionary lists. Do not claim synonyms are
interchangeable. Preserve intent, tense and politeness in rewrites. Never call a correct expression
wrong simply because there is an alternative. Avoid ornamental idioms and unnecessary advanced words.
If learner identity is unknown, teach from the conversation neutrally without attributing mistakes
to the learner; learning_points must still be generated when usable target-language text exists.
For a short greeting, give only 1-3 worthwhile points; do not pad to fill categories. For unusable or
unclear text, return [] and explain the specific limitation briefly in summary.limitations.
Keep summary under 2 sentences. The events section is secondary; at most 2 events.
 summary requires title, summary, topics,
evidence_turn_ids, limitations. scene requires scene_type, communication_goal, context_notes,
evidence_turn_ids, confidence. scene_type must be one of casual_chat, classroom, group_discussion,
interview, meeting, service_encounter, other. Each event requires type, observation, context,
suggestion, example, evidence_turn_ids, confidence. Event types are TOPIC_DEVELOPMENT,
FOLLOW_UP_QUESTION, TURN_BALANCE, CLARIFICATION. Write explanations in native_language and examples
in natural target_language. Cite only supplied turn ids. Do not infer personality, proficiency, emotion,
health, age, gender, ethnicity, politics or intent. If user_speaker_id is null, return no events, but ALWAYS summarize the actual conversation
and identify its scene using the supplied turns. Unknown learner identity does not prevent a
conversation summary. Never replace the summary with a refusal or a missing-identity error.
Do not expose field names such as user_speaker_id or null in user-facing text. If needed,
put one brief note in limitations asking the user to select their speaker for personal feedback.
Every event must analyse the learner identified by user_speaker_id and cite at least one turn spoken
by that learner. Do not present the partner's behaviour as the learner's behaviour.
JSON example: {"summary":{"title":"...","summary":"...","topics":[],"evidence_turn_ids":["turn_1"],"limitations":[]},"scene":{"scene_type":"casual_chat","communication_goal":"...","context_notes":[],"evidence_turn_ids":["turn_1"],"confidence":0.8},"events":[],"learning_points":[]}"""

PRACTICE_PROMPT = """Create exactly three evidence-grounded target_language conversation practice questions.
Prioritize the supplied learning_goal when selecting the learner task.
Use supplied learning_points to practice useful vocabulary, near-synonyms and natural expressions in context, when present.
Return JSON only with a questions array. Every question needs question_type, question, partner_prompt,
user_goal, hint, sample_answer, rubric, source_event_ids, evidence_turn_ids. question_type must be one
of continue_topic, follow_up, clarification, turn_balance, free_response. Write instructions and hints
in native_language, prompts and sample answers in target_language. Cite only supplied turn and event ids. Never invent
private facts. The rubric must contain 2 to 6 observable communication criteria."""

FEEDBACK_PROMPT = """Give evidence-based feedback on one learner response. Return JSON only with
strengths, improvements, rubric_results, revised_answer, next_question, limitations. Each
rubric_results item requires criterion, met, note. Write feedback in native_language and revised_answer and
next_question in target_language. Judge only the submitted response against the supplied rubric. Do not label
the learner's identity, personality or overall proficiency."""


def _digest(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _known_evidence(model: AIReview | PracticeSet, turn_ids: set[str], event_ids: set[str] | None = None) -> None:
    event_ids = event_ids or set()
    groups: list[list[str]] = []
    if isinstance(model, AIReview):
        groups.extend([model.summary.evidence_turn_ids, model.scene.evidence_turn_ids])
        groups.extend(item.evidence_turn_ids for item in model.events)
        groups.extend(item.evidence_turn_ids for item in model.learning_points)
    else:
        groups.extend(item.evidence_turn_ids for item in model.questions)
        if any(source_id not in event_ids for item in model.questions for source_id in item.source_event_ids):
            raise ValueError("模型引用了不存在的互动事件")
    if any(turn_id not in turn_ids for group in groups for turn_id in group):
        raise ValueError("模型引用了不存在的转写话轮")


def _user_grounded_review(model: AIReview, turns: list[dict], user_speaker_id: str | None) -> None:
    turn_ids = {turn["id"] for turn in turns}
    _known_evidence(model, turn_ids)
    turn_text = {turn["id"]: turn.get("text", "") for turn in turns}
    for point in model.learning_points:
        if not any(point.original in turn_text.get(turn_id, "") for turn_id in point.evidence_turn_ids):
            raise ValueError("学习要点的原句必须逐字引用对应转写，不得编造")
    if not user_speaker_id:
        if model.events:
            raise ValueError("未确认用户说话人时不能生成个人互动提示")
        return
    user_turn_ids = {
        turn["id"]
        for turn in turns
        if turn.get("speaker_id") == user_speaker_id
    }
    if any(not user_turn_ids.intersection(item.evidence_turn_ids) for item in model.events):
        raise ValueError("个人互动提示必须引用至少一个用户自己的话轮")


ValidatedModel = TypeVar("ValidatedModel", AIReview, PracticeSet, PracticeFeedback)


def _complete_validated(
    *,
    user_id: str,
    system_prompt: str,
    input_payload: dict[str, Any],
    max_tokens: int,
    model_type: type[ValidatedModel],
    evidence_check: Callable[[ValidatedModel], None] | None = None,
) -> tuple[Any, ValidatedModel]:
    """Ask again when JSON is syntactically valid but violates our schema/evidence boundary."""
    schema = json.dumps(model_type.model_json_schema(), ensure_ascii=False, separators=(",", ":"))
    strict_prompt = (
        f"{system_prompt}\nThe response must validate exactly against this JSON Schema: {schema}\n"
        "Use only exact evidence IDs present in the input. Do not add markdown or extra top-level keys."
    )
    validation_error: Exception | None = None
    client = DeepSeekClient()
    for attempt in range(2):
        prompt = strict_prompt
        if attempt:
            prompt += "\nYour previous answer failed schema or evidence validation. Correct every required field and evidence ID."
        result = client.complete_json(
            user_id=user_id,
            system_prompt=prompt,
            input_payload=input_payload,
            max_tokens=max_tokens,
        )
        try:
            model = model_type.model_validate(result.payload)
            if evidence_check:
                evidence_check(model)
            return result, model
        except (ValidationError, ValueError) as error:
            validation_error = error
            if isinstance(error, ValidationError):
                issues = [{"loc": item["loc"], "type": item["type"]} for item in error.errors(include_input=False, include_url=False)]
                strict_prompt += "\nCorrect these validation issues: " + json.dumps(issues)
            else:
                strict_prompt += "\nEvidence validation issue: " + str(error)
    raise ValueError("DeepSeek 结果连续两次未通过结构或证据校验") from validation_error


def _preference(db: Session, user: User) -> UserPreference:
    preference = db.get(UserPreference, user.id)
    if not preference or not preference.ai_enabled:
        raise HTTPException(409, "请先在“我的”页面阅读说明并开启 AI 分析")
    return preference


def _cached(db: Session, user_id: str, task_type: str, input_hash: str) -> AiGeneration | None:
    return db.scalar(
        select(AiGeneration).where(
            AiGeneration.owner_id == user_id,
            AiGeneration.task_type == task_type,
            AiGeneration.input_hash == input_hash,
            AiGeneration.prompt_version == PROMPT_VERSION,
            AiGeneration.status == "complete",
        )
    )


def _save_generation(db: Session, user: User, session_id: str | None, task_type: str, input_hash: str, output: dict, result) -> AiGeneration:
    generation = AiGeneration(
        owner_id=user.id,
        session_id=session_id,
        task_type=task_type,
        provider="deepseek",
        model=settings.deepseek_model,
        prompt_version=PROMPT_VERSION,
        input_hash=input_hash,
        output_json=output,
        usage_json=result.usage,
        latency_ms=result.latency_ms,
        finish_reason=result.finish_reason,
    )
    db.add(generation)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _cached(db, user.id, task_type, input_hash)
        if existing:
            return existing
        raise
    db.refresh(generation)
    return generation


def generate_review(db: Session, user: User, conversation: ConversationSession, *, force: bool = False) -> dict:
    preference = _preference(db, user)
    analysis = dict(conversation.analysis_json or {})
    turns = redact_turns(analysis.get("turns", []), preference.pii_aliases)
    if not turns:
        raise HTTPException(409, "转写完成后才能生成 AI 复盘")
    input_payload = {
        "conversation_id": conversation.id,
        "scenario_hint": conversation.scenario,
        "learning_goal": preference.goal,
        **language_context(preference, conversation.target_language),
        "user_speaker_id": conversation.user_speaker_id,
        "turns": turns,
    }
    input_hash = _digest(input_payload)
    if force:
        since = datetime.now(timezone.utc) - timedelta(days=1)
        count = db.scalar(select(func.count(AiGeneration.id)).where(AiGeneration.owner_id == user.id, AiGeneration.session_id == conversation.id, AiGeneration.task_type == "review", AiGeneration.created_at >= since)) or 0
        if count >= settings.ai_review_regenerations_per_day + 1:
            raise HTTPException(429, "今天对这段会话的重新生成次数已用完")
    existing = None if force else _cached(db, user.id, "review", input_hash)
    if existing:
        output = existing.output_json
    else:
        try:
            result, review = _complete_validated(
                user_id=user.id,
                system_prompt=REVIEW_PROMPT,
                input_payload=input_payload,
                max_tokens=4200,
                model_type=AIReview,
                evidence_check=lambda value: _user_grounded_review(value, turns, conversation.user_speaker_id),
            )
        except (DeepSeekError, ValidationError, ValueError) as error:
            if isinstance(error, DeepSeekError):
                raise HTTPException(503 if error.retryable else 502, detail={"code": error.code, "message": str(error), "retryable": error.retryable}) from error
            raise HTTPException(502, detail={"code": "AI_INVALID_RESPONSE", "message": "AI 结果未通过结构和证据校验", "retryable": True}) from error
        output = review.model_dump()
        generation_hash = input_hash if not force else _digest({"input_hash": input_hash, "regenerated_at": datetime.now(timezone.utc).isoformat()})
        _save_generation(db, user, conversation.id, "review", generation_hash, output, result)

    analysis["ai_review"] = output
    analysis["semantic_provider"] = "deepseek"
    if conversation.user_speaker_id and output.get("events"):
        turn_by_id = {turn["id"]: turn for turn in analysis.get("turns", [])}
        events = []
        for index, item in enumerate(output["events"]):
            evidence = [turn_by_id[item_id] for item_id in item["evidence_turn_ids"] if item_id in turn_by_id]
            if not evidence:
                continue
            events.append({
                "id": f"ai_{index + 1:03d}",
                "type": item["type"],
                "start_ms": min(turn["start_ms"] for turn in evidence),
                "end_ms": max(turn["end_ms"] for turn in evidence),
                "turn_ids": item["evidence_turn_ids"],
                "marker_ids": [],
                "confidence": item["confidence"],
                "insight": {
                    "observation": item["observation"],
                    "context": item["context"],
                    "suggestion": item["suggestion"],
                    "example": item["example"],
                    "evidence_turn_ids": item["evidence_turn_ids"],
                },
            })
        if events:
            analysis["events"] = events
    conversation.analysis_json = analysis
    db.commit()
    return output


def generate_practice_set(db: Session, user: User, conversation: ConversationSession, event_id: str | None = None) -> list[Practice]:
    preference = _preference(db, user)
    analysis = dict(conversation.analysis_json or {})
    turns = redact_turns(analysis.get("turns", []), preference.pii_aliases)
    events = analysis.get("events", [])
    selected_events = [item for item in events if not event_id or item.get("id") == event_id]
    if event_id and not selected_events:
        raise HTTPException(404, "未找到指定的互动事件")
    input_payload = {
        "learning_goal": preference.goal,
        **language_context(preference, conversation.target_language),
        "turns": turns,
        "events": selected_events,
        "learning_points": (analysis.get("ai_review") or {}).get("learning_points", []),
    }
    input_hash = _digest(input_payload)
    existing = _cached(db, user.id, "practice_set", input_hash)
    if existing:
        output = existing.output_json
    else:
        try:
            turn_ids = {turn["id"] for turn in turns}
            event_ids = {item.get("id") for item in selected_events}
            result, practice_set = _complete_validated(
                user_id=user.id,
                system_prompt=PRACTICE_PROMPT,
                input_payload=input_payload,
                max_tokens=2200,
                model_type=PracticeSet,
                evidence_check=lambda value: _known_evidence(value, turn_ids, event_ids),
            )
        except (DeepSeekError, ValidationError, ValueError) as error:
            if isinstance(error, DeepSeekError):
                raise HTTPException(503 if error.retryable else 502, detail={"code": error.code, "message": str(error), "retryable": error.retryable}) from error
            raise HTTPException(502, detail={"code": "AI_INVALID_RESPONSE", "message": "AI 题目未通过结构和证据校验", "retryable": True}) from error
        output = practice_set.model_dump()
        _save_generation(db, user, conversation.id, "practice_set", input_hash, output, result)
    practices = []
    for question in output["questions"]:
        practice = Practice(
            owner_id=user.id,
            session_id=conversation.id,
            event_id=(question.get("source_event_ids") or [event_id])[0],
            title=question["question"],
            prompt=question["partner_prompt"],
            hint=question["hint"],
            rubric_json=question["rubric"],
            source="deepseek",
            target_language=conversation.target_language,
        )
        db.add(practice)
        practices.append(practice)
    db.commit()
    return practices


def generate_practice_feedback(db: Session, user: User, practice: Practice, response: str) -> dict:
    _preference(db, user)
    since = datetime.now(timezone.utc) - timedelta(days=1)
    count = db.scalar(
        select(func.count(AiGeneration.id)).where(
            AiGeneration.owner_id == user.id,
            AiGeneration.task_type == "practice_feedback",
            AiGeneration.created_at >= since,
        )
    ) or 0
    if count >= settings.ai_feedback_per_day:
        raise HTTPException(429, "今天的 AI 练习反馈次数已用完")
    input_payload = {
        **language_context(user.preference, practice.target_language),
        "question": practice.title,
        "partner_prompt": practice.prompt,
        "hint": practice.hint,
        "rubric": practice.rubric_json or ["回应对方内容", "补充具体信息", "给对方继续回应的空间"],
        "learner_response": response,
    }
    input_hash = _digest(input_payload)
    existing = _cached(db, user.id, "practice_feedback", input_hash)
    if existing:
        return existing.output_json
    try:
        result, feedback = _complete_validated(
            user_id=user.id,
            system_prompt=FEEDBACK_PROMPT,
            input_payload=input_payload,
            max_tokens=1200,
            model_type=PracticeFeedback,
        )
    except (DeepSeekError, ValidationError, ValueError) as error:
        if isinstance(error, DeepSeekError):
            raise HTTPException(503 if error.retryable else 502, detail={"code": error.code, "message": str(error), "retryable": error.retryable}) from error
        raise HTTPException(502, detail={"code": "AI_INVALID_RESPONSE", "message": "AI 反馈未通过结构校验", "retryable": True}) from error
    output = feedback.model_dump()
    _save_generation(db, user, practice.session_id, "practice_feedback", input_hash, output, result)
    return output


def delete_user_ai_content(db: Session, user_id: str) -> None:
    delete_user_tts_objects(db, user_id)
    db.execute(delete(AiGeneration).where(AiGeneration.owner_id == user_id))
    for conversation in db.scalars(select(ConversationSession).where(ConversationSession.owner_id == user_id)):
        analysis = dict(conversation.analysis_json or {})
        analysis.pop("ai_review", None)
        if analysis.get("semantic_provider") == "deepseek":
            analysis["semantic_provider"] = "local-rules"
        conversation.analysis_json = analysis
    db.commit()
