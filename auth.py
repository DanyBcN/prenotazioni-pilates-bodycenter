import json

import streamlit as st

from config import INSTRUCTORS, secret

def users_config() -> dict:
    raw = secret("USERS", "").strip()
    if raw:
        try:
            users = json.loads(raw)
            return {str(k).lower().strip(): v for k, v in users.items() if isinstance(v, dict)}
        except Exception as exc:
            st.error(f"Secret USERS non valido: {exc}")
            st.stop()
    return {"bodycenter": {"password": secret("APP_PASSWORD", "pilates123"), "role": "admin"}}

def current_user() -> str:
    return st.session_state.get("current_user", "bodycenter")

def current_role() -> str:
    return st.session_state.get("current_role", "admin")

def is_admin() -> bool:
    return current_role() == "admin"

def current_instructor() -> str:
    user = current_user().lower().strip()
    return next((name for name in INSTRUCTORS if name.lower() == user), "")

def allowed_sections():
    if is_admin():
        return ["Planning", "Prenota", "Incassi", "Clienti", "Cerca", "Archivio"]
    return ["Planning", "Prenota", "Incassi", "Clienti"]

def navigate(section: str):
    st.session_state["_next_section"] = section
    st.rerun()

def login() -> bool:
    if st.session_state.get("authenticated"):
        return True

    users = users_config()
    _, col, _ = st.columns([1.3, 1.1, 1.3])
    with col:
        st.markdown("### Accesso staff")
        username = st.selectbox("Utente", list(users.keys()), key="login_user")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Accedi", type="primary", use_container_width=True):
            cfg = users.get(str(username).lower().strip(), {})
            if password and password == str(cfg.get("password", "")):
                st.session_state["authenticated"] = True
                st.session_state["current_user"] = str(username).lower().strip()
                st.session_state["current_role"] = str(cfg.get("role", "instructor")).lower().strip()
                navigate("Planning")
            else:
                st.error("Utente o password non corretti.")
    return False
