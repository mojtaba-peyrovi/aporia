from __future__ import annotations

import streamlit as st


def render_key_value(label: str, value: str) -> None:
    col_a, col_b = st.columns([1, 3])
    col_a.caption(label)
    col_b.write(value)

