from __future__ import annotations

import json
from typing import Any

from interview_app.config import Settings
from interview_app.models.schemas import ARISTOTLE_FALLACIES, ARISTOTLE_FALLACY_EXPLANATIONS, FallacyHint
from interview_app.services.llm_structured import call_structured_llm
from interview_app.services.prompt_catalog import get_fallacy_judge_system_prompt, validate_prompt_mode


def _safe_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def judge_answer_for_fallacies(
    *,
    question_text: str,
    answer: str,
    settings: Settings,
    prompt_mode: str,
    session_id: str | None = None,
) -> FallacyHint:
    prompt_mode = validate_prompt_mode(prompt_mode)
    user_content = (
        "Analyze the candidate answer for possible logical fallacies or irrelevant reasoning.\n\n"
        f"Question:\n{question_text}\n\n"
        f"Answer:\n{answer}\n\n"
        "Allowed fallacy types (Aristotle 13):\n"
        f"{_safe_json(list(ARISTOTLE_FALLACIES))}\n\n"
        "Short explanations (for reference):\n"
        f"{_safe_json(ARISTOTLE_FALLACY_EXPLANATIONS)}"
    )

    return call_structured_llm(
        system_prompt=get_fallacy_judge_system_prompt(prompt_mode),
        user_content=user_content,
        result_type=FallacyHint,
        settings=settings,
        session_id=session_id,
        event_prefix="fallacy_judge",
    )

