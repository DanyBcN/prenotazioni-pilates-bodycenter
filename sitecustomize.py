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
        b.setdefault("gym_delivered_at", "")
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
    s = _rf(s, "create_booking", '''def create_booking(data, cid, d, t, amount, paid, instructor, note):
    c = get_client(data, cid)
    if not c:
        raise ValueError("Cliente non trovato.")
    b = {"id": new_id("b_"), "created_at": datetime.now().isoformat(timespec="seconds"), "client_id": cid, "date": date_key(d), "day": DAY_NAMES[d.weekday()], "time": t, "name": full_name(c), "phone": c.get("phone", ""), "email": c.get("email", ""), "note": note.strip(), "status": auto_status(data, d, t, instructor), "amount": money(amount), "paid": bool(paid), "paid_to_gym_at": datetime.now().isoformat(timespec="seconds") if paid else "", "paid_to_gym_by": current_user() if paid else "", "gym_delivered_at": "", "gym_delivered_by": "", "settlement_id": "", "instructor": instructor, "created_by": current_user()}
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
        amount = a.number_input("Importo (€)", min_value=0.0, value=0.0, step=1.0, format="%.2f")
        paid = b.checkbox("Incassato dal cliente")
        instr = c.selectbox("Istruttrice", INSTRUCTORS, index=default_index)
        note = st.text_area("Note prenotazione")
        n = confirmed_count(data, d, t, instructor=instr)
        st.info(f"{instr} · {t}: {n}/{CAPACITY} confermate · stato automatico: {auto_status(data, d, t, instr)}")
        if st.button("Salva prenotazione", type="primary"):
            bk = create_booking(data, cid, d, t, amount, paid, instr, note)
            st.session_state["_next_section"] = "Planning"
            save_and_rerun(data, sha, f"Add booking {bk['name']}")''')

    module = r'''
def mark_client_collected(data, booking_id):
    for b in data.get("bookings", []):
        if b.get("id") == booking_id:
            if b.get("status") == "Annullata":
                return False, "Prenotazione annullata."
            b["paid"] = True
            b["paid_to_gym_at"] = datetime.now().isoformat(timespec="seconds")
            b["paid_to_gym_by"] = current_user()
            return True, "Incasso cliente segnato."
    return False, "Prenotazione non trovata."


def mark_cash_delivered_to_gym(data, booking_id):
    for b in data.get("bookings", []):
        if b.get("id") == booking_id:
            if not to_bool(b.get("paid", False)):
                return False, "Prima segna l'incasso cliente."
            b["gym_delivered_at"] = datetime.now().isoformat(timespec="seconds")
            b["gym_delivered_by"] = current_user()
            return True, "Incasso consegnato a BodyCenter segnato."
    return False, "Prenotazione non trovata."


def mark_share_received(data, booking_id):
    for b in data.get("bookings", []):
        if b.get("id") == booking_id:
            if not to_bool(b.get("paid", False)):
                return False, "Prima segna l'incasso cliente."
            if not b.get("gym_delivered_at"):
                return False, "Prima segna la consegna dell'incasso a BodyCenter."
            if b.get("settlement_id"):
                return False, "Quota già ricevuta."
            sid = new_id("sett_")
            amount = money(b.get("amount", 0))
            b["settlement_id"] = sid
            b["share_paid_at"] = datetime.now().isoformat(timespec="seconds")
            b["share_paid_by"] = current_user()
            data.setdefault("settlements", []).append({"id": sid, "created_at": b["share_paid_at"], "instructor": b.get("instructor", ""), "gross_amount": round(amount, 2), "instructor_amount": round(amount*instructor_share(), 2), "gym_amount": round(amount*gym_share(), 2), "lessons": 1, "closed_by": current_user(), "booking_id": booking_id})
            return True, "Quota istruttrice ricevuta segnata."
    return False, "Prenotazione non trovata."


def settled_share_total(data, instructor=None):
    return sum(money(x.get("instructor_amount", 0)) for x in data.get("settlements", []) if not instructor or x.get("instructor") == instructor)


def _pay_label(b):
    return f"{date_it(b.get('date'))} · {b.get('time','')} · {b.get('instructor','')} · {b.get('name','')}"


def render_payment_tracking_box(data, sha):
    with st.expander("Incassi / consegna palestra / quota istruttrice", expanded=True):
        st.caption("Qui Grazia/Alice segnano: incasso dal cliente, consegna dell'incasso a BodyCenter e quota 40% ricevuta.")
        instr_user = instructor_name_from_user()
        open_rows = [b for b in data.get("bookings", []) if b.get("status") != "Annullata" and not b.get("settlement_id")]
        rows = open_rows if is_admin() else [b for b in open_rows if b.get("instructor") == instr_user]
        todo1 = sorted([b for b in rows if not to_bool(b.get("paid", False))], key=lambda x:(str(x.get("date","")),str(x.get("time","")),str(x.get("name",""))))
        todo2 = sorted([b for b in rows if to_bool(b.get("paid", False)) and not b.get("gym_delivered_at")], key=lambda x:(str(x.get("date","")),str(x.get("time","")),str(x.get("name",""))))
        todo3 = sorted([b for b in rows if to_bool(b.get("paid", False)) and b.get("gym_delivered_at")], key=lambda x:(str(x.get("date","")),str(x.get("time","")),str(x.get("name",""))))
        st.markdown("**1. Incasso ricevuto dal cliente**")
        if todo1:
            i = st.selectbox("Scegli prenotazione da segnare come incassata", range(len(todo1)), format_func=lambda k: _pay_label(todo1[k]), key="cash_client_select")
            if st.button("Segna incasso cliente", key="cash_client_btn", use_container_width=is_mobile_client()):
                ok, msg = mark_client_collected(data, todo1[i].get("id"))
                if ok:
                    save_data(data, sha, "Mark client cash collected")
                    st.success(msg); st.rerun()
                else: st.error(msg)
        else:
            st.info("Nessun incasso cliente da segnare.")
        st.markdown("**2. Incasso consegnato a BodyCenter**")
        if todo2:
            i = st.selectbox("Scegli incasso consegnato a BodyCenter", range(len(todo2)), format_func=lambda k: _pay_label(todo2[k]) + f" · € {money(todo2[k].get('amount',0)):.2f}", key="cash_deliver_select")
            if st.button("Segna incasso consegnato a BodyCenter", key="cash_deliver_btn", use_container_width=is_mobile_client()):
                ok, msg = mark_cash_delivered_to_gym(data, todo2[i].get("id"))
                if ok:
                    save_data(data, sha, "Mark cash delivered to gym")
                    st.success(msg); st.rerun()
                else: st.error(msg)
        else:
            st.info("Nessun incasso da consegnare a BodyCenter.")
        st.markdown("**3. Quota istruttrice ricevuta**")
        if todo3:
            i = st.selectbox("Scegli quota ricevuta", range(len(todo3)), format_func=lambda k: _pay_label(todo3[k]) + f" · quota € {money(todo3[k].get('amount',0))*instructor_share():.2f}", key="share_received_select")
            if st.button("Segna quota 40% ricevuta", key="share_received_btn", use_container_width=is_mobile_client()):
                ok, msg = mark_share_received(data, todo3[i].get("id"))
                if ok:
                    save_data(data, sha, "Mark instructor share received")
                    st.success(msg); st.rerun()
                else: st.error(msg)
        else:
            st.info("Nessuna quota da segnare come ricevuta.")


def settlement_bookings(data, instructor=None, paid=None):
    rows = []
    for b in data.get("bookings", []):
        if b.get("status") == "Annullata" or b.get("settlement_id"):
            continue
        if instructor and b.get("instructor") != instructor:
            continue
        if paid is not None and to_bool(b.get("paid", False)) != paid:
            continue
        rows.append(b)
    return rows


def render_settlements(data, sha):
    st.subheader("Incassi e liquidazioni")
    rows = [b for b in data.get("bookings", []) if b.get("status") != "Annullata"]
    if is_admin():
        open_rows = [b for b in rows if not b.get("settlement_id")]
        collected = sum(money(b.get("amount",0)) for b in open_rows if to_bool(b.get("paid",False)))
        to_deliver = sum(money(b.get("amount",0)) for b in open_rows if to_bool(b.get("paid",False)) and not b.get("gym_delivered_at"))
        delivered = sum(money(b.get("amount",0)) for b in open_rows if to_bool(b.get("paid",False)) and b.get("gym_delivered_at"))
        due = delivered * instructor_share()
        a,b,c,d = st.columns(4)
        a.metric("Incassato da Alice/Grazia", f"€ {collected:.2f}")
        b.metric("Da consegnare a BodyCenter", f"€ {to_deliver:.2f}")
        c.metric("Consegnato a BodyCenter", f"€ {delivered:.2f}")
        d.metric("Da dare alle istruttrici", f"€ {due:.2f}")
        table=[]
        for instr in INSTRUCTORS:
            r=[x for x in open_rows if x.get("instructor")==instr]
            ci=sum(money(x.get("amount",0)) for x in r if to_bool(x.get("paid",False)))
            cd=sum(money(x.get("amount",0)) for x in r if to_bool(x.get("paid",False)) and not x.get("gym_delivered_at"))
            co=sum(money(x.get("amount",0)) for x in r if to_bool(x.get("paid",False)) and x.get("gym_delivered_at"))
            table.append({"Istruttrice": instr, "Totale incassato": ci, "Da consegnare a BodyCenter": cd, "Consegnato a BodyCenter": co, "Quota da dare 40%": co*instructor_share(), "Quota già data": settled_share_total(data,instr), "Quota BodyCenter 60%": co*gym_share()})
        st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)
        render_payment_tracking_box(data, sha)
        return
    instr = instructor_name_from_user()
    my=[b for b in rows if b.get("instructor")==instr and not b.get("settlement_id")]
    collected=sum(money(b.get("amount",0)) for b in my if to_bool(b.get("paid",False)))
    todel=sum(money(b.get("amount",0)) for b in my if to_bool(b.get("paid",False)) and not b.get("gym_delivered_at"))
    delivered=sum(money(b.get("amount",0)) for b in my if to_bool(b.get("paid",False)) and b.get("gym_delivered_at"))
    a,b,c,d=st.columns(4)
    a.metric("Incassato da te", f"€ {collected:.2f}")
    b.metric("Da consegnare a palestra", f"€ {todel:.2f}")
    c.metric("Consegnato a palestra", f"€ {delivered:.2f}")
    d.metric("Da ricevere 40%", f"€ {delivered*instructor_share():.2f}")
    st.caption(f"Quota già ricevuta: € {settled_share_total(data,instr):.2f}")
    if my:
        df = pd.DataFrame([{"Data": date_it(x.get("date")), "Ora": x.get("time",""), "Cliente": x.get("name",""), "Incassato": "Sì" if to_bool(x.get("paid",False)) else "No", "Consegnato palestra": "Sì" if x.get("gym_delivered_at") else "No", "Quota 40%": round(money(x.get("amount",0))*instructor_share(),2), "Stato": "Da ricevere" if to_bool(x.get("paid",False)) and x.get("gym_delivered_at") else ("Da consegnare" if to_bool(x.get("paid",False)) else "Da incassare")} for x in my])
        st.dataframe(df, use_container_width=True, hide_index=True)
    render_payment_tracking_box(data, sha)


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
    return pd.DataFrame([{"Quando": f"{date_label_it(b.get('date'))} · {b.get('time','')}", "Istruttrice": b.get("instructor",""), "Cliente": b.get("name",""), "Telefono": b.get("phone",""), "Incassato": "Sì" if to_bool(b.get("paid",False)) else "No", "Consegnato palestra": "Sì" if b.get("gym_delivered_at") else "No"} for b in rows])


def _render_planning_view(data, rows, title, days=14, show_instructor=True):
    st.markdown(f"### {title}")
    today=date.today(); all_days=[(today+timedelta(days=i)).isoformat() for i in range(days)]
    by={d:[] for d in all_days}
    for r in rows: by.setdefault(r.get("date",""),[]).append(r)
    a,b,c=st.columns(3); a.metric("Oggi", len([x for x in rows if x.get("date")==today.isoformat()])); b.metric(f"Prossimi {days} giorni", len(rows)); c.metric("Lista attesa", len([x for x in rows if x.get("status")=="Lista attesa"]))
    cards=[]
    for d in all_days:
        slot={}
        for r in by.get(d,[]): slot.setdefault((r.get("time",""),r.get("instructor","")),[]).append(r)
        lines=[]
        for (t,instr),group in sorted(slot.items(),key=lambda x:(x[0][0],x[0][1])):
            conf=[x for x in group if x.get("status")=="Confermata"]; wait=[x for x in group if x.get("status")=="Lista attesa"]; names=", ".join([x.get("name","") for x in conf]) or "—"; instr_txt=f" <span>{_h(instr)}</span>" if show_instructor and instr else ""
            lines.append(f"<div class='slot'><b>{_h(t)}</b>{instr_txt} <em>{len(conf)}/{CAPACITY} · lib {max(CAPACITY-len(conf),0)}"+(f" · att {len(wait)}" if wait else "")+f"</em><br><small>{_h(names)}</small></div>")
        cards.append(f"<div class='day-card{' empty' if not lines else ''}'><div class='day-title'>{_h(date_label_it(d))}</div>{''.join(lines) if lines else '<div class=empty-text>—</div>'}</div>")
    css="<style>.plan-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:7px}.day-card{border:1px solid #d9dde3;border-radius:10px;padding:8px 10px;background:#fff;min-height:76px}.day-card.empty{background:#fafafa;color:#9aa0a6}.day-title{font-weight:700;font-size:.92rem;margin-bottom:5px}.slot{font-size:.84rem;line-height:1.18;margin:3px 0 5px;padding-bottom:4px;border-bottom:1px solid #eef0f2}.slot:last-child{border-bottom:0}.slot em{font-style:normal;color:#707782;font-size:.78rem}.slot small{font-size:.78rem}</style>"
    st.markdown(css+"<div class='plan-grid'>"+"".join(cards)+"</div>", unsafe_allow_html=True)
    if rows:
        with st.expander("Elenco rapido", expanded=False): st.dataframe(_planning_table(rows), use_container_width=True, hide_index=True)


def personal_planning_pdf_bytes(data, instr, days=14):
    # PDF essenziale, stabile
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    buf=BytesIO(); rows=_planning_base_rows(data,days,instr); doc=SimpleDocTemplate(buf,pagesize=landscape(A4),leftMargin=.8*cm,rightMargin=.8*cm,topMargin=.7*cm,bottomMargin=.7*cm); styles=getSampleStyleSheet(); elems=[]
    if Path(LOGO_PATH).exists(): elems.append(Image(LOGO_PATH,width=2.5*cm,height=1.2*cm,kind="proportional"))
    elems += [Paragraph(f"Planning personale - {instr}", styles["Title"]), Spacer(1,.2*cm)]
    data_tbl=[["Data","Ora","Cliente","Telefono","Incassato","Consegnato","Quota 40%"]]
    for b in rows:
        am=money(b.get("amount",0)); data_tbl.append([date_label_it(b.get("date")), b.get("time",""), b.get("name",""), b.get("phone",""), "Sì" if to_bool(b.get("paid",False)) else "No", "Sì" if b.get("gym_delivered_at") else "No", f"€ {am*instructor_share():.2f}"])
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
    for token in ["\n\ndef mark_client_collected", "\n\ndef settlement_bookings", "\n\ndef render_settlements", "\n\ndef render_planning"]:
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
