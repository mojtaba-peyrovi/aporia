from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st

from interview_app.db import upsert_user_identity
from interview_app.ui.layout import find_logo_path


@dataclass(frozen=True)
class UserIdentity:
    email: str
    first_name: str
    last_name: str

    @property
    def display_name(self) -> str:
        full = f"{self.first_name} {self.last_name}".strip()
        return full or self.email


def _maybe_get(obj: Any, key: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    if hasattr(obj, "get"):
        try:
            return obj.get(key)
        except Exception:
            return None
    return getattr(obj, key, None)


def _parse_name(name: str | None) -> tuple[str, str]:
    if not name:
        return "", ""
    parts = [p for p in name.strip().split() if p]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _identity_from_streamlit_user(user: Any) -> UserIdentity | None:
    email = _maybe_get(user, "email")
    email_str = str(email).strip() if email else ""
    if not email_str:
        return None

    first = _maybe_get(user, "given_name") or _maybe_get(user, "first_name")
    last = _maybe_get(user, "family_name") or _maybe_get(user, "last_name")
    name = _maybe_get(user, "name")
    if not (first or last) and name:
        first, last = _parse_name(str(name))

    first_str = str(first).strip() if first else ""
    last_str = str(last).strip() if last else ""
    return UserIdentity(email=email_str, first_name=first_str, last_name=last_str)


def require_user_identity(*, logger) -> UserIdentity:
    existing = st.session_state.get("user_identity")
    if existing:
        return UserIdentity(**existing)

    show_logout = False
    if hasattr(st, "login"):
        try:
            st.login()  # type: ignore[attr-defined]
            show_logout = True
        except Exception:
            show_logout = False

    identity = _identity_from_streamlit_user(getattr(st, "user", None))

    if identity and identity.first_name and identity.last_name:
        user_id = upsert_user_identity(email=identity.email, first_name=identity.first_name, last_name=identity.last_name)
        st.session_state["user_id"] = user_id
        st.session_state["user_identity"] = {
            "email": identity.email,
            "first_name": identity.first_name,
            "last_name": identity.last_name,
        }
        logger.info("auth_user_ready", extra={"event_name": "AUTH_USER_READY", "user_id": user_id})
        return identity

    with st.form("user_identity_form", border=True):
        logo_path = find_logo_path()
        if logo_path:
            _, col, _ = st.columns([1, 2, 1])
            with col:
                st.image(str(logo_path), width=144)
        st.subheader("Complete your profile")
        st.caption("We only ask once. This is stored in the app database.")
        email = st.text_input("Email", value=identity.email if identity else "")
        col_a, col_b = st.columns(2)
        with col_a:
            first_name = st.text_input("First name", value=identity.first_name if identity else "")
        with col_b:
            last_name = st.text_input("Last name", value=identity.last_name if identity else "")
        submitted = st.form_submit_button("Continue")

    if not submitted:
        st.stop()

    email = email.strip()
    first_name = first_name.strip()
    last_name = last_name.strip()
    if not email or not first_name or not last_name:
        st.error("Please provide email, first name, and last name.")
        st.stop()

    identity = UserIdentity(email=email, first_name=first_name, last_name=last_name)
    user_id = upsert_user_identity(email=identity.email, first_name=identity.first_name, last_name=identity.last_name)
    st.session_state["user_id"] = user_id
    st.session_state["user_identity"] = {"email": email, "first_name": first_name, "last_name": last_name}
    logger.info("auth_user_ready", extra={"event_name": "AUTH_USER_READY", "user_id": user_id})
    return identity


def can_show_logout() -> bool:
    return bool(hasattr(st, "logout") and hasattr(st, "login"))
