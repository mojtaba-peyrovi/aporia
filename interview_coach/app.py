from __future__ import annotations

import uuid

import streamlit as st

from interview_app.agents.cv_profiler import profile_candidate_from_cv_text
from interview_app.agents.fallacy_judge import judge_answer_for_fallacies
from interview_app.agents.interview_coach import evaluate_interview_answer, generate_interview_question
from interview_app.config import Settings, get_openai_api_key
from interview_app.logging_setup import get_logger, setup_logging
from interview_app.models.schemas import CandidateProfile, FallacyHint, InterviewQuestion, ScoreCard, UNCERTAINTY_DISCLAIMER
from interview_app.services.cv_parser import extract_text_from_upload
from interview_app.services.prompt_catalog import DEFAULT_PROMPT_MODE, list_prompt_modes
from interview_app.services.safety import OpenAIModerationClient, check_user_text
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

    api_key = get_openai_api_key()
    moderation_client = OpenAIModerationClient(api_key=api_key) if api_key else None

    st.session_state["temperature"] = st.slider(
        "Creativity (temperature)", min_value=0.0, max_value=1.2, value=float(st.session_state["temperature"])
    )

    uploaded = st.file_uploader("Upload CV (PDF/DOCX/TXT)", type=["pdf", "docx", "txt"])
    col_a, col_b = st.columns(2)

    with col_a:
        if st.button("Parse CV", disabled=uploaded is None):
            try:
                cv_text = extract_text_from_upload(uploaded)
                decision, safe_cv_text = check_user_text(text=cv_text, label="CV text", moderation_client=None)
                if not decision.allowed:
                    st.error(decision.user_message)
                    logger.info("cv_text_invalid", extra={"event_name": "cv_text_invalid", **decision.meta})
                    raise RuntimeError("CV text failed validation")
                st.session_state["cv_text"] = safe_cv_text
                logger.info("cv_text_checked", extra={"event_name": "cv_text_checked", **decision.meta})
                st.session_state["profile"] = None
                reset_interview(st.session_state)
                st.success("Parsed CV text.")
                logger.info("cv_parsed", extra={"event_name": "cv_parsed", "cv_chars": len(cv_text)})
            except RuntimeError:
                pass
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

                    answer_decision, safe_answer = check_user_text(
                        text=str(st.session_state.get("answer_draft") or ""),
                        label="an answer",
                        moderation_client=moderation_client,
                    )
                    if not answer_decision.allowed:
                        st.error(answer_decision.user_message)
                        logger.info("answer_blocked", extra={"event_name": "answer_blocked", **answer_decision.meta})
                        raise RuntimeError("Answer blocked by safety checks")
                    logger.info("answer_checked", extra={"event_name": "answer_checked", **answer_decision.meta})

                    jd_text = str(st.session_state.get("job_description") or "")
                    if jd_text.strip():
                        jd_decision, safe_jd_text = check_user_text(
                            text=jd_text,
                            label="a job description",
                            moderation_client=moderation_client,
                        )
                        if not jd_decision.allowed:
                            st.error(jd_decision.user_message)
                            logger.info(
                                "job_description_blocked",
                                extra={"event_name": "job_description_blocked", **jd_decision.meta},
                            )
                            raise RuntimeError("Job description blocked by safety checks")
                        logger.info(
                            "job_description_checked",
                            extra={"event_name": "job_description_checked", **jd_decision.meta},
                        )
                    else:
                        safe_jd_text = ""

                    scorecard: ScoreCard = evaluate_interview_answer(
                        profile=st.session_state.get("profile"),
                        job_description=safe_jd_text,
                        question=q,
                        answer=safe_answer,
                        transcript=transcript,
                        settings=settings,
                        prompt_mode=str(st.session_state.get("prompt_mode") or DEFAULT_PROMPT_MODE),
                        session_id=st.session_state["session_id"],
                    )

                    try:
                        fallacy_hint = judge_answer_for_fallacies(
                            question_text=q.question_text,
                            answer=safe_answer,
                            settings=settings,
                            prompt_mode=str(st.session_state.get("prompt_mode") or DEFAULT_PROMPT_MODE),
                            session_id=st.session_state["session_id"],
                        )
                    except Exception:
                        logger.exception("fallacy_judge_failed", extra={"event_name": "fallacy_judge_failed"})
                        fallacy_hint = FallacyHint(
                            hint_level="none",
                            coach_hint_text="",
                            possible_fallacies=[],
                            more_info_text=UNCERTAINTY_DISCLAIMER,
                            suggested_rewrite=None,
                        )

                    turn_dict = {
                        "question": q.model_dump(),
                        "answer": safe_answer,
                        "scorecard": scorecard.model_dump(),
                        "fallacy_hint": fallacy_hint.model_dump(),
                    }
                    next_question = generate_interview_question(
                        profile=st.session_state.get("profile"),
                        job_description=safe_jd_text,
                        transcript=transcript + [turn_dict],
                        settings=settings,
                        prompt_mode=str(st.session_state.get("prompt_mode") or DEFAULT_PROMPT_MODE),
                        session_id=st.session_state["session_id"],
                    )

                    submit_answer(
                        st.session_state,
                        answer=safe_answer,
                        scorecard=scorecard,
                        next_question=next_question,
                        fallacy_hint=fallacy_hint,
                    )
                    st.session_state["answer_draft"] = ""
                    st.success("Answer submitted.")
                    logger.info("answer_submitted", extra={"event_name": "answer_submitted"})
                except RuntimeError:
                    pass
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

        hint_dict = st.session_state.get("last_fallacy_hint")
        if hint_dict:
            hint = FallacyHint.model_validate(hint_dict)
            if hint.hint_level != "none" and hint.coach_hint_text.strip():
                st.warning(hint.coach_hint_text)
            else:
                st.caption("No coach hint detected for the last answer.")

            with st.expander("More info", expanded=False):
                st.write(hint.more_info_text)
                if hint.possible_fallacies:
                    st.markdown("**Possible fallacies**")
                    for pf in hint.possible_fallacies:
                        st.write(f"- {pf.type} (confidence {pf.confidence:.2f}): {pf.short_explanation}")
                        if pf.excerpt:
                            st.caption(f'Excerpt: \"{pf.excerpt}\"')
                if hint.suggested_rewrite:
                    st.markdown("**Suggested rewrite**")
                    st.write(hint.suggested_rewrite)
        else:
            st.caption("Submit an answer to see fallacy coaching hints.")

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
                    if turn.get("fallacy_hint"):
                        t_hint = FallacyHint.model_validate(turn["fallacy_hint"])
                        if t_hint.coach_hint_text.strip():
                            st.caption(f"Coach hint: {t_hint.coach_hint_text}")

        with st.expander("Raw CV text", expanded=False):
            st.text_area(
                "CV text",
                value=st.session_state.get("cv_text") or "",
                height=240,
                disabled=True,
            )


if __name__ == "__main__":
    main()
