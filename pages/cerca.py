import streamlit as st

from components.ui import page_header, render_booking_cards, render_downloads, render_table_expander
from storage import booking_dataframe

def render_search(data):
    page_header("Cerca", "Ricerca trasversale su clienti, telefono, email, istruttrice, note, date e orari.", "Ricerca")
    query = st.text_input("Cerca cliente, telefono, email, istruttrice, nota, data, ora").strip().lower()
    rows = []
    for b in data["bookings"]:
        haystack = " ".join(str(b.get(k, "")) for k in ["name", "phone", "email", "instructor", "note", "date", "time", "status"]).lower()
        if not query or query in haystack:
            rows.append(b)
    df = booking_dataframe(rows)
    st.caption(f"Risultati trovati: {len(rows)}")
    render_downloads("ricerca", df, "ricerca_prenotazioni")
    render_booking_cards(rows, "Nessun risultato.")
    render_table_expander("Tabella risultati", df, "Nessun risultato.")

