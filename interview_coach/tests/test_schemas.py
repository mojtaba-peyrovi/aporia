from __future__ import annotations

import pytest
from pydantic import ValidationError

from interview_app.models.schemas import CandidateProfile


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

