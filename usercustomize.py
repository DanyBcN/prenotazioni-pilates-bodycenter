from pathlib import Path
import re


def _rf(src, name, replacement):
    m = re.search(rf"(^|\n)def {name}\([^\n]*\):\n.*?(?=\n\ndef |\n\n# -----------------------------|\Z)", src, flags=re.S)
    if not m:
        return src
    return src[:m.start()] + ("\n" if m.group(1) else "") + replacement.rstrip() + src[m.end():]


def _patch_payments_and_planning():
    p = Path(__file__).with_name("app.py")
    if not p.exists():
        return
    s = p.read_text(encoding="utf-8")

    helpers = '''

def _payment_label(b):
    return f"{date_it(b.get('date'))} · {b.get('time','')} · {b.get('instructor','')} · {b.get('name','')}"


def mark_paid_to_gym(data, booking_id):
    for b in data.get("bookings", []):
        if b.get("id") == booking_id:
            if b.get("status") == "Annullata":
                return False, "Prenotazione annullata."
            b["paid"] = True
            b["paid_to_gym_at"] = datetime.now().isoformat(timespec="seconds")
            b["paid_to_gym_by"] = current_user()
            return True, "Incasso cliente registrato."
    return False, "Prenotazione non trovata."


def mark_cash_delivered_to_gym(data, booking_id):
    for b in data.get("bookings", []):
        if b.get("id") == booking_id:
            if b.get("status") == "Annullata":
                return False, "Prenotazione annullata."
            if not to_bool(b.get("paid", False)):
                return False, "Prima va segnato l'incasso del cliente."
            if b.get("gym_delivered_at"):
                return False, "Incasso già segnato come consegnato alla palestra."
            b["gym_delivered_at"] = datetime.now().isoformat(timespec="seconds")
            b["gym_delivered_by"] = current_user()
            return True, "Incasso consegnato alla palestra segnato."
    return False, "Prenotazione non trovata."


def mark_instructor_share_paid(data, booking_id):
    for b in data.get("bookings", []):
        if b.get("id") == booking_id:
            if b.get("status") == "Annullata":
                return False, "Prenotazione annullata."
            if not to_bool(b.get("paid", False)):
                return False, "Prima va segnato l'incasso del cliente."
            if not b.get("gym_delivered_at"):
                return False, "Prima va segnato che l'incasso è stato consegnato alla palestra."
            if b.get("settlement_id"):
                return False, "Quota istruttrice già segnata come ricevuta."
            sid = new_id("sett_")
            amount = money(b.get("amount", 0))
            instr = b.get("instructor", "")
            b["settlement_id"] = sid
            b["share_paid_at"] = datetime.now().isoformat(timespec="seconds")
            b["share_paid_by"] = current_user()
            data.setdefault("settlements", []).append({
                "id": sid,
                "created_at": b["share_paid_at"],
                "instructor": instr,
                "gross_amount": round(amount, 2),
                "instructor_amount": round(amount * instructor_share(), 2),
                "gym_amount": round(amount * gym_share(), 2),
                "lessons": 1,
                "closed_by": current_user(),
                "mode": "quota_istruttrice_ricevuta",
                "booking_id": booking_id,
            })
            return True, "Quota istruttrice segnata come ricevuta."
    return False, "Prenotazione non trovata."


def settled_share_total(data, instructor=None):
    total = 0.0
    for x in data.get("settlements", []):
        if instructor and x.get("instructor") != instructor:
            continue
        total += money(x.get("instructor_amount", 0))
    return total


def render_payment_tracking_box(data, sha):
    with st.expander("Incassi / consegna palestra / quota istruttrice", expanded=False):
        st.caption("Sequenza corretta: 1) l'istruttrice incassa dal cliente; 2) consegna l'incasso alla palestra; 3) quando riceve il 40%, segna la quota ricevuta.")

        instr_user = instructor_name_from_user()
        active_all = [b for b in data.get("bookings", []) if b.get("status") != "Annullata" and not b.get("settlement_id")]
        active = active_all if is_admin() else [b for b in active_all if b.get("instructor") == instr_user]

        not_collected = sorted([b for b in active if not to_bool(b.get("paid", False))], key=lambda x: (str(x.get("date", "")), str(x.get("time", "")), str(x.get("instructor", "")), str(x.get("name", ""))))
        if not_collected:
            st.markdown("**1. Segna incasso ricevuto dal cliente**")
            idx = st.selectbox("Prenotazione incassata", list(range(len(not_collected))), format_func=lambda i: _payment_label(not_collected[i]), key="paid_to_gym_select")
            if st.button("Segna incasso cliente", key="paid_to_gym_btn", use_container_width=is_mobile_client()):
                ok, msg = mark_paid_to_gym(data, not_collected[idx].get("id"))
                if ok:
                    save_data(data, sha, "Mark client cash collected")
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.info("Nessun incasso cliente da segnare.")

        to_deliver = sorted([b for b in active if to_bool(b.get("paid", False)) and not b.get("gym_delivered_at")], key=lambda x: (str(x.get("date", "")), str(x.get("time", "")), str(x.get("instructor", "")), str(x.get("name", ""))))
        if to_deliver:
            st.markdown("**2. Segna incasso consegnato alla palestra**")
            idxd = st.selectbox("Incasso da consegnare", list(range(len(to_deliver))), format_func=lambda i: _payment_label(to_deliver[i]) + f" · € {money(to_deliver[i].get('amount',0)):.2f}", key="cash_delivered_select")
            if st.button("Segna incasso consegnato a BodyCenter", key="cash_delivered_btn", use_container_width=is_mobile_client()):
                ok, msg = mark_cash_delivered_to_gym(data, to_deliver[idxd].get("id"))
                if ok:
                    save_data(data, sha, "Mark cash delivered to gym")
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.info("Nessun incasso da consegnare alla palestra.")

        share_rows = sorted([b for b in active if to_bool(b.get("paid", False)) and b.get("gym_delivered_at")], key=lambda x: (str(x.get("date", "")), str(x.get("time", "")), str(x.get("instructor", "")), str(x.get("name", ""))))
        if share_rows:
            st.markdown("**3. Segna quota istruttrice ricevuta dalla palestra**")
            idx2 = st.selectbox("Quota ricevuta", list(range(len(share_rows))), format_func=lambda i: _payment_label(share_rows[i]) + f" · quota € {money(share_rows[i].get('amount',0))*instructor_share():.2f}", key="share_paid_select")
            if st.button("Segna quota istruttrice ricevuta", key="share_paid_btn", use_container_width=is_mobile_client()):
                ok, msg = mark_instructor_share_paid(data, share_rows[idx2].get("id"))
                if ok:
                    save_data(data, sha, "Mark instructor share paid")
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.info("Nessuna quota istruttrice da segnare come ricevuta.")
'''
    if "def mark_cash_delivered_to_gym(" not in s:
        anchor = "\ndef render_settlements("
        if anchor in s:
            s = s.replace(anchor, helpers + anchor, 1)

    s = _rf(s, "create_booking", '''def create_booking(data, cid, d, t, amount, paid, instructor, note):
    c = get_client(data, cid)
    if not c:
        raise ValueError("Cliente non trovato.")
    b = {
        "id": new_id("b_"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "client_id": cid,
        "date": date_key(d),
        "day": DAY_NAMES[d.weekday()],
        "time": t,
        "name": full_name(c),
        "phone": c.get("phone", ""),
        "email": c.get("email", ""),
        "note": note.strip(),
        "status": auto_status(data, d, t, instructor),
        "amount": money(amount),
        "paid": bool(paid),
        "paid_to_gym_at": datetime.now().isoformat(timespec="seconds") if paid else "",
        "paid_to_gym_by": current_user() if paid else "",
        "gym_delivered_at": "",
        "gym_delivered_by": "",
        "settlement_id": "",
        "instructor": instructor,
        "created_by": current_user(),
    }
    data["bookings"].append(b)
    return b''')

    s = _rf(s, "render_settlements", '''def render_settlements(data, sha):
    st.subheader("Incassi e liquidazioni")
    rows = [b for b in data.get("bookings", []) if b.get("status") != "Annullata"]

    if is_admin():
        st.markdown("### Riepilogo BodyCenter")
        open_rows = [b for b in rows if not b.get("settlement_id")]
        total_collected = sum(money(b.get("amount", 0)) for b in open_rows if to_bool(b.get("paid", False)))
        total_to_deliver = sum(money(b.get("amount", 0)) for b in open_rows if to_bool(b.get("paid", False)) and not b.get("gym_delivered_at"))
        total_delivered = sum(money(b.get("amount", 0)) for b in open_rows if to_bool(b.get("paid", False)) and b.get("gym_delivered_at"))
        total_due_instr = sum(money(b.get("amount", 0)) * instructor_share() for b in open_rows if to_bool(b.get("paid", False)) and b.get("gym_delivered_at"))
        a, b, c, d = st.columns(4)
        a.metric("Incassato da Alice/Grazia", f"€ {total_collected:.2f}")
        b.metric("Da consegnare a BodyCenter", f"€ {total_to_deliver:.2f}")
        c.metric("Consegnato a BodyCenter", f"€ {total_delivered:.2f}")
        d.metric("Da dare alle istruttrici", f"€ {total_due_instr:.2f}")
        table = []
        for instr in INSTRUCTORS:
            r = [x for x in open_rows if x.get("instructor") == instr]
            collected = sum(money(x.get("amount", 0)) for x in r if to_bool(x.get("paid", False)))
            to_deliver = sum(money(x.get("amount", 0)) for x in r if to_bool(x.get("paid", False)) and not x.get("gym_delivered_at"))
            delivered = sum(money(x.get("amount", 0)) for x in r if to_bool(x.get("paid", False)) and x.get("gym_delivered_at"))
            due = delivered * instructor_share()
            already = settled_share_total(data, instr)
            table.append({"Istruttrice": instr, "Incassato da": instr, "Totale incassato": collected, "Da consegnare a BodyCenter": to_deliver, "Consegnato a BodyCenter": delivered, "Quota da dare 40%": due, "Quota già data": already, "Quota BodyCenter 60%": delivered * gym_share()})
        st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)
        render_payment_tracking_box(data, sha)
        return

    instr = instructor_name_from_user()
    my = [b for b in rows if b.get("instructor") == instr and not b.get("settlement_id")]
    collected = sum(money(b.get("amount", 0)) for b in my if to_bool(b.get("paid", False)))
    to_deliver = sum(money(b.get("amount", 0)) for b in my if to_bool(b.get("paid", False)) and not b.get("gym_delivered_at"))
    delivered = sum(money(b.get("amount", 0)) for b in my if to_bool(b.get("paid", False)) and b.get("gym_delivered_at"))
    due = delivered * instructor_share()
    already = settled_share_total(data, instr)
    a, b, c, d = st.columns(4)
    a.metric("Incassato da te", f"€ {collected:.2f}")
    b.metric("Da consegnare a palestra", f"€ {to_deliver:.2f}")
    c.metric("Consegnato a palestra", f"€ {delivered:.2f}")
    d.metric("Da ricevere 40%", f"€ {due:.2f}")
    st.caption(f"Quota già ricevuta: € {already:.2f}")
    if my:
        df = pd.DataFrame([{
            "Data": date_it(x.get("date")),
            "Ora": x.get("time", ""),
            "Cliente": x.get("name", ""),
            "Incassato": "Sì" if to_bool(x.get("paid", False)) else "No",
            "Consegnato palestra": "Sì" if x.get("gym_delivered_at") else "No",
            "Quota 40%": round(money(x.get("amount", 0)) * instructor_share(), 2),
            "Quota BodyCenter 60%": round(money(x.get("amount", 0)) * gym_share(), 2),
            "Stato quota": "Da ricevere" if to_bool(x.get("paid", False)) and x.get("gym_delivered_at") else ("Da consegnare alla palestra" if to_bool(x.get("paid", False)) else "Da incassare"),
        } for x in my])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Nessuna quota aperta.")

    hist = []
    for x in data.get("settlements", []):
        if x.get("instructor") == instr:
            hist.append({"Data": x.get("created_at", ""), "Quota ricevuta": money(x.get("instructor_amount", 0)), "Quota BodyCenter 60%": money(x.get("gym_amount", 0)), "Lezioni": int(x.get("lessons", 0) or 0)})
    if hist:
        st.markdown("### Storico quote ricevute")
        st.dataframe(pd.DataFrame(hist), use_container_width=True, hide_index=True)''')

    s = _rf(s, "render_planning", '''def render_planning(data, sha=None):
    st.subheader("Planning 14 giorni")
    render_cancel_booking_box(data, sha)
    render_payment_tracking_box(data, sha)
    giorni = 14
    if is_admin():
        vista = st.selectbox("Vista", ["Tutte", *INSTRUCTORS], key="planning_admin_view")
        instr = None if vista == "Tutte" else vista
        _render_planning_view(data, _planning_base_rows(data, giorni, instr), f"Planning {vista}", giorni, show_instructor=True)
        return
    instr = instructor_name_from_user()
    render_personal_planning_download(data, instr, giorni)
    tab_all, tab_miei = st.tabs(["Planning completo", "I miei impegni"])
    with tab_all:
        _render_planning_view(data, _planning_base_rows(data, giorni, None), "Planning completo", giorni, show_instructor=True)
    with tab_miei:
        _render_planning_view(data, _planning_base_rows(data, giorni, instr), f"Prossimi impegni {instr}", giorni, show_instructor=False)''')

    p.write_text(s, encoding="utf-8")


try:
    _patch_payments_and_planning()
except Exception:
    pass
