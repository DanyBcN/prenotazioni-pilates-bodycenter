from datetime import date, timedelta

import streamlit as st

from auth import current_instructor, is_admin, navigate
from components.ui import render_booking_cards, render_downloads, render_table_expander
from config import CAPACITY, INSTRUCTORS, PLANNING_DAYS, date_label, date_it, is_gift, money, parse_date, yes
from storage import (
    booking_dataframe, cancel_booking, open_rows, planning_rows, row_label, save_data,
)

def render_quick_actions():
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("Nuova prenotazione", type="primary", use_container_width=True):
        navigate("Prenota")
    if c2.button("Vai a Incassi", use_container_width=True):
        navigate("Incassi")
    if c3.button("Clienti", use_container_width=True):
        navigate("Clienti")
    if is_admin() and c4.button("Archivio", use_container_width=True):
        navigate("Archivio")

def render_dashboard(data: dict, instructor: str = ""):
    today_key = date.today().isoformat()
    rows = [b for b in data.get("bookings", []) if b.get("status") != "Annullata" and (not instructor or b.get("instructor") == instructor)]
    today_rows = [b for b in rows if b.get("date") == today_key]
    upcoming = planning_rows(data, 14, instructor)
    unpaid = [b for b in open_rows(data, instructor) if not is_gift(b) and not yes(b.get("paid"))]
    paid_open_share = [b for b in open_rows(data, instructor) if not is_gift(b) and yes(b.get("paid")) and not b.get("settlement_id")]
    gifts = [b for b in upcoming if is_gift(b)]

    st.markdown(
        f"""
        <div class="quick-grid">
          <div class="quick-card"><div class="quick-label">Oggi</div><div class="quick-value">{len(today_rows)}</div><div class="quick-note">lezioni/prenotazioni attive</div></div>
          <div class="quick-card"><div class="quick-label">Prossimi 14 giorni</div><div class="quick-value">{len(upcoming)}</div><div class="quick-note">prenotazioni in agenda</div></div>
          <div class="quick-card"><div class="quick-label">Da incassare</div><div class="quick-value">â‚¬ {sum(money(b.get("amount")) for b in unpaid):.2f}</div><div class="quick-note">{len(unpaid)} movimenti aperti</div></div>
          <div class="quick-card"><div class="quick-label">Quote 40%</div><div class="quick-value">{len(paid_open_share)}</div><div class="quick-note">da chiudere Â· {len(gifts)} omaggi</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def cancel_box(data, sha):
    future = []
    for b in data["bookings"]:
        try:
            if b.get("status") != "Annullata" and not b.get("settlement_id") and parse_date(b.get("date")) >= date.today():
                future.append(b)
        except Exception:
            pass
    future = sorted(future, key=lambda b: (b.get("date", ""), b.get("time", ""), b.get("instructor", ""), b.get("name", "")))

    with st.expander("Annulla prenotazione", expanded=False):
        if not future:
            st.info("Nessuna prenotazione futura annullabile.")
            return
        idx = st.selectbox("Prenotazione", range(len(future)), format_func=lambda i: row_label(future[i]))
        note = st.text_input("Motivo / nota opzionale")
        confirm = st.checkbox("Confermo l'annullamento")
        if st.button("Annulla prenotazione selezionata"):
            if not confirm:
                st.warning("Spunta la conferma prima di annullare.")
                return
            ok, msg = cancel_booking(data, future[idx].get("id"), note)
            if ok:
                save_data(data, sha, "Cancel booking")
                navigate("Planning")
            else:
                st.error(msg)

def render_planning_grid(rows: list, title: str, days: int = PLANNING_DAYS, show_instructor: bool = True):
    st.markdown(f"### {title}")
    today = date.today()
    all_days = [(today + timedelta(days=i)).isoformat() for i in range(days)]
    by_day = {d: [] for d in all_days}
    for row in rows:
        by_day.setdefault(row.get("date", ""), []).append(row)

    c1, c2, c3 = st.columns(3)
    c1.metric("Oggi", len([r for r in rows if r.get("date") == today.isoformat()]))
    c2.metric(f"Prossimi {days} giorni", len(rows))
    c3.metric("Omaggio", len([r for r in rows if is_gift(r)]))

    cards = []
    for day_key in all_days:
        grouped = {}
        for row in by_day.get(day_key, []):
            grouped.setdefault((row.get("time", ""), row.get("instructor", "")), []).append(row)

        lines = []
        for (time, instructor), group in sorted(grouped.items(), key=lambda item: item[0]):
            confirmed_rows = [r for r in group if r.get("status") == "Confermata"]
            waiting_rows = [r for r in group if r.get("status") == "Lista attesa"]
            gift_count = len([r for r in group if is_gift(r)])
            free_spots = max(CAPACITY - len(confirmed_rows), 0)
            names = ", ".join([r.get("name", "") + (" (omaggio)" if is_gift(r) else "") for r in confirmed_rows]) or "â€”"
            instructor_html = f" <span class='muted'>{instructor}</span>" if show_instructor and instructor else ""
            waiting = f"<span class='pill pill-warn'>att {len(waiting_rows)}</span>" if waiting_rows else ""
            gift = f"<span class='pill pill-gift'>{gift_count} omaggio</span>" if gift_count else ""
            free = f"<span class='pill pill-free'>{free_spots} liberi</span>"
            status = "<span class='pill pill-ok'>pieno</span>" if free_spots == 0 else free
            lines.append(
                f"<div class='slot'><b>{time}</b>{instructor_html} "
                f"<span class='muted'>{len(confirmed_rows)}/{CAPACITY}</span> {status}{waiting}{gift}<br>"
                f"<small>{names}</small></div>"
            )
        body = "".join(lines) if lines else "<div class='muted'>â€”</div>"
        cls = "day-card day-empty" if not lines else "day-card"
        cards.append(f"<div class='{cls}'><div class='day-title'>{date_label(day_key)}</div>{body}</div>")

    st.markdown("<div class='day-grid'>" + "".join(cards) + "</div>", unsafe_allow_html=True)

    df = booking_dataframe(rows)
    with st.expander("Elenco rapido", expanded=False):
        render_booking_cards(rows, "Nessuna prenotazione nel periodo.")
        render_table_expander("Tabella completa", df, "Nessuna prenotazione nel periodo.")

def render_planning(data, sha):
    st.subheader("Planning 3 mesi")
    pdf_scope = "" if is_admin() else current_instructor()
    render_dashboard(data, pdf_scope)
    render_quick_actions()

    pdf_rows = planning_rows(data, PLANNING_DAYS, pdf_scope)
    df = booking_dataframe(pdf_rows)

    with st.expander("Download planning", expanded=False):
        render_downloads("planning", df, "planning_3_mesi")

    cancel_box(data, sha)

    if is_admin():
        view = st.selectbox("Vista", ["Tutte", *INSTRUCTORS])
        instructor = "" if view == "Tutte" else view
        render_planning_grid(planning_rows(data, PLANNING_DAYS, instructor), f"Planning {view}", PLANNING_DAYS, True)
    else:
        instructor = current_instructor()
        tab_all, tab_mine = st.tabs(["Planning completo", "I miei impegni"])
        with tab_all:
            render_planning_grid(planning_rows(data, PLANNING_DAYS, ""), "Planning completo", PLANNING_DAYS, True)
        with tab_mine:
            render_planning_grid(planning_rows(data, PLANNING_DAYS, instructor), f"Prossimi impegni {instructor}", PLANNING_DAYS, False)

