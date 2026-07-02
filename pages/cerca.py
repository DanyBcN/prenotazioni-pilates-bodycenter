import streamlit as st

from components.ui import render_downloads
from storage import booking_dataframe

def render_search(data):
    st.subheader("Cerca")
    query = st.text_input("Cerca cliente, telefono, email, istruttrice, nota, data, ora").strip().lower()
    rows = []
    for b in data["bookings"]:
        haystack = " ".join(str(b.get(k, "")) for k in ["name", "phone", "email", "instructor", "note", "date", "time", "status"]).lower()
        if not query or query in haystack:
            rows.append(b)
    df = booking_dataframe(rows)
    render_downloads("ricerca", df, "ricerca_prenotazioni")
    st.dataframe(df, use_container_width=True, hide_index=True) if not df.empty else st.info("Nessun risultato.")
