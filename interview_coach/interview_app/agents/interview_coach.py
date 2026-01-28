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
    """Serialize data to JSON for prompt inclusion.

    Uses ``ensure_ascii=False`` so that Unicode characters remain readable in the prompt.

    Args:
        data: Any JSON-serializable value.

    Returns:
        A JSON string representation of ``data``.
    """
    return json.dumps(data, ensure_ascii=False)


def _normalize_profile(profile: CandidateProfile | dict[str, Any] | None) -> dict[str, Any] | None:
    """Normalize a candidate profile into a plain dict (or None).

    Args:
        profile: Candidate profile as a Pydantic model, a dict, or None.

    Returns:
        A JSON-serializable dict representation of the profile, or None.
    """
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
    top_skills: list[str] | None = None,
    focus_skill: str | None = None,
    skill_coverage: dict[str, int] | None = None,
    settings: Settings,
    prompt_mode: str,
    session_id: str | None = None,
) -> InterviewQuestion:
    """Generate the next interview question as a structured :class:`InterviewQuestion`.

    Builds a prompt containing the candidate profile, job description, and the transcript so
    far. Optionally includes top skills/coverage and can enforce a specific ``focus_skill`` by
    instructing the model to include it as a tag. As a final safeguard, if ``focus_skill`` is
    set and the model fails to include it, this function appends it to ``question.tags``.

    Args:
        profile: Candidate profile as a Pydantic model, dict, or None.
        job_description: Job description text (may be empty).
        transcript: Transcript entries so far (may be empty).
        top_skills: Optional list of skills to emphasize; when relevant, the model should use
            these exact strings in ``tags``.
        focus_skill: Optional single skill to prioritize assessing next; if provided, it should
            appear exactly as one of the returned tags.
        skill_coverage: Optional mapping of skill -> count of tagged questions so far.
        settings: App settings containing LLM configuration.
        prompt_mode: Which prompt template variant to use (validated by ``validate_prompt_mode``).
        session_id: Optional session identifier to include in logs/telemetry.

    Returns:
        An :class:`InterviewQuestion` for the next turn.
    """
    prompt_mode = validate_prompt_mode(prompt_mode)
    user_content = (
        "Create the next interview question.\n\n"
        f"Candidate profile JSON:\n{_safe_json(_normalize_profile(profile))}\n\n"
        f"Job description (may be empty):\n{job_description}\n\n"
        f"Transcript so far (may be empty):\n{_safe_json(transcript)}\n\n"
    )
    if top_skills:
        user_content += (
            f"Top skills to cover (use these exact strings in tags when relevant):\n{_safe_json(top_skills)}\n\n"
        )
    if skill_coverage:
        user_content += f"Skill coverage so far (count of questions tagged per skill):\n{_safe_json(skill_coverage)}\n\n"
    if focus_skill:
        user_content += (
            "Constraints:\n"
            f"- Prioritize assessing this skill next: {focus_skill}\n"
            "- Include the focus skill EXACTLY as one of the tags.\n\n"
        )
    question = call_structured_llm(
        system_prompt=get_interview_question_system_prompt(prompt_mode),
        user_content=user_content,
        result_type=InterviewQuestion,
        settings=settings,
        session_id=session_id,
        event_prefix="question_generation",
    )
    if focus_skill and focus_skill.strip():
        focus_normalized = focus_skill.strip().lower()
        if not any(str(t).strip().lower() == focus_normalized for t in question.tags):
            question.tags = list(question.tags) + [focus_skill.strip()]
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
    """Evaluate a candidate answer and return a structured :class:`ScoreCard`.

    Builds a prompt including the candidate profile, job description, current question (as
    structured JSON), the candidate's answer, and the transcript so far. The prompt mode is
    validated before selecting the system prompt template.

    Args:
        profile: Candidate profile as a Pydantic model, dict, or None.
        job_description: Job description text (may be empty).
        question: The current question as a Pydantic model or dict.
        answer: The candidate's answer text.
        transcript: Transcript entries so far (may be empty).
        settings: App settings containing LLM configuration.
        prompt_mode: Which prompt template variant to use (validated by ``validate_prompt_mode``).
        session_id: Optional session identifier to include in logs/telemetry.

    Returns:
        A :class:`ScoreCard` with scores, strengths, improvements, red flags, and optional rewrite.
    """
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
