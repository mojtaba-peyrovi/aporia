from __future__ import annotations

from interview_app.config import Settings, get_openai_api_key
from interview_app.models.schemas import CandidateProfile
from interview_app.services.llm_structured import call_structured_llm


SYSTEM_PROMPT = """You are a careful recruiting analyst.
Reason internally; do not reveal chain-of-thought.
Return ONLY strict JSON matching the provided schema. Do not include markdown.
If fields are unknown, use null/empty defaults.
"""


def profile_candidate_from_cv_text(cv_text: str, settings: Settings, session_id: str | None = None) -> CandidateProfile:
    """Generate a structured :class:`~interview_app.models.schemas.CandidateProfile` from CV text.

    This uses the app's structured-LLM helper to extract candidate details (skills, tools,
    experience highlights, education, etc.) into a validated Pydantic model. The OpenAI API
    key is loaded via :func:`~interview_app.config.get_openai_api_key` and must be present.

    Args:
        cv_text: Raw CV text (typically extracted from an uploaded document).
        settings: App settings, including LLM configuration.
        session_id: Optional session identifier to include in logs/telemetry.

    Returns:
        A populated :class:`~interview_app.models.schemas.CandidateProfile`.

    Raises:
        RuntimeError: If the OpenAI API key is not configured.
    """
    api_key = get_openai_api_key()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set (set it in `.env` or Streamlit secrets as `OPENAI_API_KEY`)."
        )

    return call_structured_llm(
        system_prompt=SYSTEM_PROMPT,
        user_content="Build a CandidateProfile JSON from this CV text.\n\nCV text:\n" + cv_text,
        result_type=CandidateProfile,
        settings=settings,
        session_id=session_id,
        event_prefix="profiling",
    )
