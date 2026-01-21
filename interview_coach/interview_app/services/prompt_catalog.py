from __future__ import annotations

from typing import Final


PROMPT_MODES: Final[tuple[str, ...]] = (
    "default",
    "strict",
    "friendly",
    "challenging",
    "concise",
)

DEFAULT_PROMPT_MODE: Final[str] = "default"


def list_prompt_modes() -> list[str]:
    return list(PROMPT_MODES)


def validate_prompt_mode(mode: str) -> str:
    if mode not in PROMPT_MODES:
        raise ValueError(f"Unknown prompt mode: {mode}")
    return mode


def _base_json_rules() -> str:
    return (
        "Reason internally; do not reveal chain-of-thought.\n"
        "Return ONLY strict JSON matching the provided schema. Do not include markdown.\n"
        "If fields are unknown, use null/empty defaults.\n"
    )


def interview_coach_tone_instructions(mode: str) -> str:
    mode = validate_prompt_mode(mode)
    if mode == "default":
        return "Be practical and realistic; optimize for interview signal."
    if mode == "strict":
        return "Be strict, rubric-driven, and no-nonsense; highlight gaps clearly."
    if mode == "friendly":
        return "Be supportive and encouraging while still honest."
    if mode == "challenging":
        return "Be adversarial in a fair way; probe weak points and assumptions."
    if mode == "concise":
        return "Be brief and high-signal; minimal verbosity."
    raise AssertionError("unreachable")


def get_interview_question_system_prompt(mode: str) -> str:
    return (
        "You are an expert interview coach.\n"
        f"{interview_coach_tone_instructions(mode)}\n"
        "Generate one next interview question tailored to the candidate profile and job description.\n"
        + _base_json_rules()
    )


def get_scorecard_system_prompt(mode: str) -> str:
    return (
        "You are an expert interview coach.\n"
        f"{interview_coach_tone_instructions(mode)}\n"
        "Evaluate the candidate answer and produce a rubric-based scorecard.\n"
        + _base_json_rules()
    )

