import pandas as pd
import streamlit as st

from auth import current_instructor, is_admin, navigate
from components.ui import render_booking_cards, render_table_expander
from config import instructor_share, is_gift, money, yes
from storage import (
    booking_dataframe, mark_gift, mark_paid, mark_share, open_rows, row_label, save_data,
    unmark_gift, update_amount,
)

def render_cash(data, sha):
    instructor = "" if is_admin() else current_instructor()
    rows = open_rows(data, instructor)
    pay_rows = [b for b in rows if not is_gift(b)]
    gift_rows = [b for b in rows if is_gift(b)]
    unpaid = [b for b in pay_rows if not yes(b.get("paid"))]
    paid = [b for b in pay_rows if yes(b.get("paid"))]

    collected = sum(money(b.get("amount")) for b in paid)
    total_open = sum(money(b.get("amount")) for b in pay_rows)
    to_collect = sum(money(b.get("amount")) for b in unpaid)
    quota_open = collected * instructor_share()
    quota_closed = sum(money(s.get("instructor_amount")) for s in data.get("settlements", []) if not instructor or s.get("instructor") == instructor)

    st.subheader("Incassi")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Totale aperto", f"â‚¬ {total_open:.2f}")
    m2.metric("Da incassare", f"â‚¬ {to_collect:.2f}")
    m3.metric("Incassato palestra", f"â‚¬ {collected:.2f}")
    m4.metric("40% da dare" if is_admin() else "Tuo 40% da ricevere", f"â‚¬ {quota_open:.2f}")
    m5.metric("Omaggio", len(gift_rows))
    if is_admin():
        st.info(f"Quote istruttrici: da dare â‚¬ {quota_open:.2f} Â· giÃ  pagate â‚¬ {quota_closed:.2f}")
    else:
        st.info(f"Quota {current_instructor()}: da ricevere â‚¬ {quota_open:.2f} Â· giÃ  ricevuto â‚¬ {quota_closed:.2f}")

    st.markdown("### Azione unica")
    all_rows = sorted(rows, key=lambda b: (b.get("date", ""), b.get("time", ""), b.get("name", "")))
    with st.container(border=True):
        if not all_rows:
            st.info("Nessuna prenotazione modificabile.")
        else:
            idx = st.selectbox("Prenotazione", range(len(all_rows)), format_func=lambda i: row_label(all_rows[i]))
            selected = all_rows[idx]
            booking_id = selected.get("id")
            was_gift = is_gift(selected)
            c1, c2, c3 = st.columns(3)
            gift_now = c1.checkbox("Seduta omaggio / prova", value=was_gift, key=f"gift_{booking_id}")
            new_amount = c2.number_input("Importo totale (â‚¬)", min_value=0.0, value=0.0 if gift_now else float(money(selected.get("amount"))), step=1.0, format="%.2f", disabled=gift_now, key=f"amount_{booking_id}")
            paid_now = c3.checkbox("Incassato palestra", value=True if gift_now else yes(selected.get("paid")), disabled=gift_now, key=f"paid_{booking_id}")
            note = st.text_input("Nota opzionale", key=f"note_{booking_id}")
            if st.button("Salva", type="primary", key=f"save_cash_{booking_id}"):
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

    st.markdown("### Quota 40%")
    payable = [b for b in paid if not b.get("settlement_id") and not is_gift(b)]
    with st.container(border=True):
        if not payable:
            st.info("Nessuna quota da chiudere.")
        else:
            q_idx = st.selectbox("Prenotazione quota", range(len(payable)), format_func=lambda i: row_label(payable[i]) + f" Â· quota â‚¬ {money(payable[i].get('amount')) * instructor_share():.2f}")
            label = "Segna quota 40% pagata ad Alice/Grazia" if is_admin() else "Segna quota 40% ricevuta"
            if st.button(label, type="primary"):
                ok, msg = mark_share(data, payable[q_idx].get("id"))
                if ok:
                    save_data(data, sha, "Close instructor share")
                    navigate("Incassi")
                else:
                    st.error(msg)

    history = []
    for s in data.get("settlements", []):
        if instructor and s.get("instructor") != instructor:
            continue
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

    st.markdown("### Elenchi incassi")
    tab_unpaid, tab_paid, tab_gifts, tab_history = st.tabs(["Da incassare", "Incassati", "Omaggi", "Quote chiuse"])
    with tab_unpaid:
        render_booking_cards(unpaid, "Nessun importo da incassare.")
        render_table_expander("Tabella da incassare", booking_dataframe(unpaid), "Nessun importo da incassare.")
    with tab_paid:
        render_booking_cards(paid, "Nessun incasso registrato.")
        render_table_expander("Tabella incassati", booking_dataframe(paid), "Nessun incasso registrato.")
    with tab_gifts:
        render_booking_cards(gift_rows, "Nessuna seduta omaggio.")
        render_table_expander("Tabella omaggi", booking_dataframe(gift_rows), "Nessuna seduta omaggio.")
    with tab_history:
        history_df = pd.DataFrame(history)
        if history:
            st.markdown(
                "<div class='bc-card-list'>"
                + "".join(
                    f"<div class='bc-booking-card'><div class='bc-card-title'>{row['Istruttrice']}</div>"
                    f"<div class='bc-card-meta'>{row['Data']}</div>"
                    f"<div class='bc-card-meta'>Lordo EUR {row['Lordo']:.2f} · Quota 40% EUR {row['Quota 40%']:.2f}</div>"
                    f"<div class='bc-card-meta'>Body Center 60% EUR {row['Body Center 60%']:.2f} · {row['Chiusa da']}</div></div>"
                    for row in history
                )
                + "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.info("Nessuna quota chiusa.")
        render_table_expander("Tabella quote chiuse", history_df, "Nessuna quota chiusa.")


