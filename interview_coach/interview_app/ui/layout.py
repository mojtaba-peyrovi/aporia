from __future__ import annotations

import streamlit as st


def inject_global_css() -> None:
    st.markdown(
        """
<style>
  /* Center content to ~80% width (with a max width) */
  .block-container {
    width: 80%;
    max-width: 1200px;
    padding-top: 1.5rem;
    padding-bottom: 4rem;
  }

  /* A simple top bar */
  .aporia-topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 0.75rem;
  }
  .aporia-logo {
    font-weight: 700;
    letter-spacing: 0.2px;
  }
  .aporia-user {
    color: rgb(107, 114, 128);
    font-size: 0.9rem;
    white-space: nowrap;
  }
</style>
""",
        unsafe_allow_html=True,
    )


def render_topbar(*, user_label: str, show_logout: bool) -> None:
    left, right = st.columns([3, 2], vertical_alignment="center")
    with left:
        st.markdown('<div class="aporia-logo">[Logo] Interview Practice Coach</div>', unsafe_allow_html=True)
    with right:
        cols = st.columns([5, 2], vertical_alignment="center")
        cols[0].markdown(f'<div class="aporia-user">Welcome, {user_label}</div>', unsafe_allow_html=True)
        if show_logout and hasattr(st, "logout"):
            cols[1].button("Logout", on_click=st.logout)  # type: ignore[attr-defined]
