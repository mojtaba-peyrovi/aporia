from __future__ import annotations

from typing import Any


def _normalize_token(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def _extract_question_tags_from_turn(turn: Any) -> list[str]:
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
