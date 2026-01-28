from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol


DEFAULT_MAX_CHARS = 12_000


@dataclass(frozen=True)
class SafetyDecision:
    """Represents the result of a safety check/moderation decision.

    Attributes:
        allowed: Whether the input is allowed to proceed.
        user_message: A user-facing message to display when blocked or when guidance is needed.
        meta: Diagnostic metadata for logging/debugging (provider info, signals, truncation, etc.).
    """

    allowed: bool
    user_message: str
    meta: dict[str, Any]


def _normalize(text: str) -> str:
    """Normalize user text for safety checks.

    This removes NUL bytes and trims surrounding whitespace. It also tolerates None-like
    inputs by treating them as empty strings.

    Args:
        text: Raw input text.

    Returns:
        Normalized text.
    """
    return (text or "").replace("\x00", "").strip()


def truncate_text(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> tuple[str, bool]:
    """Truncate text to a maximum length, returning whether truncation occurred.

    Args:
        text: Input text to normalize and potentially truncate.
        max_chars: Maximum number of characters to keep.

    Returns:
        A tuple of (possibly truncated text, was_truncated).
    """
    text = _normalize(text)
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(ignore|disregard)\b.*\b(previous|prior)\b", re.IGNORECASE),
    re.compile(r"\b(system prompt|developer message|hidden instructions)\b", re.IGNORECASE),
    re.compile(r"\bdo not follow\b|\bforget\b|\boverride\b", re.IGNORECASE),
    re.compile(r"\byou are (now|no longer)\b", re.IGNORECASE),
    re.compile(r"\b(ignore|disregard)\b.*\b(above|earlier|earlier messages)\b", re.IGNORECASE),
    re.compile(r"\b(ignore|disregard)\b.*\b(instructions|rules|guidelines)\b", re.IGNORECASE),
    re.compile(r"\b(reset|wipe)\b.*\b(instructions|system prompt|developer message)\b", re.IGNORECASE),
    re.compile(r"\b(reveal|show|print|leak|dump)\b.*\b(system prompt|developer message|hidden instructions)\b", re.IGNORECASE),
    re.compile(r"\b(what are|show me)\b.*\b(your|the)\b.*\b(instructions|system prompt|developer message)\b", re.IGNORECASE),
    re.compile(r"\b(repeat|quote)\b.*\b(system prompt|developer message|hidden instructions)\b", re.IGNORECASE),
    re.compile(r"\bverbatim\b.*\b(system prompt|developer message|instructions)\b", re.IGNORECASE),
    re.compile(r"\b(act as|roleplay as|pretend to be)\b", re.IGNORECASE),
    re.compile(r"\b(simulate|emulate)\b.*\b(system|developer|admin)\b", re.IGNORECASE),
    re.compile(r"\bDAN\b|\bdo anything now\b", re.IGNORECASE),
    re.compile(r"\bdeveloper mode\b|\bjailbreak\b|\bprompt injection\b", re.IGNORECASE),
    re.compile(r"\b(bypass|circumvent|evade)\b.*\b(safety|filters|guardrails|policy)\b", re.IGNORECASE),
    re.compile(r"\b(unfiltered|uncensored|no restrictions)\b", re.IGNORECASE),
    re.compile(r"\b(ignore|disable)\b.*\b(moderation|content policy|safety checks)\b", re.IGNORECASE),
    re.compile(r"\b(override)\b.*\b(system|developer)\b", re.IGNORECASE),
    re.compile(r"\b(you must|you will)\b.*\b(comply|follow)\b", re.IGNORECASE),
    re.compile(r"\b(do not|don't)\b.*\b(refuse|decline)\b", re.IGNORECASE),
    re.compile(r"\bBEGIN\b.*\b(SYSTEM|DEVELOPER)\b|\bEND\b.*\b(SYSTEM|DEVELOPER)\b", re.IGNORECASE | re.DOTALL),
    re.compile(r"\b(#\#\#|<)\s*(system|developer)\s*(prompt|message|instructions)\b", re.IGNORECASE),
    re.compile(r"\b(confidential|internal)\b.*\b(instructions|prompt)\b", re.IGNORECASE),
)


def detect_prompt_injection(text: str) -> dict[str, Any]:
    """Detect simple prompt-injection signals using regex heuristics.

    This is a lightweight, best-effort detector that looks for common phrases used
    to manipulate system instructions (e.g., "ignore previous", "system prompt").

    Args:
        text: Input text to scan.

    Returns:
        A dict containing:
        - ``detected``: True if any patterns matched.
        - ``signals``: A list of the regex patterns that matched.
    """
    text = _normalize(text)
    hits: list[str] = []
    for pat in _INJECTION_PATTERNS:
        if pat.search(text):
            hits.append(pat.pattern)
    return {"detected": bool(hits), "signals": hits}


class ModerationClient(Protocol):
    """Protocol for moderation providers used by :func:`check_user_text`."""

    def moderate(self, text: str) -> SafetyDecision: ...


class NoopModerationClient:
    """A moderation client that never blocks (useful for local/dev or disabled moderation)."""

    def moderate(self, text: str) -> SafetyDecision:
        """Allow all content without performing any checks."""
        return SafetyDecision(allowed=True, user_message="", meta={"provider": "noop"})


class OpenAIModerationClient:
    """Moderation client backed by the OpenAI Moderations API."""

    def __init__(self, *, api_key: str, model: str = "omni-moderation-latest") -> None:
        """Create a moderation client.

        Args:
            api_key: OpenAI API key.
            model: Moderation model name to use.
        """
        self._api_key = api_key
        self._model = model

    def moderate(self, text: str) -> SafetyDecision:
        """Moderate text via OpenAI and return an allow/block decision.

        This is best-effort: on API errors (e.g., missing permissions/network issues),
        the function returns ``allowed=True`` and records error details in ``meta``.

        Args:
            text: Input text to moderate.

        Returns:
            A :class:`SafetyDecision` indicating whether the text is allowed.
        """
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
    """Validate, truncate, and (optionally) moderate a user-provided text field.

    This performs three steps:
    1) Normalize and truncate the text to ``max_chars``.
    2) If the result is empty, block with a helpful "Please provide ..." message.
    3) Run prompt-injection heuristics and, if provided, a moderation client.

    The returned metadata includes truncation info, injection signals, and moderation
    provider details (namespaced as ``moderation_*``).

    Args:
        text: Raw user input.
        label: Human-readable label used in error messages (e.g., "a job description").
        max_chars: Maximum number of characters to keep.
        moderation_client: Optional moderation provider. If None, moderation is skipped.

    Returns:
        A tuple of (decision, safe_text). When not allowed, ``safe_text`` is ``""``.
    """
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
