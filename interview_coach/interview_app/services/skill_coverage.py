from __future__ import annotations

from typing import Any


def _normalize_token(value: str) -> str:
    """Normalize a skill/tag token for consistent matching.

    This lowercases, strips, collapses internal whitespace, and returns a stable key
    used to compare user skills (from a profile/CV) with question tags (from transcript).

    Args:
        value: Raw token value (skill or tag).

    Returns:
        A normalized token suitable for dict/set keys (e.g., ``"  Python  "`` -> ``"python"``).
    """
    return " ".join(str(value).strip().lower().split())


def _extract_question_tags_from_turn(turn: Any) -> list[str]:
    """Extract question tags from a transcript turn in a tolerant way.

    The app's transcript can contain different shapes (e.g., dicts that include a
    ``question`` sub-dict, or objects with a ``tags`` attribute). This function
    returns a list of non-empty tags as strings.

    Args:
        turn: A transcript entry (dict-like or object-like), or None.

    Returns:
        A list of tag strings (possibly empty).
    """
    if turn is None:
        return []

    if isinstance(turn, dict):
        question = turn.get("question", turn)
        if isinstance(question, dict):
            tags = question.get("tags")
            if isinstance(tags, list):
                return [str(t) for t in tags if str(t).strip()]
        return []

    tags = getattr(turn, "tags", None)
    if isinstance(tags, list):
        return [str(t) for t in tags if str(t).strip()]
    return []


def compute_skill_coverage(*, top_skills: list[str], transcript: list[Any]) -> dict[str, int]:
    """Compute how often each top skill appears in the interview transcript.

    Matches are done by normalizing both skill names and question tags and counting
    exact normalized token matches.

    Args:
        top_skills: Skills to track coverage for (typically from a profile/CV).
        transcript: Transcript entries, where question tags may be stored in different shapes.

    Returns:
        A mapping of canonical skill string -> count of matching tagged questions in the transcript.
        Skills that normalize to the same key are deduplicated (first occurrence wins).
    """
    normalized_to_skill: dict[str, str] = {}
    for skill in top_skills:
        skill_str = str(skill).strip()
        if not skill_str:
            continue
        key = _normalize_token(skill_str)
        if key and key not in normalized_to_skill:
            normalized_to_skill[key] = skill_str

    coverage: dict[str, int] = {skill: 0 for skill in normalized_to_skill.values()}
    if not coverage:
        return {}

    for turn in transcript:
        for tag in _extract_question_tags_from_turn(turn):
            key = _normalize_token(tag)
            skill = normalized_to_skill.get(key)
            if skill is not None:
                coverage[skill] += 1

    return coverage


def pick_next_focus_skill(*, top_skills: list[str], coverage: dict[str, int]) -> str | None:
    """Pick the next skill to focus on based on minimal coverage.

    This normalizes/deduplicates ``top_skills`` (preserving first-seen order), then
    selects the skill with the smallest count in ``coverage``. Ties are broken by the
    original order in ``top_skills``.

    Args:
        top_skills: Candidate skills in priority order.
        coverage: Output from :func:`compute_skill_coverage` (or a compatible mapping).

    Returns:
        The selected skill string, or None if there are no usable skills.
    """
    unique_skills: list[str] = []
    seen: set[str] = set()
    for skill in top_skills:
        skill_str = str(skill).strip()
        if not skill_str:
            continue
        key = _normalize_token(skill_str)
        if key and key not in seen:
            seen.add(key)
            unique_skills.append(skill_str)

    if not unique_skills:
        return None

    counts = {skill: int(coverage.get(skill, 0)) for skill in unique_skills}
    min_count = min(counts.values())
    for skill in unique_skills:
        if counts[skill] == min_count:
            return skill
    return unique_skills[0]
