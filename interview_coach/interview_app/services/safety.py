from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol


DEFAULT_MAX_CHARS = 12_000


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    user_message: str
    meta: dict[str, Any]


def _normalize(text: str) -> str:
    return (text or "").replace("\x00", "").strip()


def truncate_text(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> tuple[str, bool]:
    text = _normalize(text)
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(ignore|disregard)\b.*\b(previous|prior)\b", re.IGNORECASE),
    re.compile(r"\b(system prompt|developer message|hidden instructions)\b", re.IGNORECASE),
    re.compile(r"\bdo not follow\b|\bforget\b|\boverride\b", re.IGNORECASE),
    re.compile(r"\byou are (now|no longer)\b", re.IGNORECASE),
)


def detect_prompt_injection(text: str) -> dict[str, Any]:
    text = _normalize(text)
    hits: list[str] = []
    for pat in _INJECTION_PATTERNS:
        if pat.search(text):
            hits.append(pat.pattern)
    return {"detected": bool(hits), "signals": hits}


class ModerationClient(Protocol):
    def moderate(self, text: str) -> SafetyDecision: ...


class NoopModerationClient:
    def moderate(self, text: str) -> SafetyDecision:
        return SafetyDecision(allowed=True, user_message="", meta={"provider": "noop"})


class OpenAIModerationClient:
    def __init__(self, *, api_key: str, model: str = "omni-moderation-latest") -> None:
        self._api_key = api_key
        self._model = model

    def moderate(self, text: str) -> SafetyDecision:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=self._api_key)
        try:
            resp = client.moderations.create(model=self._model, input=text)
            result = resp.results[0]
            allowed = not bool(result.flagged)
            meta: dict[str, Any] = {"provider": "openai", "model": self._model, "flagged": bool(result.flagged)}
            if hasattr(result, "categories"):
                meta["categories"] = getattr(result, "categories")
            if allowed:
                return SafetyDecision(allowed=True, user_message="", meta=meta)
            return SafetyDecision(
                allowed=False,
                user_message="This content may violate safety policies. Please rephrase and try again.",
                meta=meta,
            )
        except Exception as e:
            # Moderation is best-effort. If unavailable (e.g., API permissions), do not block the user.
            meta = {
                "provider": "openai",
                "model": self._model,
                "unavailable": True,
                "error_type": type(e).__name__,
                "error": str(e)[:300],
            }
            return SafetyDecision(allowed=True, user_message="", meta=meta)


def check_user_text(
    *,
    text: str,
    label: str,
    max_chars: int = DEFAULT_MAX_CHARS,
    moderation_client: ModerationClient | None = None,
) -> tuple[SafetyDecision, str]:
    normalized = _normalize(text)
    truncated, was_truncated = truncate_text(normalized, max_chars=max_chars)

    if not truncated:
        return (
            SafetyDecision(
                allowed=False,
                user_message=f"Please provide {label}.",
                meta={"label": label, "empty": True},
            ),
            "",
        )

    injection_meta = detect_prompt_injection(truncated)
    meta: dict[str, Any] = {
        "label": label,
        "chars": len(truncated),
        "truncated": was_truncated,
        **injection_meta,
    }

    if moderation_client is not None:
        decision = moderation_client.moderate(truncated)
        meta.update({f"moderation_{k}": v for k, v in decision.meta.items()})
        if not decision.allowed:
            return SafetyDecision(allowed=False, user_message=decision.user_message, meta=meta), ""

    return SafetyDecision(allowed=True, user_message="", meta=meta), truncated
