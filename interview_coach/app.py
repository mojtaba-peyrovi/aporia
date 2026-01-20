from __future__ import annotations

import uuid

import streamlit as st

from interview_app.agents.cv_profiler import profile_candidate_from_cv_text
from interview_app.config import Settings
from interview_app.logging_setup import get_logger, setup_logging
from interview_app.services.cv_parser import extract_text_from_upload


def _init_state() -> None:
    st.session_state.setdefault("session_id", str(uuid.uuid4()))
    st.session_state.setdefault("cv_text", None)
    st.session_state.setdefault("profile", None)
    st.session_state.setdefault("temperature", 0.3)


def main() -> None:
    st.set_page_config(page_title="Interview Practice Coach", layout="wide")
    _init_state()

    setup_logging()
    logger = get_logger(st.session_state["session_id"])

    st.title("Interview Practice Coach")
    st.caption("Step 1: Upload CV → parse → generate Candidate Profile.")

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

    with col_b:
        st.subheader("Candidate Profile")
        if st.session_state.get("profile"):
            st.json(st.session_state["profile"])
        else:
            st.info("Upload and parse a CV, then generate a profile.")

        with st.expander("Raw CV text", expanded=False):
            st.text_area(
                "CV text",
                value=st.session_state.get("cv_text") or "",
                height=240,
                disabled=True,
            )


if __name__ == "__main__":
    main()

