import streamlit as st

from components.ui import page_header, render_booking_cards, render_downloads, render_table_expander
from storage import booking_dataframe

def render_archive(data, sha):
    page_header("Archivio prenotazioni", "Storico completo consultabile con card compatte, tabella e download.", "Archivio")
    rows = sorted(data["bookings"], key=lambda b: (b.get("date", ""), b.get("time", ""), b.get("instructor", ""), b.get("name", "")), reverse=True)
    df = booking_dataframe(rows)
    c1, c2, c3 = st.columns(3)
    c1.metric("Prenotazioni", len(rows))
    c2.metric("Attive", len([b for b in rows if b.get("status") != "Annullata"]))
    c3.metric("Annullate", len([b for b in rows if b.get("status") == "Annullata"]))
    render_downloads("archivio", df, "archivio_prenotazioni")
    render_booking_cards(rows, "Archivio vuoto.")
    render_table_expander("Tabella archivio", df, "Archivio vuoto.")

