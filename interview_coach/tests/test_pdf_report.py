from __future__ import annotations

from datetime import datetime, timezone

from interview_app.pdf_report import AnalyticsPdfInputs, build_analytics_pdf_bytes


def test_build_analytics_pdf_bytes_returns_pdf_bytes() -> None:
    inputs = AnalyticsPdfInputs(
        user_label="Test User (test@example.com)",
        position_title="Backend Engineer",
        generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        summary={
            "total_questions": 3,
            "answered_questions": 2,
            "skipped_questions": 1,
            "avg_correctness": 75,
            "avg_role_relevance": 60,
            "avg_red_flags": 0.5,
            "fallacy_detected_count": 1,
        },
        timeline=[
            {"question_order": 1, "is_skipped": False, "correctness": 80, "role_relevance": 70, "red_flags_count": 0, "fallacy_detected": False},
            {"question_order": 2, "is_skipped": True, "correctness": None, "role_relevance": None, "red_flags_count": None, "fallacy_detected": False},
            {"question_order": 3, "is_skipped": False, "correctness": 70, "role_relevance": 50, "red_flags_count": 1, "fallacy_detected": True},
        ],
    )

    pdf_bytes = build_analytics_pdf_bytes(inputs)
    assert isinstance(pdf_bytes, (bytes, bytearray))
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 1_000

