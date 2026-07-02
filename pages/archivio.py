import streamlit as st

from components.ui import render_downloads
from storage import booking_dataframe

def render_archive(data, sha):
    st.subheader("Archivio prenotazioni")
    rows = sorted(data["bookings"], key=lambda b: (b.get("date", ""), b.get("time", ""), b.get("instructor", ""), b.get("name", "")), reverse=True)
    df = booking_dataframe(rows)
    render_downloads("archivio", df, "archivio_prenotazioni")
    st.dataframe(df, use_container_width=True, hide_index=True) if not df.empty else st.info("Archivio vuoto.")
