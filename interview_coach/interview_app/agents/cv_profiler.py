from __future__ import annotations

import json
from typing import Any

from interview_app.config import Settings, get_openai_api_key, redact_settings
from interview_app.logging_setup import get_logger
from interview_app.models.schemas import CandidateProfile


SYSTEM_PROMPT = """You are a careful recruiting analyst.
Reason internally; do not reveal chain-of-thought.
Return ONLY strict JSON matching the provided schema. Do not include markdown.
If fields are unknown, use null/empty defaults.
"""


def _profile_with_openai_chat(cv_text: str, settings: Settings) -> CandidateProfile:
    api_key = get_openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    from openai import OpenAI  # type: ignore

    client = OpenAI(api_key=api_key)
    schema_hint = CandidateProfile.model_json_schema()

    resp = client.chat.completions.create(
        model=settings.model,
        temperature=settings.temperature,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Build a CandidateProfile JSON from this CV text.\n\n"
                    f"JSON schema (for reference): {json.dumps(schema_hint)}\n\n"
                    f"CV text:\n{cv_text}"
                ),
            },
        ],
    )

    content = resp.choices[0].message.content or ""
    data = json.loads(content)
    return CandidateProfile.model_validate(data)


def profile_candidate_from_cv_text(cv_text: str, settings: Settings, session_id: str | None = None) -> CandidateProfile:
    logger = get_logger(session_id)
    logger.info("profiling_started", extra={"event_name": "profiling_started", **redact_settings(settings)})

    api_key = get_openai_api_key()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set (set it in `.env` or Streamlit secrets as `OPENAI_API_KEY`)."
        )

    try:
        # Optional: use PydanticAI when available, otherwise fallback.
        from pydantic_ai import Agent  # type: ignore

        agent = Agent(
            model=settings.model,
            system_prompt=SYSTEM_PROMPT,
            result_type=CandidateProfile,
        )
        result = agent.run_sync(cv_text)
        profile = result.data if hasattr(result, "data") else result  # type: ignore[assignment]
        if not isinstance(profile, CandidateProfile):
            profile = CandidateProfile.model_validate(profile)  # type: ignore[arg-type]
        logger.info("profiling_succeeded", extra={"event_name": "profiling_succeeded", "provider": "pydantic_ai"})
        return profile
    except Exception as e:
        logger.info(
            "profiling_fallback",
            extra={"event_name": "profiling_fallback", "provider": "openai_chat", "error_type": type(e).__name__},
        )
        profile = _profile_with_openai_chat(cv_text=cv_text, settings=settings)
        logger.info("profiling_succeeded", extra={"event_name": "profiling_succeeded", "provider": "openai_chat"})
        return profile
