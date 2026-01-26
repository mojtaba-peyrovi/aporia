from __future__ import annotations

from pathlib import Path

import streamlit as st


def find_logo_path() -> Path | None:
    candidate_paths = [
        Path.cwd() / "aporia_logo.png",
        Path(__file__).resolve().parents[3] / "aporia_logo.png",
    ]
    return next((path for path in candidate_paths if path.exists()), None)


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

  /* Fallacy ribbon/banner */
  .aporia-fallacy-ribbon {
    background: #fb923c; /* orange */
    color: #111827;
    border-left: 6px solid #ea580c;
    padding: 0.6rem 0.75rem;
    border-radius: 0.5rem;
    font-weight: 700;
    margin: 0.5rem 0 0.75rem 0;
  }
</style>
""",
        unsafe_allow_html=True,
    )


def render_topbar(*, user_label: str, show_logout: bool) -> None:
    left, right = st.columns([3, 2], vertical_alignment="center")
    with left:
        logo_path = find_logo_path()

        if logo_path:
            logo_col, title_col = st.columns([1, 8], vertical_alignment="center")
            with logo_col:
                st.image(str(logo_path), width=72)
            with title_col:
                st.markdown('<div class="aporia-logo">Interview Practice Coach</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="aporia-logo">Interview Practice Coach</div>', unsafe_allow_html=True)
    with right:
        cols = st.columns([5, 2], vertical_alignment="center")
        cols[0].markdown(f'<div class="aporia-user">Welcome, {user_label}</div>', unsafe_allow_html=True)
        if show_logout and hasattr(st, "logout"):
            cols[1].button("Logout", on_click=st.logout)  # type: ignore[attr-defined]
