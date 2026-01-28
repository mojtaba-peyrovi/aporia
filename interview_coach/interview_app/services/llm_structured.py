from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from interview_app.config import Settings, get_openai_api_key, redact_settings
from interview_app.logging_setup import get_logger


TModel = TypeVar("TModel", bound=BaseModel)


def _extract_json(text: str) -> Any:
    """Parse a JSON object from model output text.

    The primary path expects ``text`` to be valid JSON. As a fallback, it tries to locate
    the first ``"{"`` and last ``"}"`` and parse the substring, which helps recover from
    occasional surrounding prose/whitespace.

    Args:
        text: Raw model output text.

    Returns:
        The decoded JSON value (typically a dict for this app).

    Raises:
        json.JSONDecodeError: If no valid JSON can be extracted.
    """
    try:
        return json.loads(text)
    except JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])


def _openai_chat_json(*, system_prompt: str, user_content: str, settings: Settings) -> Any:
    """Call OpenAI Chat Completions and return the parsed JSON payload.

    Args:
        system_prompt: System instructions for the model.
        user_content: User content (augmented upstream with schema hints).
        settings: LLM settings (model name, temperature).

    Returns:
        The decoded JSON value returned by the model.

    Raises:
        RuntimeError: If the OpenAI API key is not configured.
        json.JSONDecodeError: If the response cannot be parsed as JSON.
    """
    api_key = get_openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    from openai import OpenAI  # type: ignore

    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=settings.model,
        temperature=settings.temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )
    content = resp.choices[0].message.content or ""
    return _extract_json(content)


def call_structured_llm(
    *,
    system_prompt: str,
    user_content: str,
    result_type: type[TModel],
    settings: Settings,
    session_id: str | None,
    event_prefix: str,
) -> TModel:
    """Call an LLM and return a validated Pydantic model instance.

    This is the app's "structured output" helper:
    - Logs a start/success/failure lifecycle with the given ``event_prefix``.
    - Adds the target model's JSON schema as a hint to the prompt.
    - Tries ``pydantic_ai.Agent`` first (if available) for typed structured results.
    - Falls back to OpenAI Chat Completions and parses JSON, retrying once with stricter
      "JSON only" instructions if parsing/validation fails.

    Args:
        system_prompt: System instructions for the model.
        user_content: User prompt content (CV text, job description, etc.).
        result_type: Pydantic model class to validate the response against.
        settings: LLM settings (model name, temperature).
        session_id: Optional session identifier for logging context.
        event_prefix: Prefix used for structured log event names (e.g., ``"profiling"``).

    Returns:
        An instance of ``result_type`` validated from the model output.

    Raises:
        json.JSONDecodeError: If the model output cannot be parsed as JSON after retries.
        pydantic.ValidationError: If parsed JSON does not conform to ``result_type`` after retries.
        RuntimeError: If the underlying LLM call fails or the API key is missing.
    """
    logger = get_logger(session_id)
    logger.info(
        f"{event_prefix}_started",
        extra={"event_name": f"{event_prefix}_started", **redact_settings(settings)},
    )

    schema_hint = result_type.model_json_schema()
    content_with_schema = f"{user_content}\n\nJSON schema (for reference): {json.dumps(schema_hint, ensure_ascii=False)}"

    try:
        from pydantic_ai import Agent  # type: ignore

        agent = Agent(model=settings.model, system_prompt=system_prompt, result_type=result_type)
        result = agent.run_sync(content_with_schema)
        data = result.data if hasattr(result, "data") else result  # type: ignore[assignment]
        model = data if isinstance(data, result_type) else result_type.model_validate(data)
        logger.info(
            f"{event_prefix}_succeeded",
            extra={"event_name": f"{event_prefix}_succeeded", "provider": "pydantic_ai"},
        )
        return model
    except Exception as e:
        logger.info(
            f"{event_prefix}_fallback",
            extra={"event_name": f"{event_prefix}_fallback", "provider": "openai_chat", "error_type": type(e).__name__},
        )

    attempts = 0
    last_err: Exception | None = None
    while attempts < 2:
        attempts += 1
        try:
            data = _openai_chat_json(
                system_prompt=system_prompt
                + ("\nIMPORTANT: Return ONLY strict JSON. No prose, no markdown." if attempts > 1 else ""),
                user_content=content_with_schema + ("\n\nRETRY: Output must be strict JSON." if attempts > 1 else ""),
                settings=settings,
            )
            model = result_type.model_validate(data)
            logger.info(
                f"{event_prefix}_succeeded",
                extra={"event_name": f"{event_prefix}_succeeded", "provider": "openai_chat", "attempt": attempts},
            )
            return model
        except (JSONDecodeError, ValidationError) as e:
            last_err = e
            logger.info(
                f"{event_prefix}_retry",
                extra={"event_name": f"{event_prefix}_retry", "attempt": attempts, "error_type": type(e).__name__},
            )

    logger.exception(f"{event_prefix}_failed", extra={"event_name": f"{event_prefix}_failed"})
    raise last_err or RuntimeError("LLM call failed")
