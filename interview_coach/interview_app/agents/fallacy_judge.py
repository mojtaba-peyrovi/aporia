from __future__ import annotations

import json
from typing import Any

from interview_app.config import Settings
from interview_app.models.schemas import ARISTOTLE_FALLACIES, ARISTOTLE_FALLACY_EXPLANATIONS, FallacyHint
from interview_app.services.llm_structured import call_structured_llm
from interview_app.services.prompt_catalog import get_fallacy_judge_system_prompt, validate_prompt_mode


def _safe_json(data: Any) -> str:
    """Serialize data to JSON for prompt inclusion.

    Uses ``ensure_ascii=False`` so that Unicode characters remain readable in the prompt.

    Args:
        data: Any JSON-serializable value.

    Returns:
        A JSON string representation of ``data``.
    """
    return json.dumps(data, ensure_ascii=False)


def judge_answer_for_fallacies(
    *,
    question_text: str,
    answer: str,
    settings: Settings,
    prompt_mode: str,
    session_id: str | None = None,
) -> FallacyHint:
    """Analyze an answer for likely logical fallacies and return a structured hint.

    Builds a prompt containing the interview question, the candidate's answer, and the
    allowed Aristotle fallacy types (plus short definitions) to constrain classification.
    The prompt mode is validated before selecting the system prompt template.

    Args:
        question_text: The interview question that was asked.
        answer: The candidate's answer text to analyze.
        settings: App settings containing LLM configuration.
        prompt_mode: Which prompt template variant to use (validated by ``validate_prompt_mode``).
        session_id: Optional session identifier to include in logs/telemetry.

    Returns:
        A :class:`~interview_app.models.schemas.FallacyHint` describing detected/possible fallacies
        and supporting details.
    """
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
