from html import escape

import pandas as pd
import streamlit as st

from auth import current_instructor, is_admin, navigate
from components.ui import page_header, render_booking_cards, render_table_expander
from config import INSTRUCTORS, instructor_share, is_gift, money, parse_date, yes
from storage import (
    booking_dataframe, mark_gift, mark_paid, mark_share, row_label, save_data,
    unmark_gift, update_amount,
)

PAYMENT_FILTERS = ["Tutti", "Da incassare", "Incassati", "Omaggi", "Quote 40% da chiudere"]


def booking_month_key(booking: dict) -> str:
    try:
        return parse_date(booking.get("date")).strftime("%Y-%m")
    except Exception:
        return ""


def settlement_month_key(settlement: dict) -> str:
    try:
        return parse_date(str(settlement.get("created_at", ""))[:10]).strftime("%Y-%m")
    except Exception:
        return ""


def month_label(month_key: str) -> str:
    if not month_key:
        return "Senza data"
    try:
        return parse_date(f"{month_key}-01").strftime("%m/%Y")
    except Exception:
        return month_key


def visible_by_payment_filter(rows: list, payment_state: str) -> list:
    if payment_state == "Da incassare":
        return [b for b in rows if not is_gift(b) and not yes(b.get("paid"))]
    if payment_state == "Incassati":
        return [b for b in rows if not is_gift(b) and yes(b.get("paid"))]
    if payment_state == "Omaggi":
        return [b for b in rows if is_gift(b)]
    if payment_state == "Quote 40% da chiudere":
        return [b for b in rows if not is_gift(b) and yes(b.get("paid")) and not b.get("settlement_id")]
    return rows


def section_card(title: str, value: str, note: str = "", emphasis: str = ""):
    cls = f"quick-card {emphasis}".strip()
    st.markdown(
        f"""
        <div class="{cls}">
          <div class="quick-label">{escape(title)}</div>
          <div class="quick-value">{escape(value)}</div>
          <div class="quick-note">{escape(note)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_admin_instructor_summary(rows: list, settlements: list):
    st.markdown("### Riepilogo istruttrici")
    cols = st.columns(len(INSTRUCTORS))
    for col, instructor in zip(cols, INSTRUCTORS):
        instructor_rows = [b for b in rows if b.get("instructor") == instructor]
        payable = [b for b in instructor_rows if not is_gift(b) and yes(b.get("paid")) and not b.get("settlement_id")]
        unpaid = [b for b in instructor_rows if not is_gift(b) and not yes(b.get("paid"))]
        closed = [s for s in settlements if s.get("instructor") == instructor]
        gross_paid = sum(money(b.get("amount")) for b in payable)
        quota_due = gross_paid * instructor_share()
        quota_closed = sum(money(s.get("instructor_amount")) for s in closed)
        with col:
            st.markdown(
                f"""
                <div class="bc-booking-card bc-cash-summary">
                  <div class="bc-card-title">{escape(instructor)}</div>
                  <div class="bc-card-meta">Da incassare: <b>EUR {sum(money(b.get('amount')) for b in unpaid):.2f}</b></div>
                  <div class="bc-card-meta">Quote 40% da dare: <b>EUR {quota_due:.2f}</b></div>
                  <div class="bc-card-meta">Quote gia chiuse: EUR {quota_closed:.2f}</div>
                  <span class="bc-card-chip">{len(payable)} quote aperte</span>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_history_cards(history: list):
    if not history:
        st.info("Nessuna quota chiusa.")
        return
    st.markdown(
        "<div class='bc-card-list'>"
        + "".join(
            f"<div class='bc-booking-card'><div class='bc-card-title'>{escape(str(row['Istruttrice']))}</div>"
            f"<div class='bc-card-meta'>{escape(str(row['Data']))}</div>"
            f"<div class='bc-card-meta'>Lordo EUR {row['Lordo']:.2f} - Quota 40% EUR {row['Quota 40%']:.2f}</div>"
            f"<div class='bc-card-meta'>Body Center 60% EUR {row['Body Center 60%']:.2f} - {escape(str(row['Chiusa da']))}</div></div>"
            for row in history
        )
        + "</div>",
        unsafe_allow_html=True,
    )


def render_cash(data, sha):
    allowed_instructor = "" if is_admin() else current_instructor()
    base_rows = [
        b for b in data.get("bookings", [])
        if b.get("status") != "Annullata" and (not allowed_instructor or b.get("instructor") == allowed_instructor)
    ]
    base_settlements = [
        s for s in data.get("settlements", [])
        if not allowed_instructor or s.get("instructor") == allowed_instructor
    ]

    month_keys = sorted(
        {booking_month_key(b) for b in base_rows if booking_month_key(b)}
        | {settlement_month_key(s) for s in base_settlements if settlement_month_key(s)},
        reverse=True,
    )
    month_options = ["Tutti", *[month_label(m) for m in month_keys]]
    month_lookup = {month_label(m): m for m in month_keys}

    page_header("Incassi", "Controlla pagamenti, omaggi e quote 40/60 con filtri operativi chiari.", "Contabilita")
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        if is_admin():
            instructor_filter = c1.selectbox("Istruttrice", ["Tutte", *INSTRUCTORS], key="cash_instructor_filter")
            selected_instructor = "" if instructor_filter == "Tutte" else instructor_filter
        else:
            selected_instructor = current_instructor()
            c1.text_input("Istruttrice", value=selected_instructor, disabled=True, key="cash_instructor_fixed")
        selected_month_label = c2.selectbox("Mese", month_options, key="cash_month_filter")
        selected_month = month_lookup.get(selected_month_label, "")
        payment_state = c3.selectbox("Stato pagamento", PAYMENT_FILTERS, key="cash_payment_filter")

    filtered_rows = [b for b in base_rows if not selected_instructor or b.get("instructor") == selected_instructor]
    if selected_month:
        filtered_rows = [b for b in filtered_rows if booking_month_key(b) == selected_month]
    visible_rows = visible_by_payment_filter(filtered_rows, payment_state)

    filtered_settlements = [s for s in base_settlements if not selected_instructor or s.get("instructor") == selected_instructor]
    if selected_month:
        filtered_settlements = [s for s in filtered_settlements if settlement_month_key(s) == selected_month]

    pay_rows = [b for b in visible_rows if not is_gift(b)]
    gift_rows = [b for b in visible_rows if is_gift(b)]
    unpaid = [b for b in pay_rows if not yes(b.get("paid"))]
    paid = [b for b in pay_rows if yes(b.get("paid"))]
    payable = [b for b in paid if not b.get("settlement_id")]
    settled_paid = [b for b in paid if b.get("settlement_id")]

    collected = sum(money(b.get("amount")) for b in paid)
    total_open = sum(money(b.get("amount")) for b in pay_rows)
    to_collect = sum(money(b.get("amount")) for b in unpaid)
    quota_open = sum(money(b.get("amount")) for b in payable) * instructor_share()
    quota_closed = sum(money(s.get("instructor_amount")) for s in filtered_settlements)
    gym_open = sum(money(b.get("amount")) for b in payable) * (1 - instructor_share())

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        section_card("Totale visibile", f"EUR {total_open:.2f}", f"{len(pay_rows)} pagamenti")
    with m2:
        section_card("Da incassare", f"EUR {to_collect:.2f}", f"{len(unpaid)} prenotazioni", "bc-attention")
    with m3:
        section_card("Incassati", f"EUR {collected:.2f}", f"{len(paid)} prenotazioni")
    with m4:
        section_card("Quote 40%", f"EUR {quota_open:.2f}", f"Body Center 60% EUR {gym_open:.2f}", "bc-attention")
    with m5:
        section_card("Omaggi", str(len(gift_rows)), "sedute senza incasso")

    if is_admin():
        render_admin_instructor_summary(filtered_rows, filtered_settlements)
    else:
        st.info(f"Quota {current_instructor()}: da ricevere EUR {quota_open:.2f} - gia ricevuto EUR {quota_closed:.2f}")

    st.markdown("### Registra o modifica incasso")
    action_rows = sorted(filtered_rows, key=lambda b: (b.get("date", ""), b.get("time", ""), b.get("name", "")))
    with st.container(border=True):
        if not action_rows:
            st.info("Nessuna prenotazione disponibile con questi filtri.")
        else:
            idx = st.selectbox("Prenotazione", range(len(action_rows)), format_func=lambda i: row_label(action_rows[i]))
            selected = action_rows[idx]
            booking_id = selected.get("id")
            was_gift = is_gift(selected)
            locked = bool(selected.get("settlement_id"))
            if locked:
                st.warning("Quota 40% gia chiusa: importo e omaggio non sono modificabili.")

            c1, c2, c3 = st.columns(3)
            gift_now = c1.checkbox("Seduta omaggio / prova", value=was_gift, key=f"gift_{booking_id}", disabled=locked)
            new_amount = c2.number_input(
                "Importo totale (EUR)",
                min_value=0.0,
                value=0.0 if gift_now else float(money(selected.get("amount"))),
                step=1.0,
                format="%.2f",
                disabled=gift_now or locked,
                key=f"amount_{booking_id}",
            )
            paid_now = c3.checkbox(
                "Incassato palestra",
                value=True if gift_now else yes(selected.get("paid")),
                disabled=gift_now or locked,
                key=f"paid_{booking_id}",
            )
            note = st.text_input("Nota opzionale", key=f"note_{booking_id}", disabled=locked)
            if st.button("Salva incasso", type="primary", key=f"save_cash_{booking_id}", disabled=locked):
                if gift_now:
                    ok, msg = mark_gift(data, booking_id, note)
                elif was_gift and not gift_now:
                    ok, msg = unmark_gift(data, booking_id, new_amount, paid_now, note)
                else:
                    ok, msg = update_amount(data, booking_id, new_amount, note)
                    if ok and paid_now and not yes(selected.get("paid")):
                        ok, msg = mark_paid(data, booking_id)
                if ok:
                    save_data(data, sha, "Save payment")
                    navigate("Incassi")
                else:
                    st.error(msg)

    st.markdown("### Quote 40% da chiudere")
    with st.container(border=True):
        if not payable:
            st.info("Nessuna quota da chiudere con questi filtri.")
        else:
            q_idx = st.selectbox(
                "Prenotazione quota",
                range(len(payable)),
                format_func=lambda i: row_label(payable[i]) + f" - quota EUR {money(payable[i].get('amount')) * instructor_share():.2f}",
            )
            label = "Segna quota 40% pagata ad Alice/Grazia" if is_admin() else "Segna quota 40% ricevuta"
            if st.button(label, type="primary"):
                ok, msg = mark_share(data, payable[q_idx].get("id"))
                if ok:
                    save_data(data, sha, "Close instructor share")
                    navigate("Incassi")
                else:
                    st.error(msg)

    history = []
    for s in filtered_settlements:
        history.append(
            {
                "Data": s.get("created_at", ""),
                "Istruttrice": s.get("instructor", ""),
                "Lordo": money(s.get("gross_amount")),
                "Quota 40%": money(s.get("instructor_amount")),
                "Body Center 60%": money(s.get("gym_amount")),
                "Chiusa da": s.get("closed_by", ""),
            }
        )

    st.markdown("### Sezioni operative")
    tab_unpaid, tab_paid, tab_gifts, tab_payable, tab_history = st.tabs(
        ["Da incassare", "Incassati", "Omaggi", "Quote 40%", "Storico quote"]
    )
    with tab_unpaid:
        st.caption(f"Totale da incassare: EUR {to_collect:.2f}")
        render_booking_cards(unpaid, "Nessun importo da incassare.")
        render_table_expander("Tabella da incassare", booking_dataframe(unpaid), "Nessun importo da incassare.")
    with tab_paid:
        st.caption(f"Incassato nel filtro: EUR {collected:.2f} - gia chiuse: {len(settled_paid)}")
        render_booking_cards(paid, "Nessun incasso registrato.")
        render_table_expander("Tabella incassati", booking_dataframe(paid), "Nessun incasso registrato.")
    with tab_gifts:
        render_booking_cards(gift_rows, "Nessuna seduta omaggio.")
        render_table_expander("Tabella omaggi", booking_dataframe(gift_rows), "Nessuna seduta omaggio.")
    with tab_payable:
        st.caption(f"Quote 40% da chiudere: EUR {quota_open:.2f}")
        render_booking_cards(payable, "Nessuna quota da chiudere.")
        render_table_expander("Tabella quote da chiudere", booking_dataframe(payable), "Nessuna quota da chiudere.")
    with tab_history:
        history_df = pd.DataFrame(history)
        st.caption(f"Quote gia chiuse: EUR {quota_closed:.2f}")
        render_history_cards(history)
        render_table_expander("Tabella storico quote", history_df, "Nessuna quota chiusa.")
