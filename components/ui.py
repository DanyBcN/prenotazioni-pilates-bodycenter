import base64
from pathlib import Path

import pandas as pd
import streamlit as st

from components.pdf import pdf_bytes
from config import APP_TITLE, LOGO_PATH
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
        div[data-testid="stMetric"] {background:#fff; border:1px solid #E5E7EB; border-radius:8px; padding:10px 12px;}
        .stButton > button {border-radius:8px; font-weight:700;}
        @media(max-width: 700px) {.bc-title{font-size:27px}.bc-logo{width:64px}.day-card{min-height:70px}.quick-grid{grid-template-columns:1fr}}
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
