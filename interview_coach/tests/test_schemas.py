from __future__ import annotations

import pytest
from pydantic import ValidationError

from interview_app.models.schemas import CandidateProfile, InterviewQuestion, ScoreCard


def test_candidate_profile_defaults() -> None:
    profile = CandidateProfile()
    assert profile.seniority == "unknown"
    assert profile.skills == []


def test_candidate_profile_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CandidateProfile.model_validate({"unexpected": "x"})


def test_candidate_profile_seniority_validation() -> None:
    CandidateProfile.model_validate({"seniority": "junior"})
    with pytest.raises(ValidationError):
        CandidateProfile.model_validate({"seniority": "principal"})


def test_interview_question_defaults_and_validation() -> None:
    q = InterviewQuestion(question_text="Tell me about yourself.")
    assert q.category in {"behavioral", "technical", "case", "situational", "mixed"}
    assert q.difficulty in {"easy", "medium", "hard"}
    with pytest.raises(ValidationError):
        InterviewQuestion.model_validate({"question_text": "x", "extra": 1})


def test_scorecard_range_validation() -> None:
    ScoreCard.model_validate(
        {
            "correctness": 3,
            "depth": 3,
            "structure": 3,
            "communication": 3,
            "role_relevance": 3,
            "strengths": [],
            "improvements": [],
            "red_flags": [],
            "followup_question": "",
        }
    )
    with pytest.raises(ValidationError):
        ScoreCard.model_validate(
            {
                "correctness": 6,
                "depth": 3,
                "structure": 3,
                "communication": 3,
                "role_relevance": 3,
                "strengths": [],
                "improvements": [],
                "red_flags": [],
                "followup_question": "",
            }
        )
