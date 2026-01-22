from __future__ import annotations

from interview_app.models.schemas import ARISTOTLE_FALLACY_EXPLANATIONS, FallacyHint, UNCERTAINTY_DISCLAIMER


def format_fallacy_name(fallacy_type: str) -> str:
    return fallacy_type.replace("_", " ").strip().title()


def get_primary_fallacy_type(hint: FallacyHint) -> str | None:
    if not hint.possible_fallacies:
        return None
    return hint.possible_fallacies[0].type


def _red_flag_rationale(fallacy_type: str) -> str:
    if fallacy_type == "false_cause":
        return "In interviews, jumping from correlation to causation can make decisions sound ungrounded."
    if fallacy_type == "affirming_the_consequent":
        return "In interviews, this can read as an overconfident inference without ruling out alternatives."
    if fallacy_type == "begging_the_question":
        return "In interviews, circular reasoning can make your argument feel untested or assumption-driven."
    if fallacy_type == "ignorance_of_refutation":
        return "In interviews, missing the point can signal weak listening or unclear prioritization."
    return "In interviews, this can reduce trust in your reasoning if key claims aren’t supported."


def build_read_more_text(hint: FallacyHint) -> str:
    """
    Returns a human-readable explanation suitable for a 'Read more' expander.

    Always includes the exact UNCERTAINTY_DISCLAIMER line.
    """

    primary_type = get_primary_fallacy_type(hint)
    sections: list[str] = []

    if primary_type:
        definition = ARISTOTLE_FALLACY_EXPLANATIONS.get(primary_type, "").strip()
        if definition:
            sections.append(f"Definition: {definition}")

        pf = hint.possible_fallacies[0]
        why_parts: list[str] = []
        if pf.short_explanation.strip():
            why_parts.append(pf.short_explanation.strip())
        if pf.excerpt.strip():
            why_parts.append(f'Excerpt: "{pf.excerpt.strip()}"')
        if why_parts:
            sections.append("Why this might fit:\n" + "\n".join(f"- {item}" for item in why_parts))

        sections.append(f"Why it can be a red flag in interviews: {_red_flag_rationale(primary_type)}")

    extra_lines = [line for line in hint.more_info_text.splitlines() if line.strip() and line.strip() != UNCERTAINTY_DISCLAIMER]
    if extra_lines:
        sections.append("\n".join(extra_lines).strip())

    sections.append(UNCERTAINTY_DISCLAIMER)
    return "\n\n".join(section for section in sections if section.strip())

