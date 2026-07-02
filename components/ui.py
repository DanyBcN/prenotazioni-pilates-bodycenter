import base64
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from components.pdf import pdf_bytes
from config import APP_TITLE, LOGO_PATH, date_it, instructor_share, is_gift, money, yes
from storage import to_excel_bytes


def header():
    st.markdown(
        """
        <style>
        .main .block-container {max-width: 1380px; padding-top: 1rem; padding-bottom: 2rem;}
        .bc-header {display:flex; align-items:center; gap:22px; margin-bottom:16px;}
        .bc-title {font-size:40px; font-weight:800; color:#1F2A37; line-height:1.05;}
        .bc-logo {width:92px; max-height:92px; object-fit:contain;}
        .quick-grid {display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:10px; margin:8px 0 16px;}
        .quick-card {border:1px solid #D8DEE8; border-radius:8px; padding:12px 14px; background:#fff;}
        .quick-label {font-size:0.78rem; color:#6B7280; font-weight:700; text-transform:uppercase; letter-spacing:.02em;}
        .quick-value {font-size:1.35rem; font-weight:800; color:#111827; margin-top:2px;}
        .quick-note {font-size:0.82rem; color:#6B7280; margin-top:3px;}
        .day-grid {display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:8px;}
        .day-card {border:1px solid #D8DEE8; border-radius:8px; padding:10px 12px; background:#fff; min-height:92px; box-shadow:0 1px 2px rgba(15,23,42,.04);}
        .day-empty {background:#FAFAFA; color:#9AA0A6; box-shadow:none;}
        .day-title {font-weight:800; margin-bottom:7px; color:#1F2A37;}
        .slot {font-size:0.86rem; line-height:1.28; padding:6px 0; border-bottom:1px solid #EEF0F2;}
        .slot:last-child {border-bottom:0;}
        .muted {color:#6F7782;}
        .pill {display:inline-block; border-radius:999px; padding:1px 7px; font-size:.72rem; font-weight:800; margin-left:4px;}
        .pill-ok {background:#DCFCE7; color:#166534;}
        .pill-warn {background:#FEF3C7; color:#92400E;}
        .pill-gift {background:#EDE9FE; color:#5B21B6;}
        .pill-free {background:#E0F2FE; color:#075985;}
        .bc-card-list {display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:8px; margin:8px 0 12px;}
        .bc-booking-card {border:1px solid #D8DEE8; border-radius:8px; background:#fff; padding:10px 12px; box-shadow:0 1px 2px rgba(15,23,42,.04);}
        .bc-card-top {display:flex; justify-content:space-between; gap:8px; align-items:flex-start; margin-bottom:5px;}
        .bc-card-title {font-weight:800; color:#111827; line-height:1.25;}
        .bc-card-meta {font-size:.84rem; color:#4B5563; line-height:1.35;}
        .bc-card-amount {font-weight:800; color:#111827; white-space:nowrap;}
        .bc-card-note {font-size:.8rem; color:#6B7280; margin-top:5px; overflow-wrap:anywhere;}
        .bc-card-chip {display:inline-block; margin-top:6px; border-radius:999px; padding:2px 8px; font-size:.72rem; font-weight:800; background:#EEF2FF; color:#3730A3;}
        div[data-testid="stMetric"] {background:#fff; border:1px solid #E5E7EB; border-radius:8px; padding:10px 12px;}
        .stButton > button, .stDownloadButton > button {border-radius:8px; font-weight:700; min-height:42px;}
        @media(max-width: 700px) {
          .main .block-container {padding:0.65rem 0.7rem 1.4rem;}
          .bc-header {gap:12px; margin-bottom:10px;}
          .bc-title {font-size:25px;}
          .bc-logo {width:58px; max-height:58px;}
          .quick-grid {grid-template-columns:1fr 1fr; gap:7px;}
          .quick-card {padding:9px 10px;}
          .quick-label {font-size:.68rem;}
          .quick-value {font-size:1.1rem;}
          .quick-note {font-size:.74rem;}
          .day-grid {grid-template-columns:1fr; gap:7px;}
          .day-card {min-height:0; padding:9px 10px;}
          .slot {font-size:.92rem; padding:7px 0;}
          .pill {margin-left:2px; margin-top:3px;}
          .bc-card-list {grid-template-columns:1fr;}
          .bc-booking-card {padding:10px;}
          .stButton > button, .stDownloadButton > button {width:100%; min-height:48px; font-size:1rem;}
          div[data-testid="stHorizontalBlock"] {gap:0.45rem;}
          div[data-baseweb="select"] span, input, textarea {font-size:16px !important;}
          div[data-testid="stDataFrame"] {font-size:.78rem;}
        }
        @media(max-width: 430px) {.quick-grid {grid-template-columns:1fr;}}
        </style>
        """,
        unsafe_allow_html=True,
    )
    logo = ""
    if Path(LOGO_PATH).exists():
        encoded = base64.b64encode(Path(LOGO_PATH).read_bytes()).decode("ascii")
        logo = f"<img class='bc-logo' src='data:image/png;base64,{encoded}'>"
    st.markdown(f"<div class='bc-header'>{logo}<div class='bc-title'>{APP_TITLE}</div></div>", unsafe_allow_html=True)


def render_downloads(label: str, df: pd.DataFrame, base_name: str):
    if df.empty:
        return
    col1, col2 = st.columns(2)
    col1.download_button(f"Scarica PDF {label}", data=pdf_bytes(label, df), file_name=f"{base_name}.pdf", mime="application/pdf", use_container_width=True)
    col2.download_button(f"Scarica Excel {label}", data=to_excel_bytes(df), file_name=f"{base_name}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)


def render_booking_cards(rows: list, empty_message: str = "Nessuna prenotazione.", limit: int = 80):
    if not rows:
        st.info(empty_message)
        return

    cards = []
    for booking in rows[:limit]:
        gift = is_gift(booking)
        paid = yes(booking.get("paid"))
        amount = "Omaggio" if gift else f"EUR {money(booking.get('amount')):.2f}"
        status_bits = [str(booking.get("status", ""))]
        if gift:
            status_bits.append("omaggio")
        elif paid:
            status_bits.append("incassato")
        else:
            status_bits.append("da incassare")
        if booking.get("settlement_id"):
            status_bits.append("quota chiusa")

        note = str(booking.get("note", "")).strip()
        note_html = f"<div class='bc-card-note'>{escape(note)}</div>" if note else ""
        cards.append(
            "<div class='bc-booking-card'>"
            "<div class='bc-card-top'>"
            f"<div class='bc-card-title'>{escape(str(booking.get('name', '')))}</div>"
            f"<div class='bc-card-amount'>{escape(amount)}</div>"
            "</div>"
            f"<div class='bc-card-meta'>{escape(date_it(booking.get('date')))} · {escape(str(booking.get('time', '')))} · {escape(str(booking.get('instructor', '')))}</div>"
            f"<div class='bc-card-meta'>{escape(str(booking.get('phone', '')))} {escape(str(booking.get('email', '')))}</div>"
            f"<span class='bc-card-chip'>{escape(' · '.join(filter(None, status_bits)))}</span>"
            f"{note_html}"
            "</div>"
        )

    if len(rows) > limit:
        cards.append(f"<div class='bc-card-note'>Mostrate {limit} di {len(rows)} prenotazioni. Usa download o tabella completa per il resto.</div>")
    st.markdown("<div class='bc-card-list'>" + "".join(cards) + "</div>", unsafe_allow_html=True)


def render_client_cards(clients: list, empty_message: str = "Nessun cliente.", limit: int = 80):
    if not clients:
        st.info(empty_message)
        return

    cards = []
    for client in clients[:limit]:
        name = f"{client.get('last_name', '')} {client.get('first_name', '')}".strip()
        notes = str(client.get("notes", "")).strip()
        note_html = f"<div class='bc-card-note'>{escape(notes)}</div>" if notes else ""
        cards.append(
            "<div class='bc-booking-card'>"
            f"<div class='bc-card-title'>{escape(name)}</div>"
            f"<div class='bc-card-meta'>{escape(str(client.get('phone', '')))}</div>"
            f"<div class='bc-card-meta'>{escape(str(client.get('email', '')))}</div>"
            f"{note_html}"
            "</div>"
        )
    if len(clients) > limit:
        cards.append(f"<div class='bc-card-note'>Mostrati {limit} di {len(clients)} clienti. Usa la tabella completa per il resto.</div>")
    st.markdown("<div class='bc-card-list'>" + "".join(cards) + "</div>", unsafe_allow_html=True)


def render_table_expander(title: str, df: pd.DataFrame, empty_message: str, expanded: bool = False):
    with st.expander(title, expanded=expanded):
        if df.empty:
            st.info(empty_message)
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
