from __future__ import annotations

from dataclasses import dataclass
from os import environ
from os import getenv
from typing import Any


@dataclass(frozen=True)
class Settings:
    model: str = "gpt-4.1-mini"
    temperature: float = 1.0


def load_env() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv()
    except Exception:
        return


def get_openai_api_key() -> str | None:
    load_env()

    try:
        import streamlit as st  # type: ignore

        key = st.secrets.get("OPENAI_API_KEY")  # type: ignore[attr-defined]
        if key:
            key_str = str(key)
            environ.setdefault("OPENAI_API_KEY", key_str)
            return key_str
    except Exception:
        pass

    key_env = getenv("OPENAI_API_KEY")
    if key_env:
        environ.setdefault("OPENAI_API_KEY", key_env)
    return key_env


def redact_settings(settings: Settings) -> dict[str, Any]:
    return {"model": settings.model, "temperature": settings.temperature}
