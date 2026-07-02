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
        :root {
          --bc-green-900:#244236;
          --bc-green-800:#315645;
          --bc-green-700:#3F6F56;
          --bc-green-600:#5F8F6B;
          --bc-green-100:#EAF4ED;
          --bc-green-50:#F5FAF6;
          --bc-sage:#DCEBDD;
          --bc-mint:#EFF8F0;
          --bc-cream:#FFFDF7;
          --bc-ink:#17211B;
          --bc-muted:#68766D;
          --bc-border:#D8E6DA;
          --bc-warn:#F59E0B;
          --bc-shadow:0 14px 35px rgba(36,66,54,.10);
        }
        .stApp {background:radial-gradient(circle at top left,rgba(220,235,221,.92) 0,rgba(245,250,246,.92) 26%,#FFFFFF 62%); color:var(--bc-ink);}
        .main .block-container {max-width: 1400px; padding-top: 1rem; padding-bottom: 2rem;}
        section[data-testid="stSidebar"] {background:linear-gradient(180deg,#244236 0%,#315645 48%,#F5FAF6 48%,#F5FAF6 100%); border-right:1px solid rgba(36,66,54,.16);}
        section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {padding-top:1.25rem;}
        section[data-testid="stSidebar"] h3 {color:#FFFFFF; font-weight:850; letter-spacing:.02em;}
        .sidebar-brand {padding:14px 12px 18px; margin:0 0 12px; color:#fff; border:1px solid rgba(255,255,255,.18); border-radius:16px; background:rgba(255,255,255,.08); box-shadow:0 12px 30px rgba(0,0,0,.12);}
        .sidebar-kicker {font-size:.72rem; font-weight:900; letter-spacing:.10em; text-transform:uppercase; opacity:.82;}
        .sidebar-title {font-size:1.28rem; line-height:1.1; font-weight:950; margin-top:4px;}
        .sidebar-subtitle {font-size:.82rem; opacity:.82; margin-top:4px;}
        .sidebar-menu-label {font-size:.72rem; font-weight:900; letter-spacing:.10em; text-transform:uppercase; color:#244236; margin:18px 2px 6px;}
        section[data-testid="stSidebar"] .stCaption, section[data-testid="stSidebar"] p {color:rgba(255,255,255,.86);}
        section[data-testid="stSidebar"] div[role="radiogroup"] {background:#FFFFFF; border:1px solid var(--bc-border); border-radius:14px; padding:8px; box-shadow:0 10px 26px rgba(36,66,54,.13);}
        section[data-testid="stSidebar"] label[data-baseweb="radio"] {border-radius:10px; padding:8px 10px; margin:2px 0;}
        section[data-testid="stSidebar"] label[data-baseweb="radio"]:hover {background:var(--bc-green-50);}
        .bc-header {display:flex; align-items:center; gap:22px; margin-bottom:16px; padding:16px 18px; border:1px solid var(--bc-border); border-radius:16px; background:linear-gradient(135deg,rgba(255,255,255,.96),rgba(245,250,246,.94)); box-shadow:var(--bc-shadow);}
        .bc-title {font-size:40px; font-weight:900; color:var(--bc-green-900); line-height:1.05; letter-spacing:-.01em;}
        .bc-logo {width:92px; max-height:92px; object-fit:contain; filter:drop-shadow(0 8px 14px rgba(36,66,54,.18));}
        .page-hero {border:1px solid var(--bc-border); border-radius:18px; padding:18px 20px; margin:4px 0 16px; background:linear-gradient(135deg,#FFFFFF 0%,#F5FAF6 54%,#EAF4ED 100%); box-shadow:var(--bc-shadow); position:relative; overflow:hidden;}
        .page-hero:after {content:""; position:absolute; right:-42px; top:-55px; width:170px; height:170px; border-radius:999px; background:rgba(95,143,107,.13);}
        .page-eyebrow {font-size:.74rem; font-weight:900; letter-spacing:.08em; text-transform:uppercase; color:var(--bc-green-700); margin-bottom:4px;}
        .page-title {font-size:1.7rem; font-weight:900; color:var(--bc-green-900); line-height:1.12;}
        .page-subtitle {font-size:.94rem; color:var(--bc-muted); margin-top:5px; max-width:850px;}
        .quick-grid {display:grid; grid-template-columns:repeat(auto-fit,minmax(185px,1fr)); gap:12px; margin:10px 0 18px;}
        .quick-card {border:1px solid var(--bc-border); border-radius:14px; padding:14px 15px; background:rgba(255,255,255,.96); box-shadow:0 8px 20px rgba(36,66,54,.07);}
        .quick-card:hover, .bc-booking-card:hover, .day-card:hover {transform:translateY(-1px); box-shadow:0 14px 28px rgba(36,66,54,.10);}
        .bc-attention {border-color:#F1B85B; background:linear-gradient(135deg,#FFF8E8,#FFFFFF);}
        .bc-cash-summary {min-height:118px; border-left:5px solid var(--bc-green-600);}
        .bc-section-title {font-size:1.08rem; font-weight:900; color:var(--bc-green-900); margin:18px 0 9px;}
        .quick-label {font-size:0.72rem; color:var(--bc-green-700); font-weight:900; text-transform:uppercase; letter-spacing:.06em;}
        .quick-value {font-size:1.46rem; font-weight:900; color:var(--bc-ink); margin-top:2px;}
        .quick-note {font-size:0.82rem; color:var(--bc-muted); margin-top:4px;}
        .day-grid {display:grid; grid-template-columns:repeat(auto-fit,minmax(235px,1fr)); gap:10px;}
        .day-card {border:1px solid var(--bc-border); border-radius:14px; padding:12px 13px; background:#fff; min-height:104px; box-shadow:0 8px 20px rgba(36,66,54,.06); transition:all .15s ease;}
        .day-empty {background:linear-gradient(135deg,#FAFCFA,#F3F8F4); color:#9AA7A0; box-shadow:none;}
        .day-open {border-left:5px solid #64A46F;}
        .day-busy {border-left:5px solid #F1B85B; background:linear-gradient(135deg,#FFFFFF,#FFF9ED);}
        .day-full {border-left:5px solid #C95F54; background:linear-gradient(135deg,#FFFFFF,#FFF2F0);}
        .day-title {font-weight:900; margin-bottom:8px; color:var(--bc-green-900); display:flex; justify-content:space-between; gap:8px;}
        .day-count {font-size:.72rem; color:var(--bc-muted); background:var(--bc-green-100); border-radius:999px; padding:2px 8px; white-space:nowrap;}
        .slot {font-size:0.88rem; line-height:1.34; padding:7px 0; border-bottom:1px solid #EDF3EE;}
        .slot:last-child {border-bottom:0;}
        .slot-time {font-weight:900; color:var(--bc-green-900);}
        .muted {color:var(--bc-muted);}
        .pill {display:inline-block; border-radius:999px; padding:2px 8px; font-size:.72rem; font-weight:900; margin-left:4px;}
        .pill-ok {background:#DCEBDD; color:#244236;}
        .pill-warn {background:#FEF3C7; color:#92400E;}
        .pill-gift {background:#EDE9FE; color:#5B21B6;}
        .pill-free {background:#DDF7E5; color:#25613D;}
        .bc-card-list {display:grid; grid-template-columns:repeat(auto-fit,minmax(245px,1fr)); gap:10px; margin:9px 0 14px;}
        .bc-booking-card {border:1px solid var(--bc-border); border-radius:14px; background:#fff; padding:12px 13px; box-shadow:0 8px 20px rgba(36,66,54,.06); transition:all .15s ease;}
        .bc-card-top {display:flex; justify-content:space-between; gap:8px; align-items:flex-start; margin-bottom:5px;}
        .bc-card-title {font-weight:900; color:var(--bc-green-900); line-height:1.25;}
        .bc-card-meta {font-size:.84rem; color:var(--bc-muted); line-height:1.38;}
        .bc-card-amount {font-weight:900; color:var(--bc-green-800); white-space:nowrap;}
        .bc-card-note {font-size:.8rem; color:var(--bc-muted); margin-top:5px; overflow-wrap:anywhere;}
        .bc-card-chip {display:inline-block; margin-top:7px; border-radius:999px; padding:3px 9px; font-size:.72rem; font-weight:900; background:var(--bc-green-100); color:var(--bc-green-800);}
        div[data-testid="stMetric"] {background:#fff; border:1px solid var(--bc-border); border-radius:14px; padding:11px 13px; box-shadow:0 6px 18px rgba(36,66,54,.055);}
        .stButton > button, .stDownloadButton > button {border-radius:12px; font-weight:850; min-height:44px; border:1px solid var(--bc-green-600); box-shadow:0 5px 14px rgba(36,66,54,.10);}
        .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {background:linear-gradient(135deg,#315645,#5F8F6B); border:0; color:white;}
        .stButton > button:hover, .stDownloadButton > button:hover {border-color:var(--bc-green-800); transform:translateY(-1px);}
        div[data-baseweb="input"], div[data-baseweb="select"] > div, textarea {border-radius:12px !important;}
        [data-testid="stExpander"] {border:1px solid var(--bc-border); border-radius:14px; background:#fff; box-shadow:0 6px 18px rgba(36,66,54,.04);}
        @media(max-width: 700px) {
          .main .block-container {padding:0.65rem 0.7rem 1.4rem;}
          .bc-header {gap:12px; margin-bottom:10px; padding:12px;}
          .bc-title {font-size:25px;}
          .page-hero {padding:13px; margin-bottom:11px; border-radius:14px;}
          .page-title {font-size:1.28rem;}
          .page-subtitle {font-size:.84rem;}
          .bc-logo {width:58px; max-height:58px;}
          .quick-grid {grid-template-columns:1fr 1fr; gap:8px;}
          .quick-card {padding:10px;}
          .quick-label {font-size:.66rem;}
          .quick-value {font-size:1.12rem;}
          .quick-note {font-size:.74rem;}
          .day-grid {grid-template-columns:1fr; gap:8px;}
          .day-card {min-height:0; padding:10px;}
          .slot {font-size:.93rem; padding:8px 0;}
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


def page_header(title: str, subtitle: str = "", eyebrow: str = "Gestionale"):
    subtitle_html = f"<div class='page-subtitle'>{escape(subtitle)}</div>" if subtitle else ""
    st.markdown(
        f"<div class='page-hero'><div class='page-eyebrow'>{escape(eyebrow)}</div>"
        f"<div class='page-title'>{escape(title)}</div>{subtitle_html}</div>",
        unsafe_allow_html=True,
    )


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
