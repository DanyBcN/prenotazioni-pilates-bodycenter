import pandas as pd
import streamlit as st

from auth import navigate
from components.ui import page_header, render_client_cards, render_table_expander
from config import full_name
from storage import (
    add_client, client_options, get_client, option_to_client_id, save_data, update_client,
)

def render_clients(data, sha):
    page_header("Clienti", "Anagrafica chiara, card contatto e schede modificabili senza perdere il contesto.", "Anagrafica")

    with st.expander("Aggiungi cliente", expanded=False):
        c1, c2 = st.columns(2)
        last = c1.text_input("Cognome", key="add_last")
        first = c2.text_input("Nome", key="add_first")
        c3, c4 = st.columns(2)
        phone = c3.text_input("Telefono", key="add_phone")
        email = c4.text_input("Email", key="add_email")
        birth = st.text_input("Data di nascita", key="add_birth")
        notes = st.text_area("Note", key="add_notes")
        if st.button("Salva nuovo cliente", type="primary"):
            ok, msg, client_id = add_client(data, first, last, phone, email, notes, birth)
            if ok:
                st.session_state["edit_client_id"] = client_id
                save_data(data, sha, "Add client")
                navigate("Clienti")
            else:
                st.error(msg)

    clients = sorted(data["clients"], key=lambda c: (str(c.get("last_name", "")).lower(), str(c.get("first_name", "")).lower()))
    clients_df = pd.DataFrame(
        [
            {
                "Cognome": c.get("last_name", ""),
                "Nome": c.get("first_name", ""),
                "Telefono": c.get("phone", ""),
                "Email": c.get("email", ""),
                "Note": c.get("notes", ""),
            }
            for c in clients
        ]
    )
    m1, m2, m3 = st.columns(3)
    m1.metric("Clienti", len(clients))
    m2.metric("Con email", len([c for c in clients if c.get("email")]))
    m3.metric("Con note", len([c for c in clients if c.get("notes")]))
    render_client_cards(clients, "Nessun cliente.")
    render_table_expander("Tabella clienti", clients_df, "Nessun cliente.")

    st.markdown("### Modifica scheda cliente")
    options = client_options(data)
    if not options:
        return
    selected = st.selectbox("Scegli cliente", options, key="client_pick_to_open")
    selected_id = option_to_client_id(selected)
    if st.button("Apri scheda selezionata", type="primary"):
        st.session_state["edit_client_id"] = selected_id
        st.rerun()

    client_id = st.session_state.get("edit_client_id", "")
    client = get_client(data, client_id)
    if not client:
        st.info("Scegli un cliente e clicca 'Apri scheda selezionata'.")
        return

    st.success(f"Scheda aperta: {full_name(client)}")
    with st.form(f"edit_client_{client_id}", clear_on_submit=False):
        c1, c2 = st.columns(2)
        last = c1.text_input("Cognome", value=client.get("last_name", ""), key=f"last_{client_id}")
        first = c2.text_input("Nome", value=client.get("first_name", ""), key=f"first_{client_id}")
        c3, c4 = st.columns(2)
        phone = c3.text_input("Telefono", value=client.get("phone", ""), key=f"phone_{client_id}")
        email = c4.text_input("Email", value=client.get("email", ""), key=f"email_{client_id}")
        birth = st.text_input("Data nascita", value=client.get("birth_date", ""), key=f"birth_{client_id}")
        notes = st.text_area("Note", value=client.get("notes", ""), key=f"notes_{client_id}")
        submitted = st.form_submit_button("Salva questa scheda cliente", type="primary")

    if submitted:
        ok, msg = update_client(data, client_id, first, last, phone, email, birth, notes)
        if ok:
            st.session_state["edit_client_id"] = client_id
            save_data(data, sha, "Update client")
            navigate("Clienti")
        else:
            st.error(msg)



