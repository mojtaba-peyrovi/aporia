from __future__ import annotations

from dataclasses import dataclass
from os import getenv
from typing import Any


@dataclass(frozen=True)
class Settings:
    model: str = "gpt-4.1-mini"
    temperature: float = 0.3


def get_openai_api_key() -> str | None:
    try:
        import streamlit as st  # type: ignore

        key = st.secrets.get("OPENAI_API_KEY")  # type: ignore[attr-defined]
        if key:
            return str(key)
    except Exception:
        pass

    return getenv("OPENAI_API_KEY")


def redact_settings(settings: Settings) -> dict[str, Any]:
    return {"model": settings.model, "temperature": settings.temperature}

