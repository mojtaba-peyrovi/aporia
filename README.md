## Interview Practice Coach (Streamlit)

Single-page Streamlit app for practicing interview questions with structured feedback and optional fallacy-coaching hints.

### Local run

```bash
uv sync
uv run streamlit run interview_coach/app.py
```

### Tests

```bash
uv run pytest -q
```

### Secrets (local + Streamlit Community Cloud)

- Set `OPENAI_API_KEY` in Streamlit Community Cloud secrets or as an environment variable.
- The app prefers `st.secrets["OPENAI_API_KEY"]` and falls back to `OPENAI_API_KEY` from the environment.
