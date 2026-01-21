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
