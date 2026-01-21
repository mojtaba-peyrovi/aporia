from __future__ import annotations

import uuid

import streamlit as st

from interview_app.agents.cv_profiler import profile_candidate_from_cv_text
from interview_app.agents.interview_coach import evaluate_interview_answer, generate_interview_question
from interview_app.config import Settings, get_openai_api_key
from interview_app.logging_setup import get_logger, setup_logging
from interview_app.models.schemas import CandidateProfile, InterviewQuestion, ScoreCard
from interview_app.services.cv_parser import extract_text_from_upload
from interview_app.services.prompt_catalog import DEFAULT_PROMPT_MODE, list_prompt_modes
from interview_app.session_state import new_interview_state, reset_interview, start_interview, submit_answer


def _init_state() -> None:
    st.session_state.setdefault("session_id", str(uuid.uuid4()))
    st.session_state.setdefault("cv_text", None)
    st.session_state.setdefault("profile", None)
    st.session_state.setdefault("temperature", 0.3)
    st.session_state.setdefault("target_role", "")
    for key, value in new_interview_state().items():
        st.session_state.setdefault(key, value)
    st.session_state.setdefault("answer_draft", "")


def main() -> None:
    st.set_page_config(page_title="Interview Practice Coach", layout="wide")
    _init_state()

    setup_logging()
    logger = get_logger(st.session_state["session_id"])

    st.title("Interview Practice Coach")
    st.caption("Step 1: Upload CV → parse → generate Candidate Profile. Step 2: Run a mock interview loop.")

    _ = get_openai_api_key()

    st.session_state["temperature"] = st.slider(
        "Creativity (temperature)", min_value=0.0, max_value=1.2, value=float(st.session_state["temperature"])
    )

    uploaded = st.file_uploader("Upload CV (PDF/DOCX/TXT)", type=["pdf", "docx", "txt"])
    col_a, col_b = st.columns(2)

    with col_a:
        if st.button("Parse CV", disabled=uploaded is None):
            try:
                cv_text = extract_text_from_upload(uploaded)
                st.session_state["cv_text"] = cv_text
                st.session_state["profile"] = None
                reset_interview(st.session_state)
                st.success("Parsed CV text.")
                logger.info("cv_parsed", extra={"event_name": "cv_parsed", "cv_chars": len(cv_text)})
            except Exception:
                logger.exception("cv_parse_failed", extra={"event_name": "cv_parse_failed"})
                st.error("Failed to parse CV. Try a different file or format.")

        if st.button("Generate Candidate Profile", disabled=not st.session_state.get("cv_text")):
            try:
                settings = Settings(temperature=float(st.session_state["temperature"]))
                profile = profile_candidate_from_cv_text(
                    cv_text=st.session_state["cv_text"],
                    settings=settings,
                    session_id=st.session_state["session_id"],
                )
                st.session_state["profile"] = profile.model_dump()
                st.success("Generated candidate profile.")
                logger.info("profile_generated", extra={"event_name": "profile_generated"})
            except Exception:
                logger.exception("profile_generation_failed", extra={"event_name": "profile_generation_failed"})
                st.error("Failed to generate profile. Check your API key and logs.")

        st.divider()
        st.subheader("Mock interview")

        modes = list_prompt_modes()
        st.session_state["prompt_mode"] = st.selectbox(
            "Prompt mode",
            options=modes,
            index=modes.index(st.session_state.get("prompt_mode") or DEFAULT_PROMPT_MODE),
        )

        st.session_state["target_role"] = st.text_input(
            "Target role (optional if no CV)",
            value=st.session_state.get("target_role") or "",
            placeholder="e.g., Data Analyst, Backend Engineer",
        )

        st.session_state["job_description"] = st.text_area(
            "Job description (optional)",
            value=st.session_state.get("job_description") or "",
            height=180,
        )

        col_start, col_reset = st.columns([1, 1])
        with col_start:
            if st.button("Start interview", disabled=bool(st.session_state.get("current_question"))):
                try:
                    profile_dict = st.session_state.get("profile")
                    if not profile_dict:
                        profile_dict = CandidateProfile(target_role=st.session_state.get("target_role") or None).model_dump()
                        st.session_state["profile"] = profile_dict

                    settings = Settings(temperature=float(st.session_state["temperature"]))
                    question = generate_interview_question(
                        profile=profile_dict,
                        job_description=str(st.session_state.get("job_description") or ""),
                        transcript=list(st.session_state.get("transcript") or []),
                        settings=settings,
                        prompt_mode=str(st.session_state.get("prompt_mode") or DEFAULT_PROMPT_MODE),
                        session_id=st.session_state["session_id"],
                    )
                    start_interview(st.session_state, question)
                    st.session_state["answer_draft"] = ""
                    st.success("Interview started.")
                    logger.info("interview_started", extra={"event_name": "interview_started"})
                except Exception:
                    logger.exception("interview_start_failed", extra={"event_name": "interview_start_failed"})
                    st.error("Failed to start interview. Check your API key and logs.")

        with col_reset:
            if st.button("Reset interview"):
                reset_interview(st.session_state)
                st.session_state["answer_draft"] = ""
                st.info("Interview reset.")
                logger.info("interview_reset", extra={"event_name": "interview_reset"})

        current_question = st.session_state.get("current_question")
        if current_question:
            q = InterviewQuestion.model_validate(current_question)
            st.markdown("**Current question**")
            st.info(q.question_text)
            st.session_state["answer_draft"] = st.text_area(
                "Your answer",
                value=st.session_state.get("answer_draft") or "",
                height=180,
            )
            if st.button("Submit answer", disabled=not (st.session_state.get("answer_draft") or "").strip()):
                try:
                    settings = Settings(temperature=float(st.session_state["temperature"]))
                    transcript = list(st.session_state.get("transcript") or [])

                    scorecard: ScoreCard = evaluate_interview_answer(
                        profile=st.session_state.get("profile"),
                        job_description=str(st.session_state.get("job_description") or ""),
                        question=q,
                        answer=str(st.session_state.get("answer_draft") or ""),
                        transcript=transcript,
                        settings=settings,
                        prompt_mode=str(st.session_state.get("prompt_mode") or DEFAULT_PROMPT_MODE),
                        session_id=st.session_state["session_id"],
                    )

                    turn_dict = {
                        "question": q.model_dump(),
                        "answer": str(st.session_state.get("answer_draft") or ""),
                        "scorecard": scorecard.model_dump(),
                    }
                    next_question = generate_interview_question(
                        profile=st.session_state.get("profile"),
                        job_description=str(st.session_state.get("job_description") or ""),
                        transcript=transcript + [turn_dict],
                        settings=settings,
                        prompt_mode=str(st.session_state.get("prompt_mode") or DEFAULT_PROMPT_MODE),
                        session_id=st.session_state["session_id"],
                    )

                    submit_answer(
                        st.session_state,
                        answer=str(st.session_state.get("answer_draft") or ""),
                        scorecard=scorecard,
                        next_question=next_question,
                    )
                    st.session_state["answer_draft"] = ""
                    st.success("Answer submitted.")
                    logger.info("answer_submitted", extra={"event_name": "answer_submitted"})
                except Exception:
                    logger.exception("answer_submit_failed", extra={"event_name": "answer_submit_failed"})
                    st.error("Failed to submit answer. Check your API key and logs.")

    with col_b:
        st.subheader("Candidate Profile")
        if st.session_state.get("profile"):
            st.json(st.session_state["profile"])
        else:
            st.info("Upload and parse a CV, then generate a profile.")

        st.subheader("Feedback")
        if st.session_state.get("last_scorecard"):
            st.json(st.session_state["last_scorecard"])
        else:
            st.caption("Submit an answer to see a scorecard.")

        with st.expander("Transcript", expanded=False):
            transcript = list(st.session_state.get("transcript") or [])
            if not transcript:
                st.caption("No turns yet.")
            else:
                for idx, turn in enumerate(transcript, start=1):
                    st.markdown(f"**Turn {idx}**")
                    st.write(turn.get("question", {}).get("question_text", ""))
                    st.write("Answer:")
                    st.write(turn.get("answer", ""))
                    st.write("Scorecard:")
                    st.json(turn.get("scorecard", {}))

        with st.expander("Raw CV text", expanded=False):
            st.text_area(
                "CV text",
                value=st.session_state.get("cv_text") or "",
                height=240,
                disabled=True,
            )


if __name__ == "__main__":
    main()

