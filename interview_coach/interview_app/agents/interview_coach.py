from __future__ import annotations

import json
from typing import Any

from interview_app.config import Settings
from interview_app.models.schemas import CandidateProfile, InterviewQuestion, ScoreCard
from interview_app.services.llm_structured import call_structured_llm
from interview_app.services.prompt_catalog import (
    get_interview_question_system_prompt,
    get_scorecard_system_prompt,
    validate_prompt_mode,
)


def _safe_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def _normalize_profile(profile: CandidateProfile | dict[str, Any] | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    if isinstance(profile, CandidateProfile):
        return profile.model_dump()
    return profile


def generate_interview_question(
    *,
    profile: CandidateProfile | dict[str, Any] | None,
    job_description: str,
    transcript: list[dict[str, Any]],
    settings: Settings,
    prompt_mode: str,
    session_id: str | None = None,
) -> InterviewQuestion:
    prompt_mode = validate_prompt_mode(prompt_mode)
    user_content = (
        "Create the next interview question.\n\n"
        f"Candidate profile JSON:\n{_safe_json(_normalize_profile(profile))}\n\n"
        f"Job description (may be empty):\n{job_description}\n\n"
        f"Transcript so far (may be empty):\n{_safe_json(transcript)}\n\n"
    )
    return call_structured_llm(
        system_prompt=get_interview_question_system_prompt(prompt_mode),
        user_content=user_content,
        result_type=InterviewQuestion,
        settings=settings,
        session_id=session_id,
        event_prefix="question_generation",
    )


def evaluate_interview_answer(
    *,
    profile: CandidateProfile | dict[str, Any] | None,
    job_description: str,
    question: InterviewQuestion | dict[str, Any],
    answer: str,
    transcript: list[dict[str, Any]],
    settings: Settings,
    prompt_mode: str,
    session_id: str | None = None,
) -> ScoreCard:
    prompt_mode = validate_prompt_mode(prompt_mode)
    question_obj = question if isinstance(question, InterviewQuestion) else InterviewQuestion.model_validate(question)
    user_content = (
        "Evaluate the candidate answer.\n\n"
        f"Candidate profile JSON:\n{_safe_json(_normalize_profile(profile))}\n\n"
        f"Job description (may be empty):\n{job_description}\n\n"
        f"Current question JSON:\n{_safe_json(question_obj.model_dump())}\n\n"
        f"Candidate answer:\n{answer}\n\n"
        f"Transcript so far (may be empty):\n{_safe_json(transcript)}\n\n"
    )
    return call_structured_llm(
        system_prompt=get_scorecard_system_prompt(prompt_mode),
        user_content=user_content,
        result_type=ScoreCard,
        settings=settings,
        session_id=session_id,
        event_prefix="answer_evaluation",
    )
