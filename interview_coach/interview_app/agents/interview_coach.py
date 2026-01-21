from __future__ import annotations

import json
from typing import Any

from interview_app.config import Settings, get_openai_api_key, redact_settings
from interview_app.logging_setup import get_logger
from interview_app.models.schemas import CandidateProfile, InterviewQuestion, ScoreCard
from interview_app.services.prompt_catalog import (
    get_interview_question_system_prompt,
    get_scorecard_system_prompt,
    validate_prompt_mode,
)


def _safe_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def _openai_chat_json(*, system_prompt: str, user_content: str, settings: Settings) -> Any:
    api_key = get_openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    from openai import OpenAI  # type: ignore

    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=settings.model,
        temperature=settings.temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )
    content = resp.choices[0].message.content or ""
    return json.loads(content)


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
    logger = get_logger(session_id)
    logger.info(
        "question_generation_started",
        extra={"event_name": "question_generation_started", **redact_settings(settings), "prompt_mode": prompt_mode},
    )

    schema_hint = InterviewQuestion.model_json_schema()
    user_content = (
        "Create the next interview question.\n\n"
        f"Candidate profile JSON:\n{_safe_json(_normalize_profile(profile))}\n\n"
        f"Job description (may be empty):\n{job_description}\n\n"
        f"Transcript so far (may be empty):\n{_safe_json(transcript)}\n\n"
        f"JSON schema (for reference): {_safe_json(schema_hint)}"
    )

    try:
        from pydantic_ai import Agent  # type: ignore

        agent = Agent(
            model=settings.model,
            system_prompt=get_interview_question_system_prompt(prompt_mode),
            result_type=InterviewQuestion,
        )
        result = agent.run_sync(user_content)
        data = result.data if hasattr(result, "data") else result  # type: ignore[assignment]
        question = data if isinstance(data, InterviewQuestion) else InterviewQuestion.model_validate(data)
        logger.info(
            "question_generation_succeeded",
            extra={"event_name": "question_generation_succeeded", "provider": "pydantic_ai"},
        )
        return question
    except Exception as e:
        logger.info(
            "question_generation_fallback",
            extra={
                "event_name": "question_generation_fallback",
                "provider": "openai_chat",
                "error_type": type(e).__name__,
            },
        )
        data = _openai_chat_json(
            system_prompt=get_interview_question_system_prompt(prompt_mode),
            user_content=user_content,
            settings=settings,
        )
        question = InterviewQuestion.model_validate(data)
        logger.info(
            "question_generation_succeeded",
            extra={"event_name": "question_generation_succeeded", "provider": "openai_chat"},
        )
        return question


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
    logger = get_logger(session_id)
    logger.info(
        "answer_evaluation_started",
        extra={"event_name": "answer_evaluation_started", **redact_settings(settings), "prompt_mode": prompt_mode},
    )

    question_obj = question if isinstance(question, InterviewQuestion) else InterviewQuestion.model_validate(question)
    schema_hint = ScoreCard.model_json_schema()
    user_content = (
        "Evaluate the candidate answer.\n\n"
        f"Candidate profile JSON:\n{_safe_json(_normalize_profile(profile))}\n\n"
        f"Job description (may be empty):\n{job_description}\n\n"
        f"Current question JSON:\n{_safe_json(question_obj.model_dump())}\n\n"
        f"Candidate answer:\n{answer}\n\n"
        f"Transcript so far (may be empty):\n{_safe_json(transcript)}\n\n"
        f"JSON schema (for reference): {_safe_json(schema_hint)}"
    )

    try:
        from pydantic_ai import Agent  # type: ignore

        agent = Agent(
            model=settings.model,
            system_prompt=get_scorecard_system_prompt(prompt_mode),
            result_type=ScoreCard,
        )
        result = agent.run_sync(user_content)
        data = result.data if hasattr(result, "data") else result  # type: ignore[assignment]
        scorecard = data if isinstance(data, ScoreCard) else ScoreCard.model_validate(data)
        logger.info(
            "answer_evaluation_succeeded",
            extra={"event_name": "answer_evaluation_succeeded", "provider": "pydantic_ai"},
        )
        return scorecard
    except Exception as e:
        logger.info(
            "answer_evaluation_fallback",
            extra={
                "event_name": "answer_evaluation_fallback",
                "provider": "openai_chat",
                "error_type": type(e).__name__,
            },
        )
        data = _openai_chat_json(
            system_prompt=get_scorecard_system_prompt(prompt_mode),
            user_content=user_content,
            settings=settings,
        )
        scorecard = ScoreCard.model_validate(data)
        logger.info(
            "answer_evaluation_succeeded",
            extra={"event_name": "answer_evaluation_succeeded", "provider": "openai_chat"},
        )
        return scorecard

