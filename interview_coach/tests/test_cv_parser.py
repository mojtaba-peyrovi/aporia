from __future__ import annotations

import pytest

from interview_app.services.cv_parser import extract_text_from_bytes, truncate_text


def test_extract_text_txt_roundtrip() -> None:
    text = extract_text_from_bytes("cv.txt", b"Hello  world\n\n\nLine2")
    assert text == "Hello world\n\nLine2"


def test_extract_text_unknown_extension() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        extract_text_from_bytes("cv.rtf", b"hi")


def test_truncate_text() -> None:
    assert truncate_text("abc", max_chars=2) == "ab"


def test_truncate_text_requires_positive() -> None:
    with pytest.raises(ValueError):
        truncate_text("abc", max_chars=0)


def test_extract_text_docx_optional() -> None:
    try:
        from docx import Document  # type: ignore
    except Exception:
        pytest.skip("python-docx not installed")

    from io import BytesIO

    doc = Document()
    doc.add_paragraph("Hello DOCX")
    buf = BytesIO()
    doc.save(buf)
    parsed = extract_text_from_bytes("cv.docx", buf.getvalue())
    assert "Hello DOCX" in parsed

