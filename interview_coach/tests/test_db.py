from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from interview_app.db import link_user_vacancy, update_user_cv, update_user_profile, upsert_user_identity, upsert_vacancy


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

