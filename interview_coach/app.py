from __future__ import annotations

import uuid

import streamlit as st

from interview_app.auth import can_show_logout, require_user_identity
from interview_app.agents.cv_profiler import profile_candidate_from_cv_text
from interview_app.agents.fallacy_judge import judge_answer_for_fallacies
from interview_app.agents.interview_coach import evaluate_interview_answer, generate_interview_question
from interview_app.config import Settings, get_openai_api_key
from interview_app.db import (
    create_question,
    insert_answer,
    insert_suggestion,
    link_user_vacancy,
    update_user_cv,
    update_user_profile,
    upsert_vacancy,
)
from interview_app.logging_setup import get_logger, setup_logging
from interview_app.models.schemas import CandidateProfile, FallacyHint, InterviewQuestion, ScoreCard, UNCERTAINTY_DISCLAIMER
from interview_app.services.cv_parser import extract_text_from_upload
from interview_app.services.prompt_catalog import DEFAULT_PROMPT_MODE, list_prompt_modes
from interview_app.services.safety import OpenAIModerationClient, check_user_text
from interview_app.services.uploads import upload_hash
from interview_app.session_state import new_interview_state, reset_interview, skip_question, start_interview, submit_answer
from interview_app.ui import components, layout


def _init_state() -> None:
    st.session_state.setdefault("session_id", str(uuid.uuid4()))
    st.session_state.setdefault("cv_text", None)
    st.session_state.setdefault("cv_file_hash", None)
    st.session_state.setdefault("profile", None)
    st.session_state.setdefault("temperature", 0.3)
    st.session_state.setdefault("jd_text", None)
    st.session_state.setdefault("jd_file_hash", None)
    st.session_state.setdefault("position_title", "")
    st.session_state.setdefault("vacancy_id", None)
    st.session_state.setdefault("user_vacancy_id", None)
    for key, value in new_interview_state().items():
        st.session_state.setdefault(key, value)
    st.session_state.setdefault("answer_draft", "")


def main() -> None:
    st.set_page_config(page_title="Interview Practice Coach", page_icon="🧩", layout="wide")
    _init_state()

    setup_logging()
    logger = get_logger(st.session_state["session_id"])

    layout.inject_global_css()
    identity = require_user_identity(logger=logger)
    layout.render_topbar(user_label=f"{identity.display_name} ({identity.email})", show_logout=can_show_logout())
    st.caption("Upload a job description (required), optionally upload your CV, then run a mock interview loop.")

    api_key = get_openai_api_key()
    moderation_client = OpenAIModerationClient(api_key=api_key) if api_key else None

    st.session_state["temperature"] = st.slider(
        "Creativity (temperature)", min_value=0.0, max_value=1.2, value=float(st.session_state["temperature"])
    )

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Documents")

        st.session_state["position_title"] = st.text_input(
            "Position title (required)",
            value=st.session_state.get("position_title") or "",
            placeholder="e.g., Backend Engineer",
        )

        jd_upload = st.file_uploader(
            "Upload Job Description (PDF/DOCX/TXT) (required)",
            type=["pdf", "docx", "txt"],
            key="jd_uploader",
        )
        cv_upload = st.file_uploader("Upload CV (PDF/DOCX/TXT) (optional)", type=["pdf", "docx", "txt"], key="cv_uploader")

        user_id = int(st.session_state.get("user_id") or 0)

        if cv_upload is not None:
            try:
                new_hash = upload_hash(cv_upload)
                if new_hash != st.session_state.get("cv_file_hash"):
                    cv_text = extract_text_from_upload(cv_upload)
                    decision, safe_cv_text = check_user_text(text=cv_text, label="CV text", moderation_client=None)
                    if not decision.allowed:
                        st.error(decision.user_message)
                        logger.info("cv_text_invalid", extra={"event_name": "cv_text_invalid", **decision.meta})
                        raise RuntimeError("CV text failed validation")

                    st.session_state["cv_text"] = safe_cv_text
                    st.session_state["cv_file_hash"] = new_hash
                    st.session_state["profile"] = None
                    reset_interview(st.session_state)

                    st.success("CV parsed.")
                    logger.info("cv_parsed", extra={"event_name": "CV_PARSED", "cv_chars": len(safe_cv_text)})

                    if user_id:
                        update_user_cv(user_id=user_id, cv_file_hash=new_hash, cv_text=safe_cv_text)
                        logger.info("cv_persisted", extra={"event_name": "CV_PERSISTED", "user_id": user_id})
            except RuntimeError:
                pass
            except Exception:
                logger.exception("cv_parse_failed", extra={"event_name": "cv_parse_failed"})
                st.error("Failed to parse CV. Try a different file or format.")

        if jd_upload is not None:
            if not (st.session_state.get("position_title") or "").strip():
                st.error("Enter a position title before uploading the job description.")
            else:
                try:
                    new_hash = upload_hash(jd_upload)
                    if new_hash != st.session_state.get("jd_file_hash"):
                        jd_text = extract_text_from_upload(jd_upload)
                        jd_decision, safe_jd_text = check_user_text(
                            text=jd_text,
                            label="a job description",
                            moderation_client=moderation_client,
                        )
                        if not jd_decision.allowed:
                            st.error(jd_decision.user_message)
                            logger.info(
                                "job_description_blocked",
                                extra={"event_name": "JOB_DESCRIPTION_BLOCKED", **jd_decision.meta},
                            )
                            raise RuntimeError("Job description blocked by safety checks")

                        st.session_state["jd_text"] = safe_jd_text
                        st.session_state["jd_file_hash"] = new_hash
                        reset_interview(st.session_state)

                        st.success("Job description parsed.")
                        logger.info("jd_parsed", extra={"event_name": "JD_PARSED", "jd_chars": len(safe_jd_text)})

                        if user_id:
                            vacancy_id = upsert_vacancy(
                                position_title=str(st.session_state.get("position_title") or "").strip(),
                                jd_file_hash=new_hash,
                                jd_text=safe_jd_text,
                            )
                            user_vacancy_id = link_user_vacancy(user_id=user_id, vacancy_id=vacancy_id)
                            st.session_state["vacancy_id"] = vacancy_id
                            st.session_state["user_vacancy_id"] = user_vacancy_id
                            logger.info(
                                "vacancy_persisted",
                                extra={
                                    "event_name": "VACANCY_PERSISTED",
                                    "user_id": user_id,
                                    "vacancy_id": vacancy_id,
                                    "user_vacancy_id": user_vacancy_id,
                                },
                            )
                except RuntimeError:
                    pass
                except Exception:
                    logger.exception("jd_parse_failed", extra={"event_name": "jd_parse_failed"})
                    st.error("Failed to parse the job description. Try a different file or format.")

        if st.button("Generate Candidate Profile", disabled=not st.session_state.get("cv_text")):
            try:
                settings = Settings(temperature=float(st.session_state["temperature"]))
                profile = profile_candidate_from_cv_text(
                    cv_text=st.session_state["cv_text"],
                    settings=settings,
                    session_id=st.session_state["session_id"],
                )
                profile_dict = profile.model_dump()
                st.session_state["profile"] = profile_dict
                st.success("Generated candidate profile.")
                logger.info("profile_generated", extra={"event_name": "profile_generated"})

                user_id = int(st.session_state.get("user_id") or 0)
                if user_id:
                    top_skills: list[str] = []
                    seen: set[str] = set()
                    for item in list(profile.skills) + list(profile.tools) + list(profile.keywords):
                        skill = str(item).strip()
                        key = skill.lower()
                        if skill and key not in seen:
                            seen.add(key)
                            top_skills.append(skill)
                        if len(top_skills) >= 10:
                            break
                    update_user_profile(user_id=user_id, profile=profile_dict, top_skills=top_skills)
                    logger.info("profile_persisted", extra={"event_name": "PROFILE_PERSISTED", "user_id": user_id})
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

        if not (st.session_state.get("jd_text") or "").strip():
            st.warning("Upload a job description to start the interview.")

        col_start, col_reset = st.columns([1, 1])
        with col_start:
            start_disabled = bool(st.session_state.get("current_question"))
            start_disabled = start_disabled or bool(st.session_state.get("interview_started"))
            start_disabled = start_disabled or not (st.session_state.get("jd_text") or "").strip()
            start_disabled = start_disabled or not (st.session_state.get("position_title") or "").strip()
            if st.button("Start interview", disabled=start_disabled):
                try:
                    profile_dict = st.session_state.get("profile")
                    if not profile_dict:
                        profile_dict = CandidateProfile(target_role=st.session_state.get("position_title") or None).model_dump()
                        st.session_state["profile"] = profile_dict

                    settings = Settings(temperature=float(st.session_state["temperature"]))
                    question = generate_interview_question(
                        profile=profile_dict,
                        job_description=str(st.session_state.get("jd_text") or ""),
                        transcript=list(st.session_state.get("transcript") or []),
                        settings=settings,
                        prompt_mode=str(st.session_state.get("prompt_mode") or DEFAULT_PROMPT_MODE),
                        session_id=st.session_state["session_id"],
                    )
                    question_id: int | None = None
                    question_order = len(list(st.session_state.get("transcript") or [])) + 1
                    user_vacancy_id = int(st.session_state.get("user_vacancy_id") or 0)
                    if user_vacancy_id:
                        question_id = create_question(
                            user_vacancy_id=user_vacancy_id,
                            question_text=question.question_text,
                            category=question.category,
                            difficulty=question.difficulty,
                            skill_tags=question.tags,
                            question_order=question_order,
                        )
                        logger.info(
                            "question_persisted",
                            extra={
                                "event_name": "QUESTION_PERSISTED",
                                "question_id": question_id,
                                "user_vacancy_id": user_vacancy_id,
                                "question_order": question_order,
                            },
                        )
                    start_interview(st.session_state, question, question_id=question_id, question_order=question_order)
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
            col_submit, col_next = st.columns([1, 1])
            with col_submit:
                submit_clicked = st.button(
                    "Submit answer",
                    disabled=not (st.session_state.get("answer_draft") or "").strip(),
                )
            with col_next:
                next_clicked = st.button("Next question")

            if submit_clicked:
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

                    jd_text = str(st.session_state.get("jd_text") or "")
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
                        "is_skipped": False,
                    }
                    next_question = generate_interview_question(
                        profile=st.session_state.get("profile"),
                        job_description=safe_jd_text,
                        transcript=transcript + [turn_dict],
                        settings=settings,
                        prompt_mode=str(st.session_state.get("prompt_mode") or DEFAULT_PROMPT_MODE),
                        session_id=st.session_state["session_id"],
                    )

                    current_question_id: int | None = st.session_state.get("current_question_id")
                    current_question_order = int(st.session_state.get("current_question_order") or (len(transcript) + 1))
                    user_vacancy_id = int(st.session_state.get("user_vacancy_id") or 0)
                    if user_vacancy_id and current_question_id is None:
                        current_question_id = create_question(
                            user_vacancy_id=user_vacancy_id,
                            question_text=q.question_text,
                            category=q.category,
                            difficulty=q.difficulty,
                            skill_tags=q.tags,
                            question_order=current_question_order,
                        )
                        st.session_state["current_question_id"] = current_question_id
                        st.session_state["current_question_order"] = current_question_order

                    if current_question_id is not None:
                        insert_answer(question_id=current_question_id, answer_text=safe_answer, is_skipped=False)

                        def to_pct(value: int) -> int:
                            return int(round((value / 5) * 100))

                        fallacy_detected = bool(fallacy_hint.possible_fallacies)
                        fallacy_name = fallacy_hint.possible_fallacies[0].type if fallacy_hint.possible_fallacies else None
                        insert_suggestion(
                            question_id=current_question_id,
                            correctness=to_pct(scorecard.correctness),
                            role_relevance=to_pct(scorecard.role_relevance),
                            red_flags_count=len(scorecard.red_flags),
                            red_flags_text="\n".join(scorecard.red_flags),
                            improvements_text="\n".join(scorecard.improvements),
                            suggested_rewrite=scorecard.suggested_rewrite if scorecard.suggested_rewrite else None,
                            followup_question=scorecard.followup_question.strip() or None,
                            fallacy_detected=fallacy_detected,
                            fallacy_name=fallacy_name,
                            fallacy_explanation=fallacy_hint.more_info_text if fallacy_detected else None,
                            coach_hint=fallacy_hint.coach_hint_text.strip() or None,
                        )

                    next_question_id: int | None = None
                    next_question_order = current_question_order + 1
                    if user_vacancy_id:
                        next_question_id = create_question(
                            user_vacancy_id=user_vacancy_id,
                            question_text=next_question.question_text,
                            category=next_question.category,
                            difficulty=next_question.difficulty,
                            skill_tags=next_question.tags,
                            question_order=next_question_order,
                        )

                    submit_answer(
                        st.session_state,
                        answer=safe_answer,
                        scorecard=scorecard,
                        next_question=next_question,
                        fallacy_hint=fallacy_hint,
                    )
                    st.session_state["current_question_id"] = next_question_id
                    st.session_state["current_question_order"] = next_question_order
                    st.session_state["answer_draft"] = ""
                    st.success("Answer submitted.")
                    logger.info("answer_submitted", extra={"event_name": "answer_submitted"})
                except RuntimeError:
                    pass
                except Exception:
                    logger.exception("answer_submit_failed", extra={"event_name": "answer_submit_failed"})
                    st.error("Failed to submit answer. Check your API key and logs.")

            if next_clicked:
                if (st.session_state.get("answer_draft") or "").strip():
                    st.warning("Submit your draft answer, or clear it to skip this question.")
                else:
                    try:
                        settings = Settings(temperature=float(st.session_state["temperature"]))
                        transcript = list(st.session_state.get("transcript") or [])

                        jd_text = str(st.session_state.get("jd_text") or "")
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

                        current_question_id: int | None = st.session_state.get("current_question_id")
                        current_question_order = int(st.session_state.get("current_question_order") or (len(transcript) + 1))
                        user_vacancy_id = int(st.session_state.get("user_vacancy_id") or 0)
                        if user_vacancy_id and current_question_id is None:
                            current_question_id = create_question(
                                user_vacancy_id=user_vacancy_id,
                                question_text=q.question_text,
                                category=q.category,
                                difficulty=q.difficulty,
                                skill_tags=q.tags,
                                question_order=current_question_order,
                            )
                            st.session_state["current_question_id"] = current_question_id
                            st.session_state["current_question_order"] = current_question_order

                        if current_question_id is not None:
                            insert_answer(question_id=current_question_id, answer_text=None, is_skipped=True)

                        turn_dict = {"question": q.model_dump(), "answer": "", "is_skipped": True}
                        next_question = generate_interview_question(
                            profile=st.session_state.get("profile"),
                            job_description=safe_jd_text,
                            transcript=transcript + [turn_dict],
                            settings=settings,
                            prompt_mode=str(st.session_state.get("prompt_mode") or DEFAULT_PROMPT_MODE),
                            session_id=st.session_state["session_id"],
                        )

                        next_question_id: int | None = None
                        next_question_order = current_question_order + 1
                        if user_vacancy_id:
                            next_question_id = create_question(
                                user_vacancy_id=user_vacancy_id,
                                question_text=next_question.question_text,
                                category=next_question.category,
                                difficulty=next_question.difficulty,
                                skill_tags=next_question.tags,
                                question_order=next_question_order,
                            )

                        skip_question(st.session_state, next_question=next_question)
                        st.session_state["current_question_id"] = next_question_id
                        st.session_state["current_question_order"] = next_question_order
                        st.session_state["answer_draft"] = ""
                        st.info("Skipped. Next question ready.")
                        logger.info("question_skipped", extra={"event_name": "question_skipped"})
                    except RuntimeError:
                        pass
                    except Exception:
                        logger.exception("next_question_failed", extra={"event_name": "next_question_failed"})
                        st.error("Failed to get the next question. Check your API key and logs.")
        elif st.session_state.get("interview_started"):
            if st.button("Next question"):
                try:
                    settings = Settings(temperature=float(st.session_state["temperature"]))
                    transcript = list(st.session_state.get("transcript") or [])

                    jd_text = str(st.session_state.get("jd_text") or "")
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

                    next_question = generate_interview_question(
                        profile=st.session_state.get("profile"),
                        job_description=safe_jd_text,
                        transcript=transcript,
                        settings=settings,
                        prompt_mode=str(st.session_state.get("prompt_mode") or DEFAULT_PROMPT_MODE),
                        session_id=st.session_state["session_id"],
                    )

                    user_vacancy_id = int(st.session_state.get("user_vacancy_id") or 0)
                    next_question_order = len(transcript) + 1
                    next_question_id: int | None = None
                    if user_vacancy_id:
                        next_question_id = create_question(
                            user_vacancy_id=user_vacancy_id,
                            question_text=next_question.question_text,
                            category=next_question.category,
                            difficulty=next_question.difficulty,
                            skill_tags=next_question.tags,
                            question_order=next_question_order,
                        )

                    st.session_state["current_question"] = next_question.model_dump()
                    st.session_state["current_question_id"] = next_question_id
                    st.session_state["current_question_order"] = next_question_order
                    st.session_state["answer_draft"] = ""
                    st.success("Next question ready.")
                    logger.info("next_question_generated", extra={"event_name": "next_question_generated"})
                except RuntimeError:
                    pass
                except Exception:
                    logger.exception("next_question_failed", extra={"event_name": "next_question_failed"})
                    st.error("Failed to get the next question. Check your API key and logs.")

    with col_b:
        st.subheader("Candidate Profile")
        if st.session_state.get("profile"):
            components.render_candidate_profile(st.session_state["profile"])
        else:
            st.info("Upload and parse a CV, then generate a profile.")

        st.subheader("Feedback")
        if st.session_state.get("last_scorecard"):
            components.render_scorecard(st.session_state["last_scorecard"])
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
            components.render_transcript(list(st.session_state.get("transcript") or []))

        with st.expander("Raw CV text", expanded=False):
            st.text_area(
                "CV text",
                value=st.session_state.get("cv_text") or "",
                height=240,
                disabled=True,
            )

        with st.expander("Raw job description", expanded=False):
            st.text_area(
                "Job description",
                value=st.session_state.get("jd_text") or "",
                height=240,
                disabled=True,
            )


if __name__ == "__main__":
    main()
