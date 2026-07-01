from pathlib import Path
import re


def _rf(src, name, repl):
    m = re.search(rf"(^|\n)def {name}\([^\n]*\):\n.*?(?=\n\ndef |\n\n# -----------------------------|\Z)", src, re.S)
    if not m:
        return src
    return src[:m.start()] + ("\n" if m.group(1) else "") + repl.rstrip() + src[m.end():]


def _patch_app():
    p = Path(__file__).with_name("app.py")
    if not p.exists():
        return
    s = p.read_text(encoding="utf-8")

    marker = 'def github_file_url():\n    return f"https://api.github.com/repos/{get_secret(\'GITHUB_REPO\')}/contents/{LOCAL_DATA_PATH}"\n'
    helpers = marker + '''
def configured_users():
    raw = get_secret("USERS", "").strip()
    if raw:
        try:
            users = json.loads(raw)
            return {str(k).lower().strip(): v for k, v in users.items() if isinstance(v, dict)}
        except Exception as e:
            st.error(f"Configurazione USERS non valida nei Secrets: {e}")
            st.stop()
    return {"bodycenter": {"password": get_secret("APP_PASSWORD", "pilates123"), "role": "admin"}}


def current_role():
    return st.session_state.get("current_role", "admin")


def current_user():
    return st.session_state.get("current_user", "bodycenter")


def is_admin():
    return current_role() == "admin"


def instructor_name_from_user():
    u = current_user().lower().strip()
    for n in INSTRUCTORS:
        if n.lower() == u:
            return n
    return ""


def instructor_share():
    try:
        return float(get_secret("INSTRUCTOR_SHARE", "0.40"))
    except Exception:
        return 0.40


def gym_share():
    try:
        return float(get_secret("GYM_SHARE", "0.60"))
    except Exception:
        return 0.60


def visible_sections():
    if is_admin():
        return ["Planning", "Settimana", "Prenota", "Clienti", "Cerca", "Incassi", "Archivio"]
    return ["Planning", "Prenota", "Clienti", "Cerca", "Incassi"]
'''
    if "def configured_users():" not in s and marker in s:
        s = s.replace(marker, helpers, 1)
    else:
        s = _rf(s, "visible_sections", '''def visible_sections():
    if is_admin():
        return ["Planning", "Settimana", "Prenota", "Clienti", "Cerca", "Incassi", "Archivio"]
    return ["Planning", "Prenota", "Clienti", "Cerca", "Incassi"]''')

    s = s.replace('''    data.setdefault("bookings", [])
    data.setdefault("clients", [])''', '''    data.setdefault("bookings", [])
    data.setdefault("clients", [])
    data.setdefault("settlements", [])''', 1)
    s = s.replace('''        b.setdefault("status", "Confermata")
        b.setdefault("date", date.today().isoformat())''', '''        b.setdefault("status", "Confermata")
        b.setdefault("settlement_id", "")
        b.setdefault("gift", False)
        b.setdefault("date", date.today().isoformat())''', 1)

    s = _rf(s, "login", '''def login():
    if st.session_state.get("authenticated", False):
        return True
    users = configured_users()
    left, center, right = st.columns([1.4, 1.2, 1.4])
    with center:
        st.markdown("### Accesso staff")
        username = st.selectbox("Utente", list(users.keys()), key="login_username")
        pwd = st.text_input("Password", type="password", key="main_login_password")
        if st.button("Accedi", type="primary", use_container_width=True):
            cfg = users.get(str(username).lower().strip(), {})
            if pwd and pwd == str(cfg.get("password", "")):
                st.session_state["authenticated"] = True
                st.session_state["current_user"] = str(username).lower().strip()
                st.session_state["current_role"] = str(cfg.get("role", "instructor")).lower().strip()
                st.rerun()
            else:
                st.error("Utente o password non corretti")
    return False''')

    s = _rf(s, "slot_rows", '''def slot_rows(data, d, t, include_cancelled=False, instructor=None):
    rows = []
    for b in data.get("bookings", []):
        if b.get("date") != date_key(d) or b.get("time") != t:
            continue
        if instructor and b.get("instructor") != instructor:
            continue
        if not include_cancelled and b.get("status") == "Annullata":
            continue
        rows.append(b)
    return sorted(rows, key=lambda x: x.get("created_at", ""))''')
    s = _rf(s, "confirmed_count", '''def confirmed_count(data, d, t, exclude_id=None, instructor=None):
    return sum(1 for b in slot_rows(data, d, t, instructor=instructor) if b.get("status") == "Confermata" and b.get("id") != exclude_id)''')
    s = _rf(s, "auto_status", '''def auto_status(data, d, t, instructor=None):
    return "Confermata" if confirmed_count(data, d, t, instructor=instructor) < CAPACITY else "Lista attesa"''')
    s = _rf(s, "slot_status", '''def slot_status(data, d, t, instructor=None):
    rows = slot_rows(data, d, t, instructor=instructor)
    conf = [b for b in rows if b.get("status") == "Confermata"]
    wait = [b for b in rows if b.get("status") == "Lista attesa"]
    return len(conf), len(wait), conf, wait''')
    s = _rf(s, "change_status", '''def change_status(data, bid, status):
    for b in data.get("bookings", []):
        if b.get("id") == bid:
            d, t = parse_date(b["date"]), b["time"]
            instr = b.get("instructor", "")
            if status == "Confermata" and confirmed_count(data, d, t, bid, instr) >= CAPACITY:
                st.error("Lezione già piena (4/4) per questa istruttrice.")
                return False
            b["status"] = status
            return True
    return False''')
    s = _rf(s, "create_booking", '''def create_booking(data, cid, d, t, amount, paid, instructor, note, gift=False):
    c = get_client(data, cid)
    if not c:
        raise ValueError("Cliente non trovato.")
    amount = 0.0 if gift else money(amount)
    paid = True if gift else bool(paid)
    clean_note = note.strip()
    if gift and "omaggio" not in clean_note.lower():
        clean_note = (clean_note + " | " if clean_note else "") + "Seduta omaggio / prova"
    b = {"id": new_id("b_"), "created_at": datetime.now().isoformat(timespec="seconds"), "client_id": cid, "date": date_key(d), "day": DAY_NAMES[d.weekday()], "time": t, "name": full_name(c), "phone": c.get("phone", ""), "email": c.get("email", ""), "note": clean_note, "status": auto_status(data, d, t, instructor), "amount": amount, "paid": paid, "gift": bool(gift), "paid_to_gym_at": datetime.now().isoformat(timespec="seconds") if paid and not gift else "", "paid_to_gym_by": current_user() if paid and not gift else "", "settlement_id": "", "instructor": instructor, "created_by": current_user()}
    data["bookings"].append(b)
    return b''')
    s = _rf(s, "render_booking", '''def render_booking(data, sha):
    st.subheader("Prenota")
    mode = st.radio("Cliente", ["Seleziona da archivio", "Nuovo cliente"], horizontal=True)
    cid = None
    if mode == "Seleziona da archivio":
        opts = client_options(data)
        if opts:
            cid = option_to_client_id(st.selectbox("Cliente", opts))
            c = get_client(data, cid)
            st.caption(f"Telefono: {c.get('phone','')} · Email: {c.get('email','')}")
        else:
            st.warning("Nessun cliente in archivio.")
    else:
        a, b = st.columns(2)
        last = a.text_input("Cognome")
        first = b.text_input("Nome")
        c, d = st.columns(2)
        phone = c.text_input("Telefono")
        email = d.text_input("Email")
        birth = st.text_input("Data di nascita", placeholder="gg-mm-aaaa")
        notes = st.text_area("Note cliente")
        if st.button("Salva nuovo cliente"):
            ok, msg, cid = add_client(data, first, last, phone, email, notes, birth)
            if ok:
                save_and_rerun(data, sha, "Add client")
            else:
                st.error(msg)
    if cid:
        st.markdown("### Dati prenotazione")
        a, b = st.columns(2)
        d = parse_date(a.date_input("Data", value=date.today(), min_value=date.today(), format="DD/MM/YYYY", key="booking_date"))
        ts = times_for(d)
        if not ts:
            st.warning("Nessun orario previsto per questa data.")
            return
        t = b.selectbox("Orario", ts)
        default_instr = instructor_name_from_user()
        default_index = INSTRUCTORS.index(default_instr) if default_instr in INSTRUCTORS else 0
        a, b, c = st.columns(3)
        gift = a.checkbox("Seduta omaggio / prova gratuita", key="booking_gift")
        amount = b.number_input("Importo (€)", min_value=0.0, value=0.0, step=1.0, format="%.2f", disabled=gift)
        paid = c.checkbox("Già incassato dalla palestra", disabled=gift)
        instr = st.selectbox("Istruttrice", INSTRUCTORS, index=default_index)
        note = st.text_area("Note prenotazione")
        n = confirmed_count(data, d, t, instructor=instr)
        status_txt = "Seduta omaggio" if gift else auto_status(data, d, t, instr)
        st.info(f"{instr} · {t}: {n}/{CAPACITY} confermate · stato: {status_txt}")
        if st.button("Salva prenotazione", type="primary"):
            bk = create_booking(data, cid, d, t, amount, paid, instr, note, gift=gift)
            st.session_state["_next_section"] = "Planning"
            save_and_rerun(data, sha, f"Add booking {bk['name']}")''')

    module = '''
def is_gift_booking(b):
    return bool(b.get("gift", False)) or str(b.get("type", "")).lower() == "seduta omaggio" or "omaggio" in str(b.get("note", "")).lower()


def open_cash_rows(data, instructor=None):
    rows = []
    for b in data.get("bookings", []):
        if b.get("status") == "Annullata" or b.get("settlement_id"):
            continue
        if instructor and b.get("instructor") != instructor:
            continue
        rows.append(b)
    return rows


def mark_gym_collected(data, booking_id):
    for b in data.get("bookings", []):
        if b.get("id") == booking_id:
            if is_gift_booking(b):
                return False, "Questa è una seduta omaggio: non c'è incasso."
            b["paid"] = True
            b["paid_to_gym_at"] = datetime.now().isoformat(timespec="seconds")
            b["paid_to_gym_by"] = current_user()
            return True, "Incasso segnato come pagato alla palestra."
    return False, "Prenotazione non trovata."


def mark_share_paid_or_received(data, booking_id):
    for b in data.get("bookings", []):
        if b.get("id") == booking_id:
            if is_gift_booking(b):
                return False, "Seduta omaggio: non genera quota istruttrice."
            if not to_bool(b.get("paid", False)):
                return False, "Prima deve risultare incassato dalla palestra."
            if b.get("settlement_id"):
                return False, "Quota già chiusa."
            sid = new_id("sett_")
            amount = money(b.get("amount", 0))
            b["settlement_id"] = sid
            b["share_paid_at"] = datetime.now().isoformat(timespec="seconds")
            b["share_paid_by"] = current_user()
            data.setdefault("settlements", []).append({"id": sid, "created_at": b["share_paid_at"], "instructor": b.get("instructor", ""), "gross_amount": round(amount, 2), "instructor_amount": round(amount*instructor_share(), 2), "gym_amount": round(amount*gym_share(), 2), "lessons": 1, "closed_by": current_user(), "booking_id": booking_id})
            return True, "Quota 40% segnata come pagata/ricevuta."
    return False, "Prenotazione non trovata."


def settled_share_total(data, instructor=None):
    return sum(money(x.get("instructor_amount", 0)) for x in data.get("settlements", []) if not instructor or x.get("instructor") == instructor)


def _pay_label(b):
    tag = " · OMAGGIO" if is_gift_booking(b) else f" · € {money(b.get('amount', 0)):.2f}"
    return f"{date_it(b.get('date'))} · {b.get('time','')} · {b.get('instructor','')} · {b.get('name','')}{tag}"


def _cash_df(rows):
    return pd.DataFrame([{"Data": date_it(x.get("date")), "Ora": x.get("time", ""), "Istruttrice": x.get("instructor", ""), "Cliente": x.get("name", ""), "Tipo": "Seduta omaggio" if is_gift_booking(x) else "Pagamento", "Importo": money(x.get("amount", 0)), "Incassato palestra": "Sì" if to_bool(x.get("paid", False)) and not is_gift_booking(x) else ("Omaggio" if is_gift_booking(x) else "No"), "Quota 40%": round(money(x.get("amount", 0)) * instructor_share(), 2) if not is_gift_booking(x) else 0.0} for x in rows])


def render_cash_workflow(data, sha, compact=False):
    instr = None if is_admin() else instructor_name_from_user()
    rows = open_cash_rows(data, instr)
    pay_rows = [b for b in rows if not is_gift_booking(b)]
    gift_rows = [b for b in rows if is_gift_booking(b)]
    da_incassare = [b for b in pay_rows if not to_bool(b.get("paid", False))]
    incassati_palestra = [b for b in pay_rows if to_bool(b.get("paid", False))]
    totale = sum(money(b.get("amount", 0)) for b in pay_rows)
    incassato = sum(money(b.get("amount", 0)) for b in incassati_palestra)
    quota_da_pagare = incassato * instructor_share()

    st.markdown("### Gestione incassi")
    a, b, c, d = st.columns(4)
    a.metric("Incasso totale", f"€ {totale:.2f}")
    b.metric("Da incassare", f"€ {sum(money(x.get('amount', 0)) for x in da_incassare):.2f}")
    c.metric("Incassato dalla palestra", f"€ {incassato:.2f}")
    d.metric("Sedute omaggio", len(gift_rows))
    st.caption("Sequenza corretta: 1) da incassare → 2) incassato dalla palestra → 3) BodyCenter paga il 40% ad Alice/Grazia.")

    tab1, tab2, tab3, tab4 = st.tabs(["Da incassare", "Incassati dalla palestra", "Quota 40% da pagare/ricevere", "Sedute omaggio"])
    with tab1:
        if da_incassare:
            st.dataframe(_cash_df(da_incassare), use_container_width=True, hide_index=True)
            i = st.selectbox("Seleziona pagamento incassato dalla palestra", range(len(da_incassare)), format_func=lambda k: _pay_label(da_incassare[k]), key="cash_collect_select")
            if st.button("Segna come incassato dalla palestra", key="cash_collect_btn", use_container_width=is_mobile_client()):
                ok, msg = mark_gym_collected(data, da_incassare[i].get("id"))
                if ok:
                    save_data(data, sha, "Mark gym cash collected")
                    st.success(msg); st.rerun()
                else:
                    st.error(msg)
        else:
            st.success("Nessun importo da incassare.")
    with tab2:
        if incassati_palestra:
            st.metric("Totale incassato dalla palestra", f"€ {incassato:.2f}")
            st.dataframe(_cash_df(incassati_palestra), use_container_width=True, hide_index=True)
        else:
            st.info("Nessun incasso registrato dalla palestra.")
    with tab3:
        if incassati_palestra:
            label = "Totale quota 40% da pagare" if is_admin() else "Totale quota 40% da ricevere"
            button_label = "Segna quota 40% pagata ad Alice/Grazia" if is_admin() else "Segna quota 40% ricevuta"
            st.metric(label, f"€ {quota_da_pagare:.2f}")
            st.dataframe(_cash_df(incassati_palestra), use_container_width=True, hide_index=True)
            i = st.selectbox("Seleziona quota 40%", range(len(incassati_palestra)), format_func=lambda k: _pay_label(incassati_palestra[k]) + f" · quota € {money(incassati_palestra[k].get('amount',0))*instructor_share():.2f}", key="share_received_select")
            if st.button(button_label, key="share_received_btn", use_container_width=is_mobile_client()):
                ok, msg = mark_share_paid_or_received(data, incassati_palestra[i].get("id"))
                if ok:
                    save_data(data, sha, "Mark instructor share paid")
                    st.success(msg); st.rerun()
                else:
                    st.error(msg)
        else:
            st.info("Nessuna quota da pagare/ricevere: prima il pagamento deve essere incassato dalla palestra.")
    with tab4:
        if gift_rows:
            st.dataframe(_cash_df(gift_rows), use_container_width=True, hide_index=True)
        else:
            st.info("Nessuna seduta omaggio registrata.")


def render_payment_tracking_box(data, sha):
    with st.expander("Gestione incassi", expanded=True):
        render_cash_workflow(data, sha, compact=True)


def render_settlements(data, sha):
    st.subheader("Incassi e liquidazioni")
    render_cash_workflow(data, sha)
    instr = None if is_admin() else instructor_name_from_user()
    already = settled_share_total(data, instr)
    st.markdown("### Storico quote 40% già pagate/ricevute")
    hist = []
    for x in data.get("settlements", []):
        if instr and x.get("instructor") != instr:
            continue
        hist.append({"Data": x.get("created_at", ""), "Istruttrice": x.get("instructor", ""), "Quota 40%": money(x.get("instructor_amount", 0)), "Quota BodyCenter 60%": money(x.get("gym_amount", 0)), "Lezioni": int(x.get("lessons", 0) or 0)})
    st.metric("Totale quota già pagata/ricevuta", f"€ {already:.2f}")
    if hist:
        st.dataframe(pd.DataFrame(hist), use_container_width=True, hide_index=True)
    else:
        st.info("Nessuna quota già chiusa.")


def cancel_booking(data, booking_id, note=""):
    for b in data.get("bookings", []):
        if b.get("id") == booking_id:
            if b.get("settlement_id"):
                return False, "Prenotazione già liquidata: non annullarla da qui."
            b["status"] = "Annullata"
            b["cancelled_at"] = datetime.now().isoformat(timespec="seconds")
            b["cancelled_by"] = current_user()
            if note.strip():
                b["note"] = (b.get("note", "") + " | " if b.get("note") else "") + f"Annullata da {current_user()}: {note.strip()}"
            return True, "Prenotazione annullata."
    return False, "Prenotazione non trovata."


def render_cancel_booking_box(data, sha):
    rows=[]
    for b in data.get("bookings",[]):
        if b.get("status") == "Annullata" or b.get("settlement_id"):
            continue
        try:
            if parse_date(b.get("date")) >= date.today(): rows.append(b)
        except Exception: pass
    rows=sorted(rows,key=lambda x:(str(x.get("date","")),str(x.get("time","")),str(x.get("instructor","")),str(x.get("name",""))))
    with st.expander("Annulla prenotazione", expanded=False):
        if not rows:
            st.info("Nessuna prenotazione futura annullabile."); return
        labels=[]; mp={}
        for b in rows:
            lab=f"{date_it(b.get('date'))} · {b.get('time','')} · {b.get('instructor','')} · {b.get('name','')}"; labels.append(lab); mp[lab]=b.get("id")
        choice=st.selectbox("Prenotazione", labels, key="cancel_booking_select")
        note=st.text_input("Motivo / nota opzionale", key="cancel_booking_note")
        okc=st.checkbox("Confermo l'annullamento", key="cancel_booking_confirm")
        if st.button("Annulla prenotazione selezionata", key="cancel_booking_button", type="secondary", use_container_width=is_mobile_client()):
            if not okc: st.warning("Spunta la conferma prima di annullare."); return
            ok,msg=cancel_booking(data,mp[choice],note)
            if ok: save_data(data,sha,"Cancel booking"); st.success(msg); st.rerun()
            else: st.error(msg)


def _planning_base_rows(data, days, instructor=None):
    today=date.today(); end=today+timedelta(days=days-1); out=[]
    for b in data.get("bookings",[]):
        if b.get("status")=="Annullata": continue
        if instructor and b.get("instructor")!=instructor: continue
        try: d=parse_date(b.get("date"))
        except Exception: continue
        if today <= d <= end: out.append(b)
    return sorted(out,key=lambda x:(str(x.get("date","")),str(x.get("time","")),str(x.get("instructor","")),str(x.get("name",""))))


def _h(x):
    return str(x or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")


def _planning_table(rows):
    return pd.DataFrame([{"Quando": f"{date_label_it(b.get('date'))} · {b.get('time','')}", "Istruttrice": b.get("instructor",""), "Cliente": b.get("name",""), "Telefono": b.get("phone",""), "Tipo": "Omaggio" if is_gift_booking(b) else "Pagamento", "Incassato palestra": "Sì" if to_bool(b.get("paid",False)) and not is_gift_booking(b) else ("Omaggio" if is_gift_booking(b) else "No")} for b in rows])


def _render_planning_view(data, rows, title, days=14, show_instructor=True):
    st.markdown(f"### {title}")
    today=date.today(); all_days=[(today+timedelta(days=i)).isoformat() for i in range(days)]
    by={d:[] for d in all_days}
    for r in rows: by.setdefault(r.get("date",""),[]).append(r)
    a,b,c=st.columns(3); a.metric("Oggi", len([x for x in rows if x.get("date")==today.isoformat()])); b.metric(f"Prossimi {days} giorni", len(rows)); c.metric("Omaggio", len([x for x in rows if is_gift_booking(x)]))
    cards=[]
    for d in all_days:
        slot={}
        for r in by.get(d,[]): slot.setdefault((r.get("time",""),r.get("instructor","")),[]).append(r)
        lines=[]
        for (t,instr),group in sorted(slot.items(),key=lambda x:(x[0][0],x[0][1])):
            conf=[x for x in group if x.get("status")=="Confermata"]; wait=[x for x in group if x.get("status")=="Lista attesa"]; names=", ".join([x.get("name","") + (" (omaggio)" if is_gift_booking(x) else "") for x in conf]) or "—"; instr_txt=f" <span>{_h(instr)}</span>" if show_instructor and instr else ""
            lines.append(f"<div class='slot'><b>{_h(t)}</b>{instr_txt} <em>{len(conf)}/{CAPACITY} · lib {max(CAPACITY-len(conf),0)}"+(f" · att {len(wait)}" if wait else "")+f"</em><br><small>{_h(names)}</small></div>")
        cards.append(f"<div class='day-card{' empty' if not lines else ''}'><div class='day-title'>{_h(date_label_it(d))}</div>{''.join(lines) if lines else '<div class=empty-text>—</div>'}</div>")
    css="<style>.plan-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:7px}.day-card{border:1px solid #d9dde3;border-radius:10px;padding:8px 10px;background:#fff;min-height:76px}.day-card.empty{background:#fafafa;color:#9aa0a6}.day-title{font-weight:700;font-size:.92rem;margin-bottom:5px}.slot{font-size:.84rem;line-height:1.18;margin:3px 0 5px;padding-bottom:4px;border-bottom:1px solid #eef0f2}.slot:last-child{border-bottom:0}.slot em{font-style:normal;color:#707782;font-size:.78rem}.slot small{font-size:.78rem}</style>"
    st.markdown(css+"<div class='plan-grid'>"+"".join(cards)+"</div>", unsafe_allow_html=True)
    if rows:
        with st.expander("Elenco rapido", expanded=False): st.dataframe(_planning_table(rows), use_container_width=True, hide_index=True)


def personal_planning_pdf_bytes(data, instr, days=14):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    buf=BytesIO(); rows=_planning_base_rows(data,days,instr); doc=SimpleDocTemplate(buf,pagesize=landscape(A4),leftMargin=.8*cm,rightMargin=.8*cm,topMargin=.7*cm,bottomMargin=.7*cm); styles=getSampleStyleSheet(); elems=[]
    if Path(LOGO_PATH).exists(): elems.append(Image(LOGO_PATH,width=2.5*cm,height=1.2*cm,kind="proportional"))
    elems += [Paragraph(f"Planning personale - {instr}", styles["Title"]), Spacer(1,.2*cm)]
    data_tbl=[["Data","Ora","Cliente","Telefono","Tipo","Incassato palestra","Quota 40%"]]
    for b in rows:
        am=money(b.get("amount",0)); data_tbl.append([date_label_it(b.get("date")), b.get("time",""), b.get("name",""), b.get("phone",""), "Omaggio" if is_gift_booking(b) else "Pagamento", "Sì" if to_bool(b.get("paid",False)) and not is_gift_booking(b) else ("Omaggio" if is_gift_booking(b) else "No"), f"€ {am*instructor_share():.2f}" if not is_gift_booking(b) else "€ 0.00"])
    tab=Table(data_tbl, repeatRows=1); tab.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor(DARK)),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.25,colors.lightgrey),("FONTSIZE",(0,0),(-1,-1),8)])); elems.append(tab); doc.build(elems); return buf.getvalue()


def render_personal_planning_download(data, instr, days=14):
    if instr: st.download_button("Scarica PDF planning personale + incasso", data=personal_planning_pdf_bytes(data,instr,days), file_name=f"planning_{instr.lower()}_14_giorni.pdf", mime="application/pdf", use_container_width=is_mobile_client(), key=f"download_pdf_planning_{instr}")


def render_planning(data, sha=None):
    st.subheader("Planning 14 giorni")
    render_cancel_booking_box(data, sha)
    render_payment_tracking_box(data, sha)
    giorni=14
    if is_admin():
        vista=st.selectbox("Vista", ["Tutte", *INSTRUCTORS], key="planning_admin_view"); instr=None if vista=="Tutte" else vista; _render_planning_view(data,_planning_base_rows(data,giorni,instr),f"Planning {vista}",giorni,show_instructor=True); return
    instr=instructor_name_from_user(); render_personal_planning_download(data,instr,giorni); tab_all,tab_miei=st.tabs(["Planning completo","I miei impegni"])
    with tab_all: _render_planning_view(data,_planning_base_rows(data,giorni,None),"Planning completo",giorni,show_instructor=True)
    with tab_miei: _render_planning_view(data,_planning_base_rows(data,giorni,instr),f"Prossimi impegni {instr}",giorni,show_instructor=False)
'''
    boot = "\n\n# -----------------------------\n# App bootstrap"
    for token in ["\n\ndef mark_gym_collected", "\n\ndef mark_client_collected", "\n\ndef settlement_bookings", "\n\ndef render_settlements", "\n\ndef render_planning"]:
        if token in s:
            start = s.index(token)
            end = s.index(boot, start)
            s = s[:start] + "\n\n" + module.strip() + s[end:]
            break
    else:
        s = s.replace(boot, "\n\n" + module.strip() + boot, 1)

    s = re.sub(r'\ncol_access, col_logout = st\.columns\(\[4, 1\]\).*?st\.rerun\(\)', '', s, flags=re.S)
    menu = '''allowed_sections = visible_sections()
if "_next_section" in st.session_state:
    nxt = st.session_state.pop("_next_section")
    st.session_state["section"] = nxt if nxt in allowed_sections else "Planning"
if "section" not in st.session_state or st.session_state["section"] not in allowed_sections:
    st.session_state["section"] = "Planning"
section = st.radio("Sezione", allowed_sections, horizontal=True, key="section", label_visibility="collapsed")
col_access, col_logout = st.columns([4, 1])
with col_access:
    try: st.caption(f"Accesso: {current_user().capitalize()} · {'Admin' if is_admin() else 'Istruttrice'}")
    except Exception: pass
with col_logout:
    if st.button("Logout", key="logout_user_button", use_container_width=True):
        for k in ["authenticated", "current_user", "current_role", "section", "client_open_id", "archive_open_client_id", "archive_open_select"]: st.session_state.pop(k, None)
        st.rerun()'''
    m = re.search(r'(?:allowed_sections = visible_sections\(\)|if "_next_section" in st\.session_state:).*?section = st\.radio\("Sezione", (?:allowed_sections|SECTIONS), horizontal=True, key="section", label_visibility="collapsed"\)', s, flags=re.S)
    if m: s = s[:m.start()] + menu + s[m.end():]
    dispatch = '''if section == "Planning":
    render_planning(data, sha)
elif section == "Settimana":
    render_week(data, sha)
elif section == "Prenota":
    render_booking(data, sha)
elif section == "Clienti":
    render_clients(data, sha)
elif section == "Cerca":
    render_search(data)
elif section == "Incassi":
    render_settlements(data, sha)
elif section == "Archivio":
    render_archive(data, sha)
'''
    pos = s.rfind('if section == "Planning":')
    if pos == -1: pos = s.rfind('if section == "Settimana":')
    s = s[:pos] + dispatch if pos != -1 else s + "\n" + dispatch
    p.write_text(s, encoding="utf-8")

try:
    _patch_app()
except Exception:
    pass
