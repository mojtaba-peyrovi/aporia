# Interview Practice Coach (implementation notes)

This folder contains the Streamlit app (`interview_coach/app.py`) and all Python modules under `interview_coach/interview_app/`.

## Stepwise plan (mirrors root `PLAN.md`)

1. Setup + CV parsing + profiling agent (this step)
2. Interview loop (question, answer, scoring)
3. Fallacy coach hints + safety guards + deploy polish

## Key decisions

- Logs write to `interview_coach/logs/app.log` using a rotating file handler.
- CV parsing supports `.pdf`, `.docx`, `.txt` with lazy imports to keep tests deterministic.
- Agent output is validated with strict Pydantic models; agent calls are not exercised in tests.

