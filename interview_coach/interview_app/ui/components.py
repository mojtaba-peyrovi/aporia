from __future__ import annotations

import streamlit as st


def render_key_value(label: str, value: str) -> None:
    col_a, col_b = st.columns([1, 3])
    col_a.caption(label)
    col_b.write(value)


def render_bullets(label: str, items: list[str]) -> None:
    if not items:
        return
    st.markdown(f"**{label}**")
    st.markdown("\n".join(f"- {item}" for item in items))


def render_candidate_profile(profile_dict: dict) -> None:
    from interview_app.models.schemas import CandidateProfile

    profile = CandidateProfile.model_validate(profile_dict)
    if profile.full_name:
        render_key_value("Name", profile.full_name)
    if profile.target_role:
        render_key_value("Target role", profile.target_role)
    if profile.seniority and profile.seniority != "unknown":
        render_key_value("Seniority", profile.seniority)

    if profile.summary.strip():
        st.markdown("**Summary**")
        st.write(profile.summary)

    render_bullets("Skills", profile.skills)
    render_bullets("Tools", profile.tools)
    render_bullets("Key projects", profile.key_projects)
    render_bullets("Achievements", profile.achievements)
    render_bullets("Education", profile.education)
    render_bullets("Gaps / risks", profile.gaps_or_risks)


def render_scorecard(scorecard_dict: dict) -> None:
    from interview_app.models.schemas import ScoreCard

    scorecard = ScoreCard.model_validate(scorecard_dict)

    def to_pct(value: int) -> int:
        return int(round((value / 5) * 100))

    col_a, col_b = st.columns(2)
    col_a.metric("Correctness", f"{to_pct(scorecard.correctness)}%")
    col_b.metric("Role relevance", f"{to_pct(scorecard.role_relevance)}%")

    render_bullets("Strengths", scorecard.strengths)
    render_bullets("Improvements", scorecard.improvements)
    render_bullets("Red flags", scorecard.red_flags)

    if scorecard.suggested_rewrite and scorecard.suggested_rewrite.strip():
        st.markdown("**Suggested rewrite**")
        st.write(scorecard.suggested_rewrite)

    if scorecard.followup_question.strip():
        with st.expander("Optional follow-up question", expanded=False):
            st.write(scorecard.followup_question)


def render_transcript(transcript: list[dict]) -> None:
    from interview_app.models.schemas import FallacyHint, ScoreCard
    from interview_app.services.fallacy_formatting import format_fallacy_name, get_primary_fallacy_type

    if not transcript:
        st.caption("No turns yet.")
        return

    for idx, turn in enumerate(transcript, start=1):
        st.markdown(f"**Turn {idx}**")
        st.write(turn.get("question", {}).get("question_text", ""))
        st.write("Answer:")
        st.write(turn.get("answer", ""))

        scorecard_dict = turn.get("scorecard") or {}
        if scorecard_dict:
            scorecard = ScoreCard.model_validate(scorecard_dict)
            st.caption(f"Correctness: {scorecard.correctness}/5 · Role relevance: {scorecard.role_relevance}/5")

        hint_dict = turn.get("fallacy_hint")
        if hint_dict:
            hint = FallacyHint.model_validate(hint_dict)
            fallacy_type = get_primary_fallacy_type(hint)
            if fallacy_type:
                st.markdown(
                    f'<div class="aporia-fallacy-ribbon">Fallacy Detected - {format_fallacy_name(fallacy_type)}</div>',
                    unsafe_allow_html=True,
                )
            if hint.coach_hint_text.strip():
                st.caption(f"Coach hint: {hint.coach_hint_text}")
