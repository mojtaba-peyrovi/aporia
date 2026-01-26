from __future__ import annotations

from pathlib import Path

from interview_app.db import (
    create_question,
    fetch_population_correctness_distribution,
    fetch_user_vacancy_analytics,
    insert_answer,
    insert_suggestion,
    link_user_vacancy,
    upsert_user_identity,
    upsert_vacancy,
)


def test_fetch_user_vacancy_analytics_summarizes_answers_and_skips(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite3"
    user_id = upsert_user_identity(email="user@example.com", first_name="Ada", last_name="Lovelace", sqlite_db_path=db_path)
    vacancy_id = upsert_vacancy(position_title="Backend Engineer", jd_file_hash="jdhash", jd_text="jd text", sqlite_db_path=db_path)
    user_vacancy_id = link_user_vacancy(user_id=user_id, vacancy_id=vacancy_id, sqlite_db_path=db_path)

    q1 = create_question(
        user_vacancy_id=user_vacancy_id,
        question_text="Q1",
        category="behavioral",
        difficulty="easy",
        skill_tags=["communication"],
        question_order=1,
        sqlite_db_path=db_path,
    )
    insert_answer(question_id=q1, answer_text="A1", is_skipped=False, sqlite_db_path=db_path)
    insert_suggestion(
        question_id=q1,
        correctness=80,
        role_relevance=70,
        red_flags_count=1,
        red_flags_text="One red flag",
        improvements_text="Improve structure",
        suggested_rewrite=None,
        followup_question=None,
        fallacy_detected=False,
        fallacy_name=None,
        fallacy_explanation=None,
        coach_hint=None,
        sqlite_db_path=db_path,
    )

    q2 = create_question(
        user_vacancy_id=user_vacancy_id,
        question_text="Q2",
        category="behavioral",
        difficulty="easy",
        skill_tags=["communication"],
        question_order=2,
        sqlite_db_path=db_path,
    )
    insert_answer(question_id=q2, answer_text=None, is_skipped=True, sqlite_db_path=db_path)

    result = fetch_user_vacancy_analytics(user_vacancy_id=user_vacancy_id, sqlite_db_path=db_path)
    summary = result["summary"]
    assert summary["total_questions"] == 2
    assert summary["answered_questions"] == 1
    assert summary["skipped_questions"] == 1
    assert summary["avg_correctness"] == 80
    assert summary["avg_role_relevance"] == 70
    assert summary["avg_red_flags"] == 1


def test_population_distribution_computes_percentile(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite3"

    user_1 = upsert_user_identity(email="user1@example.com", first_name="Ada", last_name="Lovelace", sqlite_db_path=db_path)
    vac_1 = upsert_vacancy(position_title="Backend Engineer", jd_file_hash="jdhash1", jd_text="jd text", sqlite_db_path=db_path)
    uv_1 = link_user_vacancy(user_id=user_1, vacancy_id=vac_1, sqlite_db_path=db_path)
    q1 = create_question(
        user_vacancy_id=uv_1,
        question_text="Q1",
        category="technical",
        difficulty="easy",
        skill_tags=["python"],
        question_order=1,
        sqlite_db_path=db_path,
    )
    insert_answer(question_id=q1, answer_text="A1", is_skipped=False, sqlite_db_path=db_path)
    insert_suggestion(
        question_id=q1,
        correctness=80,
        role_relevance=80,
        red_flags_count=0,
        red_flags_text="",
        improvements_text="",
        suggested_rewrite=None,
        followup_question=None,
        fallacy_detected=False,
        fallacy_name=None,
        fallacy_explanation=None,
        coach_hint=None,
        sqlite_db_path=db_path,
    )

    user_2 = upsert_user_identity(email="user2@example.com", first_name="Grace", last_name="Hopper", sqlite_db_path=db_path)
    vac_2 = upsert_vacancy(position_title="Backend Engineer", jd_file_hash="jdhash2", jd_text="jd text", sqlite_db_path=db_path)
    uv_2 = link_user_vacancy(user_id=user_2, vacancy_id=vac_2, sqlite_db_path=db_path)
    q2 = create_question(
        user_vacancy_id=uv_2,
        question_text="Q2",
        category="technical",
        difficulty="easy",
        skill_tags=["python"],
        question_order=1,
        sqlite_db_path=db_path,
    )
    insert_answer(question_id=q2, answer_text="A2", is_skipped=False, sqlite_db_path=db_path)
    insert_suggestion(
        question_id=q2,
        correctness=40,
        role_relevance=40,
        red_flags_count=0,
        red_flags_text="",
        improvements_text="",
        suggested_rewrite=None,
        followup_question=None,
        fallacy_detected=False,
        fallacy_name=None,
        fallacy_explanation=None,
        coach_hint=None,
        sqlite_db_path=db_path,
    )

    dist_1 = fetch_population_correctness_distribution(user_id=user_1, sqlite_db_path=db_path)
    assert dist_1["user_avg_correctness"] == 80.0
    assert dist_1["population_avg_correctness"] == [40.0, 80.0]
    assert dist_1["percentile"] == 100

    dist_2 = fetch_population_correctness_distribution(user_id=user_2, sqlite_db_path=db_path)
    assert dist_2["user_avg_correctness"] == 40.0
    assert dist_2["population_avg_correctness"] == [40.0, 80.0]
    assert dist_2["percentile"] == 50

