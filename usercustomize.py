from pathlib import Path


def _add_logout_button():
    p = Path(__file__).with_name("app.py")
    if not p.exists():
        return
    s = p.read_text(encoding="utf-8")
    if 'key="logout_user_button"' in s:
        return

    old = 'section = st.radio("Sezione", allowed_sections, horizontal=True, key="section", label_visibility="collapsed")'
    new = '''section = st.radio("Sezione", allowed_sections, horizontal=True, key="section", label_visibility="collapsed")

user_label = current_user().capitalize() if "current_user" in globals() else "Utente"
role_label = "Admin" if is_admin() else "Istruttrice"
col_user, col_logout = st.columns([4, 1])
with col_user:
    st.caption(f"Accesso: {user_label} · {role_label}")
with col_logout:
    if st.button("Logout", key="logout_user_button", use_container_width=True):
        for k in ["authenticated", "current_user", "current_role", "section", "client_open_id", "archive_open_client_id", "archive_open_select"]:
            st.session_state.pop(k, None)
        st.rerun()'''
    if old in s:
        s = s.replace(old, new, 1)
        p.write_text(s, encoding="utf-8")


try:
    _add_logout_button()
except Exception:
    pass
