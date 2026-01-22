from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from interview_app.models.schemas import FallacyHint, InterviewQuestion, ScoreCard


@dataclass(frozen=True)
class InterviewTurn:
    question: InterviewQuestion
    answer: str
    scorecard: ScoreCard


def new_interview_state() -> dict[str, Any]:
    return {
        "job_description": "",
        "prompt_mode": "default",
        "interview_started": False,
        "current_question": None,
        "last_scorecard": None,
        "last_fallacy_hint": None,
        "transcript": [],
    }


def start_interview(state: dict[str, Any], first_question: InterviewQuestion) -> None:
    state["interview_started"] = True
    state["current_question"] = first_question.model_dump()
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
    if not state.get("current_question"):
        raise ValueError("No current question to answer")

    question = InterviewQuestion.model_validate(state["current_question"])
    turn = InterviewTurn(question=question, answer=answer, scorecard=scorecard)

    transcript: list[dict[str, Any]] = state.setdefault("transcript", [])
    transcript.append(
        {
            "question": turn.question.model_dump(),
            "answer": turn.answer,
            "scorecard": turn.scorecard.model_dump(),
            "fallacy_hint": fallacy_hint.model_dump() if fallacy_hint is not None else None,
        }
    )

    state["last_scorecard"] = scorecard.model_dump()
    state["last_fallacy_hint"] = fallacy_hint.model_dump() if fallacy_hint is not None else None
    state["current_question"] = next_question.model_dump() if next_question is not None else None


def reset_interview(state: dict[str, Any]) -> None:
    keep_job_description = state.get("job_description", "")
    keep_prompt_mode = state.get("prompt_mode", "default")

    defaults = new_interview_state()
    for key, value in defaults.items():
        state[key] = value

    state["job_description"] = keep_job_description
    state["prompt_mode"] = keep_prompt_mode
