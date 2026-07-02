from datetime import date, timedelta
from html import escape

import streamlit as st

from auth import current_instructor, is_admin, navigate
from components.ui import page_header, render_booking_cards, render_downloads, render_table_expander
from config import CAPACITY, INSTRUCTORS, PLANNING_DAYS, date_label, is_gift, money, parse_date, yes
from storage import booking_dataframe, cancel_booking, open_rows, planning_rows, row_label, save_data


def action_tile(label: str, note: str, target: str, primary: bool = False):
    if st.button(label, type="primary" if primary else "secondary", use_container_width=True):
        navigate(target)
    st.caption(note)


def render_quick_actions():
    st.markdown("<div class='bc-section-title'>Azioni rapide</div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        action_tile("Nuova prenotazione", "Aggiungi subito una lezione", "Prenota", True)
    with c2:
        action_tile("Incassi", "Pagamenti e quote 40%", "Incassi")
    with c3:
        action_tile("Clienti", "Archivio e schede", "Clienti")
    with c4:
        if is_admin():
            action_tile("Archivio", "Storico completo", "Archivio")
        else:
            st.button("Archivio", use_container_width=True, disabled=True)
            st.caption("Solo admin")


def render_dashboard(data: dict, instructor: str = ""):
    today_key = date.today().isoformat()
    rows = [b for b in data.get("bookings", []) if b.get("status") != "Annullata" and (not instructor or b.get("instructor") == instructor)]
    today_rows = [b for b in rows if b.get("date") == today_key]
    upcoming = planning_rows(data, PLANNING_DAYS, instructor)
    unpaid = [b for b in open_rows(data, instructor) if not is_gift(b) and not yes(b.get("paid"))]
    paid_open_share = [b for b in open_rows(data, instructor) if not is_gift(b) and yes(b.get("paid")) and not b.get("settlement_id")]
    gifts = [b for b in upcoming if is_gift(b)]

    st.markdown(
        f"""
        <div class="quick-grid">
          <div class="quick-card"><div class="quick-label">Oggi</div><div class="quick-value">{len(today_rows)}</div><div class="quick-note">prenotazioni attive</div></div>
          <div class="quick-card"><div class="quick-label">Prossimi {PLANNING_DAYS} giorni</div><div class="quick-value">{len(upcoming)}</div><div class="quick-note">in agenda</div></div>
          <div class="quick-card bc-attention"><div class="quick-label">Da incassare</div><div class="quick-value">EUR {sum(money(b.get('amount')) for b in unpaid):.2f}</div><div class="quick-note">{len(unpaid)} movimenti aperti</div></div>
          <div class="quick-card"><div class="quick-label">Quote 40%</div><div class="quick-value">{len(paid_open_share)}</div><div class="quick-note">da chiudere - {len(gifts)} omaggi</div></div>
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

    with st.expander("Gestione prenotazione", expanded=False):
        if not future:
            st.info("Nessuna prenotazione futura annullabile.")
            return
        idx = st.selectbox("Prenotazione", range(len(future)), format_func=lambda i: row_label(future[i]))
        note = st.text_input("Motivo / nota opzionale")
        confirm = st.checkbox("Confermo l'operazione")
        if st.button("Annulla prenotazione selezionata"):
            if not confirm:
                st.warning("Spunta la conferma prima di procedere.")
                return
            ok, msg = cancel_booking(data, future[idx].get("id"), note)
            if ok:
                save_data(data, sha, "Cancel booking")
                navigate("Planning")
            else:
                st.error(msg)


def day_class(groups: dict) -> str:
    if not groups:
        return "day-card day-empty"
    confirmed = sum(len([r for r in group if r.get("status") == "Confermata"]) for group in groups.values())
    capacity_total = max(len(groups), 1) * CAPACITY
    if confirmed >= capacity_total:
        return "day-card day-full"
    if confirmed >= capacity_total * 0.7:
        return "day-card day-busy"
    return "day-card day-open"


def render_planning_grid(rows: list, title: str, days: int = PLANNING_DAYS, show_instructor: bool = True):
    st.markdown(f"<div class='bc-section-title'>{escape(title)}</div>", unsafe_allow_html=True)
    today = date.today()
    all_days = [(today + timedelta(days=i)).isoformat() for i in range(days)]
    by_day = {d: [] for d in all_days}
    for row in rows:
        by_day.setdefault(row.get("date", ""), []).append(row)

    c1, c2, c3 = st.columns(3)
    c1.metric("Oggi", len([r for r in rows if r.get("date") == today.isoformat()]))
    c2.metric(f"Prossimi {days} giorni", len(rows))
    c3.metric("Omaggi", len([r for r in rows if is_gift(r)]))

    cards = []
    for day_key in all_days:
        grouped = {}
        for row in by_day.get(day_key, []):
            grouped.setdefault((row.get("time", ""), row.get("instructor", "")), []).append(row)

        lines = []
        day_confirmed = 0
        day_waiting = 0
        day_gifts = 0
        for (time, instructor), group in sorted(grouped.items(), key=lambda item: item[0]):
            confirmed_rows = [r for r in group if r.get("status") == "Confermata"]
            waiting_rows = [r for r in group if r.get("status") == "Lista attesa"]
            gift_count = len([r for r in group if is_gift(r)])
            day_confirmed += len(confirmed_rows)
            day_waiting += len(waiting_rows)
            day_gifts += gift_count
            free_spots = max(CAPACITY - len(confirmed_rows), 0)
            names = ", ".join([escape(r.get("name", "")) + (" (omaggio)" if is_gift(r) else "") for r in confirmed_rows]) or "posti disponibili"
            instructor_html = f" <span class='muted'>{escape(instructor)}</span>" if show_instructor and instructor else ""
            waiting = f"<span class='pill pill-warn'>attesa {len(waiting_rows)}</span>" if waiting_rows else ""
            gift = f"<span class='pill pill-gift'>{gift_count} omaggio</span>" if gift_count else ""
            free = f"<span class='pill pill-free'>{free_spots} liberi</span>"
            status = "<span class='pill pill-ok'>pieno</span>" if free_spots == 0 else free
            lines.append(
                f"<div class='slot'><span class='slot-time'>{escape(time)}</span>{instructor_html} "
                f"<span class='muted'>{len(confirmed_rows)}/{CAPACITY}</span> {status}{waiting}{gift}<br>"
                f"<small>{names}</small></div>"
            )
        body = "".join(lines) if lines else "<div class='muted'>Nessuna prenotazione</div>"
        cls = day_class(grouped)
        badge = f"{day_confirmed} pren."
        if day_waiting:
            badge += f" / {day_waiting} att."
        if day_gifts:
            badge += f" / {day_gifts} om."
        cards.append(f"<div class='{cls}'><div class='day-title'><span>{escape(date_label(day_key))}</span><span class='day-count'>{escape(badge)}</span></div>{body}</div>")

    st.markdown("<div class='day-grid'>" + "".join(cards) + "</div>", unsafe_allow_html=True)

    df = booking_dataframe(rows)
    with st.expander("Elenco rapido", expanded=False):
        render_booking_cards(rows, "Nessuna prenotazione nel periodo.")
        render_table_expander("Tabella completa", df, "Nessuna prenotazione nel periodo.")


def render_planning(data, sha):
    page_header("Planning 3 mesi", "Agenda colorata dei prossimi 92 giorni: verde per disponibilita, giallo per quasi pieno, rosso per pieno.", "Agenda")
    pdf_scope = "" if is_admin() else current_instructor()
    render_dashboard(data, pdf_scope)
    render_quick_actions()

    pdf_rows = planning_rows(data, PLANNING_DAYS, pdf_scope)
    df = booking_dataframe(pdf_rows)
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
