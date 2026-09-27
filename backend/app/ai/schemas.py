from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ReviewSummary(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=1600)
    topics: list[str] = Field(default_factory=list, max_length=8)
    evidence_turn_ids: list[str] = Field(min_length=1, max_length=20)
    limitations: list[str] = Field(default_factory=list, max_length=5)


class SceneAnalysis(BaseModel):
    scene_type: Literal[
        "casual_chat", "classroom", "group_discussion", "interview", "meeting", "service_encounter", "other"
    ]
    communication_goal: str = Field(min_length=1, max_length=500)
    context_notes: list[str] = Field(default_factory=list, max_length=8)
    evidence_turn_ids: list[str] = Field(min_length=1, max_length=20)
    confidence: float = Field(ge=0, le=1)


class InteractionInsight(BaseModel):
    type: Literal["TOPIC_DEVELOPMENT", "FOLLOW_UP_QUESTION", "TURN_BALANCE", "CLARIFICATION"]
    observation: str = Field(min_length=1, max_length=800)
    context: str = Field(min_length=1, max_length=800)
    suggestion: str = Field(min_length=1, max_length=800)
    example: str = Field(min_length=1, max_length=800)
    evidence_turn_ids: list[str] = Field(min_length=1, max_length=10)
    confidence: float = Field(ge=0, le=1)


class LanguageLearningPoint(BaseModel):
    kind: Literal["vocabulary", "synonym", "natural_expression"]
    original: str = Field(min_length=1, max_length=800)
    explanation: str = Field(min_length=1, max_length=600)
    alternative: str = Field(min_length=1, max_length=800)
    usage_note: str = Field(min_length=1, max_length=500)
    example: str = Field(min_length=1, max_length=800)
    evidence_turn_ids: list[str] = Field(min_length=1, max_length=3)


class AIReview(BaseModel):
    learning_points: list[LanguageLearningPoint] = Field(max_length=8)
    summary: ReviewSummary
    scene: SceneAnalysis
    events: list[InteractionInsight] = Field(default_factory=list, max_length=5)


class PracticeQuestion(BaseModel):
    question_type: Literal["continue_topic", "follow_up", "clarification", "turn_balance", "free_response"]
    question: str = Field(min_length=1, max_length=800)
    partner_prompt: str = Field(min_length=1, max_length=800)
    user_goal: str = Field(min_length=1, max_length=500)
    hint: str = Field(min_length=1, max_length=800)
    sample_answer: str = Field(min_length=1, max_length=1200)
    rubric: list[str] = Field(min_length=2, max_length=6)
    source_event_ids: list[str] = Field(default_factory=list, max_length=5)
    evidence_turn_ids: list[str] = Field(min_length=1, max_length=10)


class PracticeSet(BaseModel):
    questions: list[PracticeQuestion] = Field(min_length=3, max_length=3)


class RubricResult(BaseModel):
    criterion: str
    met: bool
    note: str


class PracticeFeedback(BaseModel):
    strengths: list[str] = Field(default_factory=list, max_length=5)
    improvements: list[str] = Field(default_factory=list, max_length=5)
    rubric_results: list[RubricResult] = Field(default_factory=list, max_length=8)
    revised_answer: str = Field(min_length=1, max_length=1600)
    next_question: str = Field(min_length=1, max_length=800)
    limitations: list[str] = Field(default_factory=list, max_length=5)
