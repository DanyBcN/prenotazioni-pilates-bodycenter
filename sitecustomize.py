from pathlib import Path
import re


def _rf(src, name, replacement):
    m = re.search(rf"(^|\n)def {name}\([^\n]*\):\n.*?(?=\n\ndef |\n\n# -----------------------------|\Z)", src, flags=re.S)
    if not m:
        return src
    return src[:m.start()] + ("\n" if m.group(1) else "") + replacement.rstrip() + src[m.end():]


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

    module = '''
def settlement_bookings(data, instructor=None, paid=None):
    out = []
    for b in data.get("bookings", []):
        if b.get("status") == "Annullata" or b.get("settlement_id"):
            continue
        if instructor and b.get("instructor") != instructor:
            continue
        if paid is not None and to_bool(b.get("paid", False)) != paid:
            continue
        out.append(b)
    return out


def settlement_summary(data, instructor=None):
    rows = settlement_bookings(data, instructor)
    paid = [b for b in rows if to_bool(b.get("paid", False))]
    total = sum(money(b.get("amount", 0)) for b in rows)
    paid_total = sum(money(b.get("amount", 0)) for b in paid)
    return {"rows": rows, "paid": paid, "total": total, "paid_total": paid_total,
            "inst_total": total * instructor_share(), "inst_paid": paid_total * instructor_share(),
            "gym_total": total * gym_share(), "gym_paid": paid_total * gym_share()}


def close_instructor_settlement(data, instructor):
    sm = settlement_summary(data, instructor)
    if not sm["paid"]:
        return False, "Nessun importo incassato da liquidare."
    sid = new_id("sett_")
    data.setdefault("settlements", []).append({"id": sid, "created_at": datetime.now().isoformat(timespec="seconds"), "instructor": instructor, "gross_amount": round(sm["paid_total"], 2), "instructor_amount": round(sm["inst_paid"], 2), "gym_amount": round(sm["gym_paid"], 2), "lessons": len(sm["paid"]), "closed_by": current_user()})
    for b in sm["paid"]:
        b["settlement_id"] = sid
    return True, f"Liquidazione chiusa per {instructor}: € {sm['inst_paid']:.2f}."


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
    rows = []
    for b in data.get("bookings", []):
        if b.get("status") == "Annullata" or b.get("settlement_id"):
            continue
        try:
            if parse_date(b.get("date")) >= date.today():
                rows.append(b)
        except Exception:
            pass
    rows = sorted(rows, key=lambda x: (str(x.get("date", "")), str(x.get("time", "")), str(x.get("instructor", "")), str(x.get("name", ""))))
    with st.expander("Annulla prenotazione", expanded=False):
        if not rows:
            st.info("Nessuna prenotazione futura annullabile.")
            return
        labels, mp = [], {}
        for b in rows:
            lab = f"{date_it(b.get('date'))} · {b.get('time','')} · {b.get('instructor','')} · {b.get('name','')}"
            labels.append(lab)
            mp[lab] = b.get("id")
        choice = st.selectbox("Prenotazione", labels, key="cancel_booking_select")
        note = st.text_input("Motivo / nota opzionale", key="cancel_booking_note")
        okc = st.checkbox("Confermo l'annullamento", key="cancel_booking_confirm")
        if st.button("Annulla prenotazione selezionata", key="cancel_booking_button", type="secondary", use_container_width=is_mobile_client()):
            if not okc:
                st.warning("Spunta la conferma prima di annullare.")
                return
            ok, msg = cancel_booking(data, mp[choice], note)
            if ok:
                save_data(data, sha, "Cancel booking")
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)


def render_settlements(data, sha):
    st.subheader("Incassi e liquidazioni")
    if is_admin():
        sums = {i: settlement_summary(data, i) for i in INSTRUCTORS}
        a, b = st.columns(2)
        a.metric("Totale incassi complessivi", f"€ {sum(x['total'] for x in sums.values()):.2f}")
        b.metric("Totale BodyCenter 60%", f"€ {sum(x['gym_total'] for x in sums.values()):.2f}")
        cols = st.columns(4)
        for n, i in enumerate(INSTRUCTORS):
            cols[n*2].metric(f"Totale {i}", f"€ {sums[i]['total']:.2f}")
            cols[n*2+1].metric(f"Guadagno {i} 40%", f"€ {sums[i]['inst_total']:.2f}")
        for i in INSTRUCTORS:
            sm = sums[i]
            with st.container(border=True):
                st.markdown(f"### {i}")
                c1, c2, c3 = st.columns(3)
                c1.metric(f"Guadagno {i} 40%", f"€ {sm['inst_total']:.2f}")
                c2.metric("Da liquidare ora", f"€ {sm['inst_paid']:.2f}")
                c3.metric("Quota BodyCenter 60%", f"€ {sm['gym_total']:.2f}")
                if st.button(f"Liquida e azzera pagato {i}", key=f"settle_{i}", type="primary", use_container_width=is_mobile_client()):
                    ok, msg = close_instructor_settlement(data, i)
                    if ok:
                        save_data(data, sha, f"Close settlement {i}")
                        st.success(msg)
                        st.rerun()
                    else:
                        st.info(msg)
        return
    instr = instructor_name_from_user()
    sm = settlement_summary(data, instr)
    a, b, c = st.columns(3)
    a.metric("Mio guadagno 40%", f"€ {sm['inst_total']:.2f}")
    b.metric("Quota palestra 60%", f"€ {sm['gym_total']:.2f}")
    c.metric("Da liquidare ora", f"€ {sm['inst_paid']:.2f}")
    st.caption(f"Lezioni mie: {len(sm['rows'])} · pagate: {len(sm['paid'])} · non pagate: {len(sm['rows'])-len(sm['paid'])}")
    if sm["rows"]:
        df = pd.DataFrame([{"Data": date_it(x.get("date")), "Ora": x.get("time", ""), "Cliente": x.get("name", ""), "Pagato": "Sì" if to_bool(x.get("paid", False)) else "No", "Quota 40%": round(money(x.get("amount", 0))*instructor_share(), 2), "Quota palestra 60%": round(money(x.get("amount", 0))*gym_share(), 2)} for x in sm["rows"]])
        st.dataframe(df, use_container_width=True, hide_index=True)


def _planning_base_rows(data, days, instructor=None):
    today = date.today()
    end = today + timedelta(days=days-1)
    out = []
    for b in data.get("bookings", []):
        if b.get("status") == "Annullata":
            continue
        if instructor and b.get("instructor") != instructor:
            continue
        try:
            d = parse_date(b.get("date"))
        except Exception:
            continue
        if today <= d <= end:
            out.append(b)
    return sorted(out, key=lambda x: (str(x.get("date", "")), str(x.get("time", "")), str(x.get("instructor", "")), str(x.get("name", ""))))


def _h(x):
    return str(x or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _planning_table(rows):
    return pd.DataFrame([{"Quando": f"{date_label_it(b.get('date'))} · {b.get('time','')}", "Istruttrice": b.get("instructor", ""), "Cliente": b.get("name", ""), "Telefono": b.get("phone", ""), "Stato": b.get("status", ""), "Pagato": "Sì" if to_bool(b.get("paid", False)) else "No"} for b in rows])


def _render_planning_view(data, rows, title, days=14, show_instructor=True):
    st.markdown(f"### {title}")
    today = date.today()
    all_days = [(today + timedelta(days=i)).isoformat() for i in range(days)]
    by_day = {d: [] for d in all_days}
    for r in rows:
        by_day.setdefault(r.get("date", ""), []).append(r)
    a, b, c = st.columns(3)
    a.metric("Oggi", len([x for x in rows if x.get("date") == today.isoformat()]))
    b.metric(f"Prossimi {days} giorni", len(rows))
    c.metric("Lista attesa", len([x for x in rows if x.get("status") == "Lista attesa"]))
    cards = []
    for d in all_days:
        slot = {}
        for r in by_day.get(d, []):
            slot.setdefault((r.get("time", ""), r.get("instructor", "")), []).append(r)
        lines = []
        for (t, instr), group in sorted(slot.items(), key=lambda x: (x[0][0], x[0][1])):
            conf = [x for x in group if x.get("status") == "Confermata"]
            wait = [x for x in group if x.get("status") == "Lista attesa"]
            names = ", ".join([x.get('name','') for x in conf]) or '—'
            instr_txt = f" <span>{_h(instr)}</span>" if show_instructor and instr else ""
            lines.append(f"<div class='slot'><b>{_h(t)}</b>{instr_txt} <em>{len(conf)}/{CAPACITY} · lib {max(CAPACITY-len(conf),0)}" + (f" · att {len(wait)}" if wait else "") + f"</em><br><small>{_h(names)}</small></div>")
        body = "".join(lines) if lines else "<div class='empty-text'>—</div>"
        cards.append(f"<div class='day-card{' empty' if not lines else ''}'><div class='day-title'>{_h(date_label_it(d))}</div>{body}</div>")
    css = "<style>.plan-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:7px}.day-card{border:1px solid #d9dde3;border-radius:10px;padding:8px 10px;background:#fff;min-height:76px}.day-card.empty{background:#fafafa;color:#9aa0a6}.day-title{font-weight:700;font-size:.92rem;margin-bottom:5px}.slot{font-size:.84rem;line-height:1.18;margin:3px 0 5px;padding-bottom:4px;border-bottom:1px solid #eef0f2}.slot:last-child{border-bottom:0}.slot em{font-style:normal;color:#707782;font-size:.78rem}.slot small{font-size:.78rem}</style>"
    st.markdown(css + "<div class='plan-grid'>" + "".join(cards) + "</div>", unsafe_allow_html=True)
    if rows:
        with st.expander("Elenco rapido", expanded=False):
            st.dataframe(_planning_table(rows), use_container_width=True, hide_index=True)


def personal_planning_pdf_bytes(data, instr, days=14):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    buf = BytesIO()
    rows = _planning_base_rows(data, days, instr)
    q40 = sum(money(b.get("amount", 0))*instructor_share() for b in rows)
    q60 = sum(money(b.get("amount", 0))*gym_share() for b in rows)
    paid40 = sum(money(b.get("amount", 0))*instructor_share() for b in rows if to_bool(b.get("paid", False)))
    today = date.today()
    all_days = [(today+timedelta(days=i)).isoformat() for i in range(days)]
    by = {d: [] for d in all_days}
    for r in rows:
        by.setdefault(r.get("date", ""), []).append(r)
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=1*cm, rightMargin=1*cm, topMargin=0.8*cm, bottomMargin=0.8*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleDB", parent=styles["Title"], fontSize=18, leading=22, textColor=colors.HexColor(DARK))
    small = ParagraphStyle("SmallDB", parent=styles["Normal"], fontSize=7, leading=8)
    normal = ParagraphStyle("NormalDB", parent=styles["Normal"], fontSize=8, leading=10)
    story = []
    logo_cell = ""
    logo = Path(LOGO_PATH)
    if logo.exists():
        logo_cell = Image(str(logo), width=3.2*cm, height=1.3*cm, kind="proportional")
    header = Table([[logo_cell, Paragraph(f"Planning personale - {instr}", title_style)], ["", Paragraph(f"Periodo: {date_it(all_days[0])} - {date_it(all_days[-1])}", normal)]], colWidths=[4*cm, 22*cm])
    header.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("BOTTOMPADDING", (0,0), (-1,-1), 5)]))
    story += [header, Spacer(1, 0.15*cm)]
    summary = Table([["Mio incasso 40%", "Quota palestra 60%", "Mio già pagato", "Mio da incassare"], [f"€ {q40:.2f}", f"€ {q60:.2f}", f"€ {paid40:.2f}", f"€ {q40-paid40:.2f}"]], colWidths=[6.5*cm]*4)
    summary.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor(LIGHT_GREEN)), ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor(DARK)), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTNAME", (0,1), (-1,1), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 10), ("ALIGN", (0,0), (-1,-1), "CENTER"), ("BOX", (0,0), (-1,-1), 0.6, colors.HexColor("#cfd8d3")), ("INNERGRID", (0,0), (-1,-1), 0.3, colors.HexColor("#dfe7e2")), ("PADDING", (0,0), (-1,-1), 7)]))
    story += [summary, Spacer(1, 0.25*cm)]
    table_rows = [["Data", "Ora", "Cliente", "Telefono", "Pagato", "Quota 40%", "Palestra 60%", "Note"]]
    for d in all_days:
        day_rows = sorted(by.get(d, []), key=lambda x: (str(x.get("time", "")), str(x.get("name", ""))))
        if not day_rows:
            table_rows.append([Paragraph(date_label_it(d), small), "-", Paragraph("-", small), "", "", "", "", ""])
            continue
        first = True
        for b in day_rows:
            am = money(b.get("amount", 0))
            table_rows.append([Paragraph(date_label_it(d) if first else "", small), Paragraph(str(b.get("time", "")), small), Paragraph(_h(b.get("name", "")), small), Paragraph(_h(b.get("phone", "")), small), "Sì" if to_bool(b.get("paid", False)) else "No", f"€ {am*instructor_share():.2f}", f"€ {am*gym_share():.2f}", Paragraph(_h(b.get("note", "")), small)])
            first = False
    tbl = Table(table_rows, repeatRows=1, colWidths=[3.0*cm, 1.6*cm, 4.3*cm, 3.0*cm, 1.6*cm, 2.3*cm, 2.5*cm, 6.5*cm])
    tbl.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor(DARK)), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 7), ("VALIGN", (0,0), (-1,-1), "TOP"), ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#d9dde3")), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8faf9")]), ("PADDING", (0,0), (-1,-1), 4)]))
    story.append(tbl)
    doc.build(story)
    return buf.getvalue()


def render_personal_planning_download(data, instr, days=14):
    if instr:
        st.download_button("Scarica PDF planning personale + incasso", data=personal_planning_pdf_bytes(data, instr, days), file_name=f"planning_{instr.lower()}_14_giorni.pdf", mime="application/pdf", use_container_width=is_mobile_client(), key=f"download_pdf_planning_{instr}")


def render_planning(data, sha=None):
    st.subheader("Planning 14 giorni")
    render_cancel_booking_box(data, sha)
    giorni = 14
    if is_admin():
        vista = st.selectbox("Vista", ["Tutte", *INSTRUCTORS], key="planning_admin_view")
        instr = None if vista == "Tutte" else vista
        _render_planning_view(data, _planning_base_rows(data, giorni, instr), f"Planning {vista}", giorni, show_instructor=True)
        return
    instr = instructor_name_from_user()
    render_personal_planning_download(data, instr, giorni)
    tab_miei, tab_tutti = st.tabs(["I miei impegni", "Tutti gli impegni"])
    with tab_miei:
        _render_planning_view(data, _planning_base_rows(data, giorni, instr), f"Prossimi impegni {instr}", giorni, show_instructor=False)
    with tab_tutti:
        _render_planning_view(data, _planning_base_rows(data, giorni, None), "Planning completo", giorni, show_instructor=True)
'''
    boot = "\n\n# -----------------------------\n# App bootstrap"
    for token in ["\n\ndef settlement_bookings", "\n\ndef unsettled_bookings", "\n\ndef render_settlements", "\n\ndef render_planning"]:
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
    try:
        st.caption(f"Accesso: {current_user().capitalize()} · {'Admin' if is_admin() else 'Istruttrice'}")
    except Exception:
        pass
with col_logout:
    if st.button("Logout", key="logout_user_button", use_container_width=True):
        for k in ["authenticated", "current_user", "current_role", "section", "client_open_id", "archive_open_client_id", "archive_open_select"]:
            st.session_state.pop(k, None)
        st.rerun()'''
    m = re.search(r'(?:allowed_sections = visible_sections\(\)|if "_next_section" in st\.session_state:).*?section = st\.radio\("Sezione", (?:allowed_sections|SECTIONS), horizontal=True, key="section", label_visibility="collapsed"\)', s, flags=re.S)
    if m:
        s = s[:m.start()] + menu + s[m.end():]

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
    if pos == -1:
        pos = s.rfind('if section == "Settimana":')
    if pos != -1:
        s = s[:pos] + dispatch
    else:
        s += "\n" + dispatch

    p.write_text(s, encoding="utf-8")

try:
    _patch_app()
except Exception:
    pass
