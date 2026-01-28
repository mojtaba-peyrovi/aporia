from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path


def _clean_text(text: str) -> str:
    """Normalize extracted CV text for downstream processing.

    - Replaces NUL bytes with spaces
    - Collapses repeated spaces/tabs
    - Collapses 3+ newlines into a double newline
    - Strips leading/trailing whitespace

    Args:
        text: Raw extracted text.

    Returns:
        Cleaned, normalized text.
    """
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def truncate_text(text: str, max_chars: int = 20_000) -> str:
    """Truncate text to a maximum number of characters.

    This is used to cap CV text size before sending it to downstream components (e.g., an LLM).

    Args:
        text: Input text to truncate.
        max_chars: Maximum allowed characters. Must be positive.

    Returns:
        The original text if it is within the limit, otherwise the first ``max_chars`` characters.

    Raises:
        ValueError: If ``max_chars`` is not positive.
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def extract_text_from_bytes(filename: str, data: bytes) -> str:
    """Extract and clean text from an uploaded CV file payload.

    Supported file types are determined from ``filename``:

    - ``.txt``: decoded as UTF-8 (fallback to latin-1 with replacement)
    - ``.pdf``: parsed with ``pypdf``
    - ``.docx``: parsed with ``python-docx``

    Args:
        filename: Original filename (used only to determine the extension).
        data: Raw file bytes.

    Returns:
        Cleaned text extracted from the file.

    Raises:
        ValueError: If the file extension is unsupported.
        RuntimeError: If a required parsing dependency is missing for the given file type.
    """
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
    """Extract text from an uploaded file-like object and apply size limits.

    This expects an object similar to Streamlit's ``UploadedFile`` (i.e., providing
    ``.name`` and ``.getvalue()``). The extracted text is cleaned and truncated.

    Args:
        uploaded_file: The uploaded file object.

    Returns:
        Cleaned, truncated text extracted from the uploaded file.

    Raises:
        ValueError: If no file was provided.
    """
    if uploaded_file is None:
        raise ValueError("No file uploaded")

    name = getattr(uploaded_file, "name", None) or "cv"
    data = uploaded_file.getvalue()
    return truncate_text(extract_text_from_bytes(name, data))
