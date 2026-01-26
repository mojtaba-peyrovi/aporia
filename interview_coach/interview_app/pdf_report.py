from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Mapping, Sequence
from xml.sax.saxutils import escape


@dataclass(frozen=True)
class AnalyticsPdfInputs:
    user_label: str
    position_title: str | None
    generated_at: datetime
    summary: Mapping[str, Any]
    timeline: Sequence[Mapping[str, Any]]


def build_analytics_pdf_bytes(inputs: AnalyticsPdfInputs) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "PDF export requires the optional dependency `reportlab`. "
            "Install it (e.g. `uv add reportlab`) to enable analytics PDF export."
        ) from e

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
        title="Interview Analytics Report",
    )

    styles = getSampleStyleSheet()
    story: list[Any] = []

    story.append(Paragraph("Interview Analytics Report", styles["Title"]))
    story.append(Paragraph(f"User: {escape(inputs.user_label)}", styles["Normal"]))

    if inputs.position_title:
        story.append(Paragraph(f"Position: {escape(inputs.position_title)}", styles["Normal"]))

    generated_at = inputs.generated_at.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    story.append(Paragraph(f"Generated: {escape(generated_at)} (UTC)", styles["Normal"]))
    story.append(Spacer(1, 14))

    summary_rows = [
        ("Questions total", inputs.summary.get("total_questions")),
        ("Answered", inputs.summary.get("answered_questions")),
        ("Skipped", inputs.summary.get("skipped_questions")),
        ("Avg correctness", _format_percent(inputs.summary.get("avg_correctness"))),
        ("Avg relevance", _format_percent(inputs.summary.get("avg_role_relevance"))),
        ("Avg red flags", _format_float(inputs.summary.get("avg_red_flags"))),
        ("Fallacy flagged", inputs.summary.get("fallacy_detected_count")),
    ]
    summary_table = Table([["Metric", "Value"], *summary_rows], colWidths=[220, 280])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 16))

    timeline_header = ["#", "Status", "Correct", "Relevant", "Red flags", "Fallacy"]
    timeline_rows = [timeline_header]
    for item in inputs.timeline:
        is_skipped = bool(item.get("is_skipped") or False)
        timeline_rows.append(
            [
                str(item.get("question_order") or "-"),
                "Skipped" if is_skipped else "Answered",
                _format_percent(item.get("correctness")),
                _format_percent(item.get("role_relevance")),
                _format_int(item.get("red_flags_count")),
                "Yes" if bool(item.get("fallacy_detected") or False) else "No",
            ]
        )

    timeline_table = Table(
        timeline_rows,
        colWidths=[30, 64, 70, 70, 70, 70],
        repeatRows=1,
    )
    timeline_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("ALIGN", (2, 1), (-2, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(Paragraph("Timeline", styles["Heading2"]))
    story.append(timeline_table)

    doc.build(story)
    return buffer.getvalue()


def _format_percent(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.0f}%"
    except Exception:
        return "-"


def _format_int(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return str(int(value))
    except Exception:
        return "-"


def _format_float(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.1f}"
    except Exception:
        return "-"

