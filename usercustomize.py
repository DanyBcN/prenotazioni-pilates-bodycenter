from pathlib import Path
import re


def _rf(src, name, repl):
    m = re.search(rf"(^|\n)def {name}\([^\n]*\):\n.*?(?=\n\ndef |\n\n# -----------------------------|\Z)", src, re.S)
    if not m:
        return src
    return src[:m.start()] + ("\n" if m.group(1) else "") + repl.rstrip() + src[m.end():]


def _patch_app_simple_cash():
    p = Path(__file__).with_name("app.py")
    if not p.exists():
        return
    s = p.read_text(encoding="utf-8")

    s = _rf(s, "go", '''def go(section):
    st.session_state["_next_section"] = section
    st.rerun()''')

    s = _rf(s, "run", '''def run():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    header()
    if not login():
        return
    data, sha = load_data()
    data = ensure_data(data)
    allowed = sections()
    next_section = st.session_state.pop("_next_section", None)
    if next_section in allowed:
        st.session_state["section"] = next_section
    if "section" not in st.session_state or st.session_state["section"] not in allowed:
        st.session_state["section"] = "Planning"
    section = st.radio("Sezione", allowed, horizontal=True, key="section", label_visibility="collapsed")
    col_access, col_logout = st.columns([4, 1])
    with col_access:
        st.caption(f"Accesso: {current_user().capitalize()} · {'Admin' if is_admin() else 'Istruttrice'}")
    with col_logout:
        if st.button("Logout", key="logout_user_button", use_container_width=True):
            for k in ["authenticated", "current_user", "current_role", "section", "_next_section"]:
                st.session_state.pop(k, None)
            st.rerun()
    st.divider()
    dispatch = {"Planning": render_planning, "Prenota": render_booking, "Incassi": render_incassi, "Clienti": render_clients, "Cerca": lambda d, s: render_search(d), "Archivio": render_archive}
    dispatch[section](data, sha)''')

    s = _rf(s, "render_incassi", '''def render_incassi(data, sha):
    instr = None if is_admin() else current_instructor()
    rows = open_rows(data, instr)
    all_rows = sorted(rows, key=lambda x: (str(x.get("date", "")), str(x.get("time", "")), str(x.get("name", ""))))
    pay_rows = [b for b in rows if not is_gift(b)]
    gift_rows = [b for b in rows if is_gift(b)]
    unpaid = sorted([b for b in pay_rows if not as_bool(b.get("paid", False))], key=lambda x: (str(x.get("date", "")), str(x.get("time", "")), str(x.get("name", ""))))
    paid = sorted([b for b in pay_rows if as_bool(b.get("paid", False))], key=lambda x: (str(x.get("date", "")), str(x.get("time", "")), str(x.get("name", ""))))
    totale = sum(money(b.get("amount", 0)) for b in pay_rows)
    da_incassare = sum(money(b.get("amount", 0)) for b in unpaid)
    incassato = sum(money(b.get("amount", 0)) for b in paid)
    quota_aperta = incassato * instructor_share()
    quota_chiusa = sum(money(x.get("instructor_amount", 0)) for x in data.get("settlements", []) if not instr or x.get("instructor") == instr)

    st.subheader("Incassi")
    a, b, c, d, e = st.columns(5)
    a.metric("Totale aperto", f"€ {totale:.2f}")
    b.metric("Da incassare", f"€ {da_incassare:.2f}")
    c.metric("Incassato palestra", f"€ {incassato:.2f}")
    d.metric("Tuo 40% da ricevere" if not is_admin() else "40% da dare", f"€ {quota_aperta:.2f}")
    e.metric("Omaggio", len(gift_rows))
    if not is_admin():
        st.info(f"Quota {current_instructor()}: da ricevere € {quota_aperta:.2f} · già ricevuto € {quota_chiusa:.2f}")
    else:
        st.info(f"Quote istruttrici: da dare € {quota_aperta:.2f} · già pagate € {quota_chiusa:.2f}")

    st.markdown("### Azione unica")
    with st.container(border=True):
        st.caption("Scegli la prenotazione e correggi tutto da qui: importo, pagamento oppure omaggio.")
        if all_rows:
            idx = st.selectbox("Prenotazione", range(len(all_rows)), format_func=lambda i: row_label(all_rows[i]), key="cash_main_select")
            selected = all_rows[idx]
            current_gift = is_gift(selected)
            c1, c2, c3 = st.columns([1, 1, 1])
            gift_now = c1.checkbox("Seduta omaggio / prova", value=current_gift, key="cash_main_gift")
            amount_value = 0.0 if gift_now else float(money(selected.get("amount", 0)))
            new_amount = c2.number_input("Importo totale (€)", min_value=0.0, value=amount_value, step=1.0, format="%.2f", disabled=gift_now, key="cash_main_amount")
            mark_now = c3.checkbox("Incassato palestra", value=True if gift_now else as_bool(selected.get("paid", False)), disabled=gift_now, key="cash_main_paid")
            note = st.text_input("Nota opzionale", placeholder="es. pacchetto 5 sedute / prova gratuita", key="cash_main_note")
            if st.button("Salva", type="primary", key="cash_main_save", use_container_width=is_mobile()):
                if selected.get("settlement_id"):
                    st.error("Quota già chiusa: non posso modificare questa prenotazione.")
                    return
                if gift_now:
                    selected["gift"] = True
                    selected["amount"] = 0.0
                    selected["paid"] = True
                    selected["paid_to_gym_at"] = ""
                    selected["paid_to_gym_by"] = current_user()
                    selected["amount_updated_at"] = datetime.now().isoformat(timespec="seconds")
                    selected["amount_updated_by"] = current_user()
                    log = "Segnata come seduta omaggio / prova gratuita"
                    if note.strip():
                        log += f" - {note.strip()}"
                    if "omaggio" not in str(selected.get("note", "")).lower():
                        selected["note"] = (selected.get("note", "") + " | " if selected.get("note") else "") + log
                    save_data(data, sha, "Mark gift session")
                    st.success("Salvato come seduta omaggio.")
                    go("Incassi")
                else:
                    selected["gift"] = False
                    ok, msg = update_amount(data, selected.get("id"), new_amount, note)
                    if ok and mark_now and not as_bool(selected.get("paid", False)):
                        ok, msg = mark_paid(data, selected.get("id"))
                    if ok:
                        save_data(data, sha, "Save amount and payment")
                        st.success("Salvato.")
                        go("Incassi")
                    else:
                        st.error(msg)
        else:
            st.info("Nessuna prenotazione modificabile.")

    st.markdown("### Quota 40%")
    with st.container(border=True):
        st.metric("Tuo 40% da ricevere" if not is_admin() else "40% da dare alle istruttrici", f"€ {quota_aperta:.2f}")
        if paid:
            qidx = st.selectbox("Prenotazione", range(len(paid)), format_func=lambda i: row_label(paid[i]) + f" · quota € {money(paid[i].get('amount',0))*instructor_share():.2f}", key="share_main_select")
            button_label = "Segna quota 40% pagata ad Alice/Grazia" if is_admin() else "Segna quota 40% ricevuta"
            if st.button(button_label, key="share_main_save", use_container_width=is_mobile()):
                ok, msg = mark_share(data, paid[qidx].get("id"))
                if ok:
                    save_data(data, sha, "Close instructor share")
                    st.success(msg)
                    go("Incassi")
                else:
                    st.error(msg)
        else:
            st.info("Nessuna quota da chiudere: prima registra un incasso.")

    st.markdown("### Elenchi")
    with st.expander("Da incassare", expanded=True):
        st.dataframe(table_df(unpaid), use_container_width=True, hide_index=True) if unpaid else st.success("Nessun importo da incassare.")
    with st.expander("Incassati dalla palestra", expanded=True):
        st.dataframe(table_df(paid), use_container_width=True, hide_index=True) if paid else st.info("Nessun incasso registrato.")
    with st.expander("Sedute omaggio", expanded=True):
        st.dataframe(table_df(gift_rows), use_container_width=True, hide_index=True) if gift_rows else st.info("Nessuna seduta omaggio.")
    hist = []
    for x in data.get("settlements", []):
        if instr and x.get("instructor") != instr:
            continue
        hist.append({"Data": x.get("created_at", ""), "Istruttrice": x.get("instructor", ""), "Quota 40%": money(x.get("instructor_amount", 0)), "Quota BodyCenter 60%": money(x.get("gym_amount", 0)), "Lezioni": int(x.get("lessons", 0) or 0)})
    with st.expander("Storico quote già chiuse", expanded=True):
        st.dataframe(pd.DataFrame(hist), use_container_width=True, hide_index=True) if hist else st.info("Nessuna quota chiusa.")''')

    s = _rf(s, "render_clients", '''def render_clients(data, sha):
    st.subheader("Clienti")
    with st.expander("Aggiungi cliente", expanded=False):
        a, b = st.columns(2)
        last = a.text_input("Cognome", key="client_add_last")
        first = b.text_input("Nome", key="client_add_first")
        c, d = st.columns(2)
        phone = c.text_input("Telefono", key="client_add_phone")
        email = d.text_input("Email", key="client_add_email")
        birth = st.text_input("Data di nascita", placeholder="gg-mm-aaaa", key="client_add_birth")
        notes = st.text_area("Note", key="client_add_notes")
        if st.button("Salva cliente", type="primary"):
            ok, msg, _ = add_client(data, first, last, phone, email, notes, birth)
            if ok:
                save_data(data, sha, "Add client")
                go("Clienti")
            else:
                st.error(msg)

    df = pd.DataFrame([{"ID": c.get("id"), "Cognome": c.get("last_name", ""), "Nome": c.get("first_name", ""), "Telefono": c.get("phone", ""), "Email": c.get("email", ""), "Note": c.get("notes", "")} for c in data.get("clients", [])])
    if not df.empty:
        st.dataframe(df.drop(columns=["ID"], errors="ignore").sort_values(["Cognome", "Nome"]), use_container_width=True, hide_index=True)
    else:
        st.info("Nessun cliente.")

    opts = client_options(data)
    if opts:
        st.markdown("### Modifica scheda cliente")
        cid_map = {option_to_client_id(o): o for o in opts}
        selected_cid = st.session_state.get("edit_client_cid")
        if selected_cid not in cid_map:
            selected_cid = option_to_client_id(opts[0])
        selected_index = list(cid_map.keys()).index(selected_cid) if selected_cid in cid_map else 0
        choice = st.selectbox("Cliente da modificare", opts, index=selected_index, key="edit_client_select_fixed")
        cid = option_to_client_id(choice)
        if st.session_state.get("edit_client_cid") != cid:
            st.session_state["edit_client_cid"] = cid
            st.rerun()
        c = get_client(data, cid)
        if not c:
            st.error("Cliente non trovato.")
            return
        a, b = st.columns(2)
        last = a.text_input("Cognome", value=c.get("last_name", ""), key=f"edit_last_{cid}")
        first = b.text_input("Nome", value=c.get("first_name", ""), key=f"edit_first_{cid}")
        x, y = st.columns(2)
        phone = x.text_input("Telefono", value=c.get("phone", ""), key=f"edit_phone_{cid}")
        email = y.text_input("Email", value=c.get("email", ""), key=f"edit_email_{cid}")
        birth = st.text_input("Data di nascita", value=c.get("birth_date", ""), key=f"edit_birth_{cid}")
        notes = st.text_area("Note", value=c.get("notes", ""), key=f"edit_notes_{cid}")
        if st.button("Salva scheda cliente", key=f"save_client_edit_{cid}"):
            ok, msg = update_client(data, cid, first, last, phone, email, birth, notes)
            if ok:
                st.session_state["edit_client_cid"] = cid
                save_data(data, sha, "Update client")
                st.success("Scheda cliente aggiornata.")
                go("Clienti")
            else:
                st.error(msg)''')

    p.write_text(s, encoding="utf-8")


try:
    _patch_app_simple_cash()
except Exception:
    pass
