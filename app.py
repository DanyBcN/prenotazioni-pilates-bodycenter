import streamlit as st

from auth import allowed_sections, current_user, is_admin, login
from components.ui import header
from config import APP_TITLE
from pages.archivio import render_archive
from pages.cerca import render_search
from pages.clienti import render_clients
from pages.incassi import render_cash
from pages.planning import render_planning
from pages.prenota import render_booking
from storage import ensure_data, load_data


def run():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    header()
    if not login():
        return

    data, sha = load_data()
    data = ensure_data(data)

    allowed = allowed_sections()
    next_section = st.session_state.pop("_next_section", None)
    if next_section in allowed:
        st.session_state["section"] = next_section
    if st.session_state.get("section") not in allowed:
        st.session_state["section"] = "Planning"

    with st.sidebar:
        st.markdown("### Menu")
        st.caption(f"Accesso: {current_user().capitalize()} - {'Admin' if is_admin() else 'Istruttrice'}")
        if st.button("Logout", use_container_width=True):
            for key in [
                "authenticated",
                "current_user",
                "current_role",
                "section",
                "_next_section",
                "edit_client_id",
                "booking_client_id",
            ]:
                st.session_state.pop(key, None)
            st.rerun()

        section = st.radio("Sezione", allowed, key="section", label_visibility="collapsed")

    dispatch = {
        "Planning": render_planning,
        "Prenota": render_booking,
        "Incassi": render_cash,
        "Clienti": render_clients,
        "Cerca": lambda d, s: render_search(d),
        "Archivio": render_archive,
    }
    dispatch[section](data, sha)


if __name__ == "__main__":
    run()
