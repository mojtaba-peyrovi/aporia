from __future__ import annotations

from interview_app.models.schemas import ARISTOTLE_FALLACY_EXPLANATIONS, FallacyHint, UNCERTAINTY_DISCLAIMER


def format_fallacy_name(fallacy_type: str) -> str:
    """Convert a fallacy type identifier into a display-friendly name.

    Args:
        fallacy_type: A snake_case fallacy identifier (e.g., ``"false_cause"``).

    Returns:
        Title-cased, space-separated name (e.g., ``"False Cause"``).
    """
    return fallacy_type.replace("_", " ").strip().title()


def get_primary_fallacy_type(hint: FallacyHint) -> str | None:
    """Return the primary (top-ranked) fallacy type from a hint, if present.

    Args:
        hint: A fallacy hint containing 0..n possible fallacies.

    Returns:
        The ``type`` of the first entry in ``hint.possible_fallacies``, or None if the list is empty.
    """
    if not hint.possible_fallacies:
        return None
    return hint.possible_fallacies[0].type


def _red_flag_rationale(fallacy_type: str) -> str:
    """Provide interview-specific rationale for why a fallacy may be a red flag.

    Args:
        fallacy_type: A fallacy type identifier (snake_case).

    Returns:
        A short, human-readable sentence tailored for interview feedback.
    """
    if fallacy_type == "equivocation":
        return "In interviews, shifting a key term’s meaning can make your reasoning feel slippery or evasive."
    if fallacy_type == "amphiboly":
        return "In interviews, leaning on ambiguous phrasing can create confusion and weaken confidence in your conclusion."
    if fallacy_type == "composition":
        return "In interviews, assuming what’s true for parts is true for the whole can lead to oversimplified system-level claims."
    if fallacy_type == "division":
        return "In interviews, assuming what’s true of the whole is true of each part can lead to incorrect, hand-wavy details."
    if fallacy_type == "accent":
        return "In interviews, relying on emphasis or selective quoting can look like cherry-picking rather than careful reasoning."
    if fallacy_type == "form_of_expression":
        return "In interviews, conclusions based on wording similarity can sound like pattern-matching instead of substance."
    if fallacy_type == "accident":
        return "In interviews, applying a general rule to an exception can signal weak judgment about context and constraints."
    if fallacy_type == "converse_accident":
        return "In interviews, generalizing from a one-off anecdote can make your claims feel unrepresentative and fragile."
    if fallacy_type == "false_cause":
        return "In interviews, jumping from correlation to causation can make decisions sound ungrounded."
    if fallacy_type == "affirming_the_consequent":
        return "In interviews, this can read as an overconfident inference without ruling out alternatives."
    if fallacy_type == "begging_the_question":
        return "In interviews, circular reasoning can make your argument feel untested or assumption-driven."
    if fallacy_type == "ignorance_of_refutation":
        return "In interviews, missing the point can signal weak listening or unclear prioritization."
    if fallacy_type == "many_questions":
        return "In interviews, bundling multiple assumptions into one question/claim can feel like leading the conversation rather than clarifying."
    return "In interviews, this can reduce trust in your reasoning if key claims aren’t supported."


def build_read_more_text(hint: FallacyHint) -> str:
    """Build a "Read more" explanation block for a fallacy hint.

    The output is designed for UI display (e.g., an expander) and may include:

    - A definition from ``ARISTOTLE_FALLACY_EXPLANATIONS`` for the primary fallacy type.
    - A "Why this might fit" section using the top-ranked possible fallacy's short explanation
      and/or excerpt.
    - An interview-specific "red flag" rationale.
    - Any additional non-empty lines from ``hint.more_info_text`` excluding the uncertainty line.

    The returned text always includes the exact ``UNCERTAINTY_DISCLAIMER`` line at the end.

    Args:
        hint: The fallacy hint to format.

    Returns:
        A multi-paragraph string suitable for display.
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
