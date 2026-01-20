# AGENTS.md (append-only)

## Development process rules
- Use `uv` for dependency management.
- Keep tests green (`uv run pytest -q`).
- Log errors with stack traces; prefer structured context fields.
- Prefer small, reviewable commits with clear messages.

## Coding style
- Python 3.11+, PEP8, type hints.
- Modular functions; avoid giant files.
- Pydantic models are strict (`extra="forbid"`).

## Project notes (append-only)

### 2026-01-20
- Initialized Step 1 scaffold: logging-to-disk, CV parsing service, CandidateProfile schema, Streamlit skeleton, and unit tests.

