from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from interview_app.models.schemas import FallacyHint, InterviewQuestion, ScoreCard


@dataclass(frozen=True)
class InterviewTurn:
    """Represents one completed Q&A turn in an interview.

    Attributes:
        question: The interview question that was asked.
        answer: The user's answer text.
        scorecard: The evaluation of the answer.
    """

    question: InterviewQuestion
    answer: str
    scorecard: ScoreCard


def new_interview_state() -> dict[str, Any]:
    """Create a fresh, default interview session state dict.

    The returned dict is intended to be stored in a session (e.g., Streamlit session_state)
    and mutated in-place by the helper functions in this module.

    Returns:
        A state dict initialized with default keys for interview flow and transcript.
    """
    return {
        "job_description": "",
        "prompt_mode": "default",
        "interview_started": False,
        "current_question": None,
        "current_question_id": None,
        "current_question_order": None,
        "last_scorecard": None,
        "last_fallacy_hint": None,
        "transcript": [],
    }


def start_interview(
    state: dict[str, Any],
    first_question: InterviewQuestion,
    *,
    question_id: int | None = None,
    question_order: int | None = None,
) -> None:
    """Start an interview by seeding the first question into the session state.

    Mutates ``state`` in-place, setting:
    - ``interview_started`` to True
    - ``current_question`` (as a serialized dict via ``model_dump()``)
    - optional ``current_question_id`` / ``current_question_order``
    - clears ``last_scorecard`` and ``last_fallacy_hint``
    - ensures ``transcript`` exists as a list

    Args:
        state: The session state dict to mutate.
        first_question: The first question to ask.
        question_id: Optional identifier associated with the question (e.g., DB id).
        question_order: Optional order number associated with the question.
    """
    state["interview_started"] = True
    state["current_question"] = first_question.model_dump()
    state["current_question_id"] = question_id
    state["current_question_order"] = question_order
    state["last_scorecard"] = None
    state["last_fallacy_hint"] = None
    state.setdefault("transcript", [])


def submit_answer(
    state: dict[str, Any],
    *,
    answer: str,
    scorecard: ScoreCard,
    next_question: InterviewQuestion | None,
    fallacy_hint: FallacyHint | None = None,
) -> None:
    """Record an answer for the current question and advance to the next question.

    This validates and deserializes the current question from ``state["current_question"]``,
    appends a new transcript entry, updates the "last" evaluation fields, and replaces the
    current question with ``next_question`` (or clears it when None).

    Raises:
        ValueError: If there is no current question in the state to answer.

    Args:
        state: The session state dict to mutate.
        answer: The user's answer text.
        scorecard: The evaluation results for this answer.
        next_question: The next question to ask, or None to end the interview.
        fallacy_hint: Optional hint to record alongside the scorecard.
    """
    if not state.get("current_question"):
        raise ValueError("No current question to answer")

    question = InterviewQuestion.model_validate(state["current_question"])
    turn = InterviewTurn(question=question, answer=answer, scorecard=scorecard)

    transcript: list[dict[str, Any]] = state.setdefault("transcript", [])
    transcript.append(
        {
            "question_id": state.get("current_question_id"),
            "question_order": state.get("current_question_order"),
            "question": turn.question.model_dump(),
            "answer": turn.answer,
            "scorecard": turn.scorecard.model_dump(),
            "fallacy_hint": fallacy_hint.model_dump() if fallacy_hint is not None else None,
            "is_skipped": False,
        }
    )

    state["last_scorecard"] = scorecard.model_dump()
    state["last_fallacy_hint"] = fallacy_hint.model_dump() if fallacy_hint is not None else None
    state["current_question"] = next_question.model_dump() if next_question is not None else None
    state["current_question_id"] = None
    state["current_question_order"] = None


def skip_question(
    state: dict[str, Any],
    *,
    next_question: InterviewQuestion | None,
) -> None:
    """Mark the current question as skipped and advance to the next question.

    Appends a transcript entry with ``is_skipped=True`` (and no answer/scorecard),
    clears "last" evaluation fields, and sets ``current_question`` to ``next_question``
    (or clears it when None).

    Raises:
        ValueError: If there is no current question in the state to skip.

    Args:
        state: The session state dict to mutate.
        next_question: The next question to ask, or None to end the interview.
    """
    if not state.get("current_question"):
        raise ValueError("No current question to skip")

    question = InterviewQuestion.model_validate(state["current_question"])
    transcript: list[dict[str, Any]] = state.setdefault("transcript", [])
    transcript.append(
        {
            "question_id": state.get("current_question_id"),
            "question_order": state.get("current_question_order"),
            "question": question.model_dump(),
            "answer": "",
            "scorecard": None,
            "fallacy_hint": None,
            "is_skipped": True,
        }
    )

    state["last_scorecard"] = None
    state["last_fallacy_hint"] = None
    state["current_question"] = next_question.model_dump() if next_question is not None else None
    state["current_question_id"] = None
    state["current_question_order"] = None


def reset_interview(state: dict[str, Any]) -> None:
    """Reset interview progress while preserving user/profile inputs.

    This resets the state keys defined by :func:`new_interview_state` (clearing the
    transcript and any in-progress question), but keeps certain user-provided fields
    such as prompt mode, job description, and optional CV/JD/profile metadata.

    Args:
        state: The session state dict to mutate.
    """
    keep_prompt_mode = state.get("prompt_mode", "default")
    keep_job_description = state.get("job_description", "")
    keep_cv_text = state.get("cv_text")
    keep_cv_file_hash = state.get("cv_file_hash")
    keep_profile = state.get("profile")
    keep_jd_text = state.get("jd_text")
    keep_jd_file_hash = state.get("jd_file_hash")
    keep_position_title = state.get("position_title")
    keep_vacancy_id = state.get("vacancy_id")
    keep_user_vacancy_id = state.get("user_vacancy_id")

    defaults = new_interview_state()
    for key, value in defaults.items():
        state[key] = value

    state["job_description"] = keep_job_description
    state["prompt_mode"] = keep_prompt_mode
    state["cv_text"] = keep_cv_text
    state["cv_file_hash"] = keep_cv_file_hash
    state["profile"] = keep_profile
    state["jd_text"] = keep_jd_text
    state["jd_file_hash"] = keep_jd_file_hash
    state["position_title"] = keep_position_title
    state["vacancy_id"] = keep_vacancy_id
    state["user_vacancy_id"] = keep_user_vacancy_id
