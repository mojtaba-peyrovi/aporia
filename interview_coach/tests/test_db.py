from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from interview_app.db import (
    create_question,
    insert_answer,
    insert_suggestion,
    link_user_vacancy,
    update_user_cv,
    update_user_profile,
    upsert_user_identity,
    upsert_vacancy,
)


def _fetch_one(db_path: Path, sql: str, params: tuple[object, ...]) -> sqlite3.Row:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(sql, params).fetchone()
        assert row is not None
        return row
    finally:
        conn.close()


def test_sqlite_persists_user_cv_profile_and_vacancy(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite3"

    user_id = upsert_user_identity(
        email="user@example.com",
        first_name="Ada",
        last_name="Lovelace",
        sqlite_db_path=db_path,
    )
    assert isinstance(user_id, int)

    update_user_cv(user_id=user_id, cv_file_hash="cvhash", cv_text="cv text", sqlite_db_path=db_path)
    update_user_profile(
        user_id=user_id,
        profile={"summary": "hi", "skills": ["python"]},
        top_skills=["python", "sql"],
        sqlite_db_path=db_path,
    )

    user_row = _fetch_one(db_path, "SELECT * FROM users WHERE user_id=?", (user_id,))
    assert user_row["email"] == "user@example.com"
    assert user_row["cv_file_hash"] == "cvhash"
    assert user_row["cv_text"] == "cv text"

    profile = json.loads(user_row["profile_json"])
    assert profile["summary"] == "hi"
    assert json.loads(user_row["top_skills_json"]) == ["python", "sql"]

    vacancy_id = upsert_vacancy(
        position_title="Backend Engineer",
        jd_file_hash="jdhash",
        jd_text="jd text",
        sqlite_db_path=db_path,
    )
    assert isinstance(vacancy_id, int)

    vacancy_row = _fetch_one(db_path, "SELECT * FROM vacancies WHERE vacancy_id=?", (vacancy_id,))
    assert vacancy_row["position_title"] == "Backend Engineer"
    assert vacancy_row["jd_file_hash"] == "jdhash"
    assert vacancy_row["jd_text"] == "jd text"

    link_id = link_user_vacancy(user_id=user_id, vacancy_id=vacancy_id, sqlite_db_path=db_path)
    link_id_2 = link_user_vacancy(user_id=user_id, vacancy_id=vacancy_id, sqlite_db_path=db_path)
    assert link_id == link_id_2


def test_sqlite_persists_questions_answers_and_suggestions(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite3"
    user_id = upsert_user_identity(
        email="user@example.com",
        first_name="Ada",
        last_name="Lovelace",
        sqlite_db_path=db_path,
    )
    vacancy_id = upsert_vacancy(
        position_title="Backend Engineer",
        jd_file_hash="jdhash",
        jd_text="jd text",
        sqlite_db_path=db_path,
    )
    user_vacancy_id = link_user_vacancy(user_id=user_id, vacancy_id=vacancy_id, sqlite_db_path=db_path)

    question_id = create_question(
        user_vacancy_id=user_vacancy_id,
        question_text="Tell me about a time you handled conflict on a team.",
        category="behavioral",
        difficulty="easy",
        skill_tags=["communication"],
        question_order=1,
        sqlite_db_path=db_path,
    )
    answer_id = insert_answer(question_id=question_id, answer_text="I did X, Y, Z.", is_skipped=False, sqlite_db_path=db_path)
    suggestion_id = insert_suggestion(
        question_id=question_id,
        correctness=80,
        role_relevance=70,
        red_flags_count=0,
        red_flags_text="",
        improvements_text="Add metrics\nExplain trade-offs",
        suggested_rewrite=None,
        followup_question=None,
        fallacy_detected=False,
        fallacy_name=None,
        fallacy_explanation=None,
        coach_hint=None,
        sqlite_db_path=db_path,
    )
    assert isinstance(answer_id, int)
    assert isinstance(suggestion_id, int)

    question_row = _fetch_one(db_path, "SELECT * FROM questions WHERE question_id=?", (question_id,))
    assert question_row["question_text"].startswith("Tell me about a time")
    assert question_row["question_order"] == 1

    answer_row = _fetch_one(db_path, "SELECT * FROM answers WHERE answer_id=?", (answer_id,))
    assert answer_row["question_id"] == question_id
    assert answer_row["is_skipped"] == 0
    assert answer_row["answer_text"] == "I did X, Y, Z."

    suggestion_row = _fetch_one(db_path, "SELECT * FROM suggestions WHERE suggestion_id=?", (suggestion_id,))
    assert suggestion_row["question_id"] == question_id
    assert suggestion_row["correctness"] == 80
