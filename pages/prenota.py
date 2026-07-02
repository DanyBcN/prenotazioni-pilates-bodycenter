from datetime import date

import streamlit as st

from auth import current_instructor, navigate
from config import CAPACITY, INSTRUCTORS, SCHEDULE, parse_date
from storage import (
    add_client, auto_status, client_options, count_confirmed, create_booking, get_client,
    option_to_client_id, save_data,
)

def render_booking(data, sha):
    st.subheader("Prenota")
    mode = st.radio("Cliente", ["Seleziona da archivio", "Nuovo cliente"], horizontal=True)
    client_id = None

    if mode == "Seleziona da archivio":
        options = client_options(data)
        if not options:
            st.warning("Nessun cliente in archivio.")
        else:
            client_id = option_to_client_id(st.selectbox("Cliente", options))
            client = get_client(data, client_id)
            st.caption(f"Telefono: {client.get('phone', '')} · Email: {client.get('email', '')}")
    else:
        with st.container(border=True):
            c1, c2 = st.columns(2)
            last = c1.text_input("Cognome", key="new_last")
            first = c2.text_input("Nome", key="new_first")
            c3, c4 = st.columns(2)
            phone = c3.text_input("Telefono", key="new_phone")
            email = c4.text_input("Email", key="new_email")
            birth = st.text_input("Data di nascita", key="new_birth")
            notes = st.text_area("Note cliente", key="new_notes")
            if st.button("Salva nuovo cliente", type="primary"):
                ok, msg, client_id = add_client(data, first, last, phone, email, notes, birth)
                if ok:
                    save_data(data, sha, "Add client")
                    st.session_state["booking_client_id"] = client_id
                    navigate("Prenota")
                else:
                    st.error(msg)
        client_id = st.session_state.get("booking_client_id")

    if client_id:
        st.markdown("### Dati prenotazione")
        c1, c2 = st.columns(2)
        selected_date = parse_date(c1.date_input("Data", value=date.today(), min_value=date.today(), format="DD/MM/YYYY"))
        times = SCHEDULE.get(selected_date.weekday(), [])
        if not times:
            st.warning("Nessun orario previsto per questa data.")
            return
        selected_time = c2.selectbox("Orario", times)
        default_instructor = current_instructor()
        default_index = INSTRUCTORS.index(default_instructor) if default_instructor in INSTRUCTORS else 0
        c3, c4, c5 = st.columns(3)
        gift_flag = c3.checkbox("Seduta omaggio / prova gratuita")
        amount = c4.number_input("Importo (€)", min_value=0.0, value=0.0, step=1.0, format="%.2f", disabled=gift_flag)
        paid = c5.checkbox("Già incassato dalla palestra", disabled=gift_flag)
        instructor = st.selectbox("Istruttrice", INSTRUCTORS, index=default_index)
        note = st.text_area("Note prenotazione")
        st.info(f"{instructor} · {selected_time}: {count_confirmed(data, selected_date, selected_time, instructor)}/{CAPACITY} confermate · stato: {'Seduta omaggio' if gift_flag else auto_status(data, selected_date, selected_time, instructor)}")
        if st.button("Salva prenotazione", type="primary"):
            create_booking(data, client_id, selected_date, selected_time, amount, paid, instructor, note, gift_flag)
            save_data(data, sha, "Add booking")
            st.success("Prenotazione salvata.")
            navigate("Planning")
