from __future__ import annotations

from interview_app.services.skill_coverage import compute_skill_coverage, pick_next_focus_skill


def test_skill_coverage_picks_least_covered_next() -> None:
    top_skills = ["Python", "SQL", "Leadership"]

    transcript: list[object] = []
    coverage = compute_skill_coverage(top_skills=top_skills, transcript=transcript)
    assert coverage == {"Python": 0, "SQL": 0, "Leadership": 0}
    assert pick_next_focus_skill(top_skills=top_skills, coverage=coverage) == "Python"

    transcript = [{"question": {"tags": ["Python"]}}]
    coverage = compute_skill_coverage(top_skills=top_skills, transcript=transcript)
    assert coverage == {"Python": 1, "SQL": 0, "Leadership": 0}
    assert pick_next_focus_skill(top_skills=top_skills, coverage=coverage) == "SQL"

    transcript.append({"question": {"tags": ["sql"]}})
    coverage = compute_skill_coverage(top_skills=top_skills, transcript=transcript)
    assert coverage == {"Python": 1, "SQL": 1, "Leadership": 0}
    assert pick_next_focus_skill(top_skills=top_skills, coverage=coverage) == "Leadership"

    transcript.append({"question": {"tags": ["Leadership", "Python", "unrelated"]}})
    coverage = compute_skill_coverage(top_skills=top_skills, transcript=transcript)
    assert coverage == {"Python": 2, "SQL": 1, "Leadership": 1}
    assert pick_next_focus_skill(top_skills=top_skills, coverage=coverage) == "SQL"


def test_skill_coverage_ignores_duplicates_and_blanks() -> None:
    top_skills = ["Python", " python ", "", "SQL"]
    coverage = compute_skill_coverage(top_skills=top_skills, transcript=[])
    assert coverage == {"Python": 0, "SQL": 0}
    assert pick_next_focus_skill(top_skills=top_skills, coverage=coverage) == "Python"
