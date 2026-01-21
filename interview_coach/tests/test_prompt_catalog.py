from __future__ import annotations

import pytest

from interview_app.services.prompt_catalog import (
    DEFAULT_PROMPT_MODE,
    get_interview_question_system_prompt,
    get_scorecard_system_prompt,
    list_prompt_modes,
    validate_prompt_mode,
)


def test_prompt_modes_has_five_entries() -> None:
    modes = list_prompt_modes()
    assert len(modes) == 5
    assert DEFAULT_PROMPT_MODE in modes


def test_validate_prompt_mode() -> None:
    assert validate_prompt_mode(DEFAULT_PROMPT_MODE) == DEFAULT_PROMPT_MODE
    with pytest.raises(ValueError):
        validate_prompt_mode("not_a_mode")


def test_prompts_include_json_and_cot_rules() -> None:
    for mode in list_prompt_modes():
        q_prompt = get_interview_question_system_prompt(mode)
        s_prompt = get_scorecard_system_prompt(mode)
        assert "Reason internally" in q_prompt
        assert "strict JSON" in q_prompt
        assert "Reason internally" in s_prompt
        assert "strict JSON" in s_prompt

