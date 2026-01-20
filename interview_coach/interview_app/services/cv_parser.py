from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path


def _clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def truncate_text(text: str, max_chars: int = 20_000) -> str:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def extract_text_from_bytes(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext == "txt":
        try:
            return _clean_text(data.decode("utf-8"))
        except UnicodeDecodeError:
            return _clean_text(data.decode("latin-1", errors="replace"))

    if ext == "pdf":
        try:
            from pypdf import PdfReader  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("Missing dependency for PDF parsing: install `pypdf`.") from e

        reader = PdfReader(BytesIO(data))
        parts: list[str] = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return _clean_text("\n".join(parts))

    if ext == "docx":
        try:
            from docx import Document  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("Missing dependency for DOCX parsing: install `python-docx`.") from e

        doc = Document(BytesIO(data))
        parts = [p.text for p in doc.paragraphs if p.text]
        return _clean_text("\n".join(parts))

    raise ValueError(f"Unsupported CV file type: .{ext}")


def extract_text_from_upload(uploaded_file) -> str:
    if uploaded_file is None:
        raise ValueError("No file uploaded")

    name = getattr(uploaded_file, "name", None) or "cv"
    data = uploaded_file.getvalue()
    return truncate_text(extract_text_from_bytes(name, data))

