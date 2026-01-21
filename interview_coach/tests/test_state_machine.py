from __future__ import annotations

import pytest

from interview_app.models.schemas import InterviewQuestion, ScoreCard
from interview_app.session_state import new_interview_state, reset_interview, start_interview, submit_answer


def _question(text: str) -> InterviewQuestion:
    return InterviewQuestion(question_text=text, category="behavioral", difficulty="easy")


def _scorecard() -> ScoreCard:
    return ScoreCard(
        correctness=3,
        depth=3,
        structure=3,
        communication=3,
        role_relevance=3,
        strengths=["clear example"],
        improvements=["add metrics"],
        red_flags=[],
        suggested_rewrite=None,
        followup_question="",
    )


def test_start_and_submit_answer_appends_transcript() -> None:
    state = new_interview_state()
    assert state["current_question"] is None

    start_interview(state, _question("Q1"))
    assert state["current_question"]["question_text"] == "Q1"
    assert state["transcript"] == []

    submit_answer(state, answer="A1", scorecard=_scorecard(), next_question=_question("Q2"))
    assert len(state["transcript"]) == 1
    assert state["transcript"][0]["question"]["question_text"] == "Q1"
    assert state["current_question"]["question_text"] == "Q2"
    assert state["last_scorecard"]["correctness"] == 3


def test_submit_requires_current_question() -> None:
    state = new_interview_state()
    with pytest.raises(ValueError, match="No current question"):
        submit_answer(state, answer="A", scorecard=_scorecard(), next_question=None)


def test_reset_preserves_mode_and_jd() -> None:
    state = new_interview_state()
    state["job_description"] = "JD"
    state["prompt_mode"] = "friendly"
    start_interview(state, _question("Q1"))
    reset_interview(state)
    assert state["job_description"] == "JD"
    assert state["prompt_mode"] == "friendly"
    assert state["current_question"] is None
    assert state["transcript"] == []

