from pathlib import Path
import re


def _rf(src, name, repl):
    m = re.search(rf"(^|\n)def {name}\([^\n]*\):\n.*?(?=\n\ndef |\n\n# -----------------------------|\Z)", src, re.S)
    if not m:
        return src
    return src[:m.start()] + ("\n" if m.group(1) else "") + repl.rstrip() + src[m.end():]


def _patch_app_navigation():
    p = Path(__file__).with_name("app.py")
    if not p.exists():
        return
    s = p.read_text(encoding="utf-8")

    s = _rf(s, "go", '''def go(section):
    st.session_state["_pending_section"] = section
    st.rerun()''')

    s = _rf(s, "run", '''def run():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    header()
    if not login():
        return
    data, sha = load_data()
    data = ensure_data(data)
    allowed = sections()
    pending = st.session_state.pop("_pending_section", None)
    if pending in allowed:
        st.session_state["section"] = pending
    if "section" not in st.session_state or st.session_state["section"] not in allowed:
        st.session_state["section"] = "Planning"
    section = st.radio("Sezione", allowed, horizontal=True, key="section", label_visibility="collapsed")
    col_access, col_logout = st.columns([4, 1])
    with col_access:
        st.caption(f"Accesso: {current_user().capitalize()} · {'Admin' if is_admin() else 'Istruttrice'}")
    with col_logout:
        if st.button("Logout", key="logout_user_button", use_container_width=True):
            for k in ["authenticated", "current_user", "current_role", "section", "_pending_section"]:
                st.session_state.pop(k, None)
            st.rerun()
    st.divider()
    dispatch = {"Planning": render_planning, "Prenota": render_booking, "Incassi": render_incassi, "Clienti": render_clients, "Cerca": lambda d, s: render_search(d), "Archivio": render_archive}
    dispatch[section](data, sha)''')

    p.write_text(s, encoding="utf-8")


try:
    _patch_app_navigation()
except Exception:
    pass
