import streamlit as st

from components.ui import render_booking_cards, render_downloads, render_table_expander
from storage import booking_dataframe


def render_archive(data, sha):
    st.subheader('Archivio prenotazioni')
    rows = sorted(data.get('bookings', []), key=lambda b: (b.get('date', ''), b.get('time', ''), b.get('instructor', ''), b.get('name', '')), reverse=True)
    df = booking_dataframe(rows)
    render_downloads('archivio', df, 'archivio_prenotazioni')
    render_booking_cards(rows, 'Archivio vuoto.')
    render_table_expander('Tabella archivio', df, 'Archivio vuoto.')
