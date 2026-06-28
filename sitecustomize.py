from pathlib import Path
import re


def _replace_function(src, name, replacement):
    m = re.search(rf"\ndef {name}\([^\n]*\):\n.*?(?=\n\ndef |\n\n# -----------------------------|\Z)", src, flags=re.S)
    if m:
        return src[:m.start()] + "\n\n" + replacement.rstrip() + src[m.end():]
    return src


def _patch_app():
    p = Path(__file__).with_name("app.py")
    if not p.exists():
        return
    s = p.read_text(encoding="utf-8")

    marker = 'def github_file_url():\n    return f"https://api.github.com/repos/{get_secret(\'GITHUB_REPO\')}/contents/{LOCAL_DATA_PATH}"\n'
    helper_block = '''def github_file_url():
    return f"https://api.github.com/repos/{get_secret('GITHUB_REPO')}/contents/{LOCAL_DATA_PATH}"


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
    for name in INSTRUCTORS:
        if name.lower() == u:
            return name
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
    return ["Planning", "Settimana", "Prenota", "Clienti", "Cerca", "Incassi", "Archivio"]
'''
    if "def configured_users():" not in s and marker in s:
        s = s.replace(marker, helper_block, 1)
    elif "def visible_sections():" in s:
        s = _replace_function(s, "visible_sections", '''def visible_sections():
    return ["Planning", "Settimana", "Prenota", "Clienti", "Cerca", "Incassi", "Archivio"]''')

    s = s.replace('''    data.setdefault("bookings", [])
    data.setdefault("clients", [])''', '''    data.setdefault("bookings", [])
    data.setdefault("clients", [])
    data.setdefault("settlements", [])''', 1)
    s = s.replace('''        b.setdefault("status", "Confermata")
        b.setdefault("date", date.today().isoformat())''', '''        b.setdefault("status", "Confermata")
        b.setdefault("settlement_id", "")
        b.setdefault("date", date.today().isoformat())''', 1)

    s = _replace_function(s, "login", '''def login():
    if st.session_state.get("authenticated", False):
        return True
    users = configured_users()
    names = list(users.keys())
    left, center, right = st.columns([1.4, 1.2, 1.4])
    with center:
        st.markdown("### Accesso staff")
        st.caption("Seleziona utente e inserisci la password.")
        username = st.selectbox("Utente", names, key="login_username")
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

    module_code = '''

def settlement_bookings(data, instructor=None, paid=None):
    rows = []
    for b in data.get("bookings", []):
        if b.get("status") == "Annullata":
            continue
        if b.get("settlement_id"):
            continue
        if instructor and b.get("instructor") != instructor:
            continue
        if paid is not None and to_bool(b.get("paid", False)) != paid:
            continue
        rows.append(b)
    return rows


def settlement_summary(data, instructor=None):
    all_rows = settlement_bookings(data, instructor, paid=None)
    paid_rows = settlement_bookings(data, instructor, paid=True)
    unpaid_rows = settlement_bookings(data, instructor, paid=False)
    total = sum(money(b.get("amount", 0)) for b in all_rows)
    paid_total = sum(money(b.get("amount", 0)) for b in paid_rows)
    unpaid_total = sum(money(b.get("amount", 0)) for b in unpaid_rows)
    return {
        "all_rows": all_rows,
        "paid_rows": paid_rows,
        "unpaid_rows": unpaid_rows,
        "total": total,
        "paid_total": paid_total,
        "unpaid_total": unpaid_total,
        "inst_total": total * instructor_share(),
        "inst_paid": paid_total * instructor_share(),
        "gym_total": total * gym_share(),
        "gym_paid": paid_total * gym_share(),
    }


def close_instructor_settlement(data, instructor):
    summary = settlement_summary(data, instructor)
    rows = summary["paid_rows"]
    if not rows:
        return False, "Nessun importo incassato da liquidare."
    sid = new_id("sett_")
    data.setdefault("settlements", []).append({
        "id": sid,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "instructor": instructor,
        "gross_amount": round(summary["paid_total"], 2),
        "instructor_amount": round(summary["inst_paid"], 2),
        "gym_amount": round(summary["gym_paid"], 2),
        "lessons": len(rows),
        "closed_by": current_user(),
    })
    for b in rows:
        b["settlement_id"] = sid
    return True, f"Liquidazione chiusa per {instructor}: € {summary['inst_paid']:.2f}."


def current_settlement_df(rows):
    return pd.DataFrame([{
        "Data": date_it(b.get("date")),
        "Ora": b.get("time", ""),
        "Cliente": b.get("name", ""),
        "Pagato": "Sì" if to_bool(b.get("paid", False)) else "No",
        "Stato": "Da liquidare" if to_bool(b.get("paid", False)) else "Da incassare",
        "Importo totale": money(b.get("amount", 0)),
        "Quota istruttrice 40%": round(money(b.get("amount", 0)) * instructor_share(), 2),
        "Quota BodyCenter 60%": round(money(b.get("amount", 0)) * gym_share(), 2),
    } for b in rows])


def historical_settlement_df(data, instructor=None):
    hist = []
    for x in data.get("settlements", []):
        if instructor and x.get("instructor") != instructor:
            continue
        hist.append({
            "Data liquidazione": x.get("created_at", ""),
            "Istruttrice": x.get("instructor", ""),
            "Incassato liquidato": money(x.get("gross_amount", 0)),
            "Quota istruttrice 40%": money(x.get("instructor_amount", 0)),
            "Quota BodyCenter 60%": money(x.get("gym_amount", 0)),
            "Lezioni": int(x.get("lessons", 0) or 0),
            "Stato": "Liquidata",
            "Chiuso da": x.get("closed_by", ""),
        })
    return pd.DataFrame(hist)


def render_instructor_statement(data, instr, show_close_button=False, sha=None):
    sm = settlement_summary(data, instr)
    with st.container(border=True):
        st.markdown(f"### {instr}")
        a, b, c = st.columns(3)
        a.metric(f"Totale {instr}", f"€ {sm['total']:.2f}")
        b.metric("Incassato", f"€ {sm['paid_total']:.2f}")
        c.metric("Da incassare", f"€ {sm['unpaid_total']:.2f}")
        a, b, c = st.columns(3)
        a.metric(f"Guadagno {instr} 40%", f"€ {sm['inst_total']:.2f}")
        b.metric("Da liquidare ora", f"€ {sm['inst_paid']:.2f}")
        c.metric("Quota BodyCenter 60%", f"€ {sm['gym_total']:.2f}")
        if sm["all_rows"]:
            st.dataframe(current_settlement_df(sm["all_rows"]), use_container_width=True, hide_index=True)
        else:
            st.info("Nessun importo corrente non liquidato.")
        if show_close_button:
            st.caption("La liquidazione azzera solo le lezioni già pagate. Le lezioni non ancora pagate restano nel corrente.")
            if st.button(f"Liquida e azzera pagato {instr}", key=f"settle_{instr}", type="primary", use_container_width=is_mobile_client()):
                ok, msg = close_instructor_settlement(data, instr)
                if ok:
                    save_data(data, sha, f"Close settlement {instr}")
                    st.success(msg)
                    st.rerun()
                else:
                    st.info(msg)


def render_settlements(data, sha):
    st.subheader("Incassi e liquidazioni")
    if is_admin():
        summaries = {instr: settlement_summary(data, instr) for instr in INSTRUCTORS}
        total_incassi = sum(sm["total"] for sm in summaries.values())
        total_bodycenter = sum(sm["gym_total"] for sm in summaries.values())
        a, b = st.columns(2)
        a.metric("Totale incassi complessivi", f"€ {total_incassi:.2f}")
        b.metric("Totale BodyCenter 60%", f"€ {total_bodycenter:.2f}")
        metric_cols = st.columns(4)
        for i, instr in enumerate(INSTRUCTORS):
            sm = summaries[instr]
            metric_cols[i * 2].metric(f"Totale {instr}", f"€ {sm['total']:.2f}")
            metric_cols[i * 2 + 1].metric(f"Guadagno {instr} 40%", f"€ {sm['inst_total']:.2f}")
        paid_total = sum(sm["paid_total"] for sm in summaries.values())
        unpaid_total = sum(sm["unpaid_total"] for sm in summaries.values())
        st.caption(f"Di cui già incassato: € {paid_total:.2f} · ancora da incassare: € {unpaid_total:.2f}")
        for instr in INSTRUCTORS:
            render_instructor_statement(data, instr, show_close_button=True, sha=sha)
        hist_df = historical_settlement_df(data)
        st.markdown("### Storico liquidazioni")
        if not hist_df.empty:
            st.dataframe(hist_df, use_container_width=True, hide_index=True)
        else:
            st.info("Nessuna liquidazione storica presente.")
        return
    instr = instructor_name_from_user()
    if not instr:
        st.error("Utente istruttrice non associato.")
        return
    render_instructor_statement(data, instr, show_close_button=False, sha=sha)
    hist_df = historical_settlement_df(data, instr)
    st.markdown("### Storico liquidazioni")
    if not hist_df.empty:
        cols = ["Data liquidazione", "Incassato liquidato", "Quota istruttrice 40%", "Quota BodyCenter 60%", "Lezioni", "Stato"]
        st.dataframe(hist_df[cols], use_container_width=True, hide_index=True)
    else:
        st.info("Nessuna liquidazione storica presente.")


def render_instructor_archive(data):
    st.subheader("Archivio prenotazioni completo")
    rows = list(data.get("bookings", []))
    rows = sorted(rows, key=lambda b: (str(b.get("date", "")), str(b.get("time", ""))), reverse=True)
    valid = [b for b in rows if b.get("status") != "Annullata"]
    total = sum(money(b.get("amount", 0)) for b in valid)
    paid = sum(money(b.get("amount", 0)) for b in valid if to_bool(b.get("paid", False)))
    unpaid = total - paid
    a, b, c = st.columns(3)
    a.metric("Totale prenotazioni", f"€ {total:.2f}")
    b.metric("Incassato", f"€ {paid:.2f}")
    c.metric("Da incassare", f"€ {unpaid:.2f}")
    if not rows:
        st.info("Nessuna prenotazione presente.")
        return
    df = pd.DataFrame([{
        "Data": date_it(x.get("date")),
        "Ora": x.get("time", ""),
        "Cliente": x.get("name", ""),
        "Telefono": x.get("phone", ""),
        "Istruttrice": x.get("instructor", ""),
        "Stato prenotazione": x.get("status", ""),
        "Pagato": "Sì" if to_bool(x.get("paid", False)) else "No",
        "Importo totale": money(x.get("amount", 0)),
        "Quota istruttrice 40%": round(money(x.get("amount", 0)) * instructor_share(), 2),
        "Quota BodyCenter 60%": round(money(x.get("amount", 0)) * gym_share(), 2),
        "Liquidazione": "Liquidata" if x.get("settlement_id") else ("Da liquidare" if to_bool(x.get("paid", False)) else "Da incassare"),
        "Note": x.get("note", ""),
    } for x in rows])
    st.dataframe(df, use_container_width=True, hide_index=True)


def _planning_base_rows(data, days, instructor=None):
    today = date.today()
    end = today + timedelta(days=days)
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


def _planning_table(rows):
    return pd.DataFrame([{
        "Quando": f"{date_label_it(b.get('date'))} · {b.get('time','')}",
        "Istruttrice": b.get("instructor", ""),
        "Cliente": b.get("name", ""),
        "Telefono": b.get("phone", ""),
        "Stato": b.get("status", ""),
        "Pagato": "Sì" if to_bool(b.get("paid", False)) else "No",
        "Note": b.get("note", ""),
    } for b in rows])


def _render_planning_view(data, rows, title):
    st.markdown(f"### {title}")
    today_key = date.today().isoformat()
    today_rows = [b for b in rows if b.get("date") == today_key]
    week_limit = date.today() + timedelta(days=7)
    week_rows = []
    for b in rows:
        try:
            if parse_date(b.get("date")) <= week_limit:
                week_rows.append(b)
        except Exception:
            pass
    waiting = [b for b in rows if b.get("status") == "Lista attesa"]
    a, b, c = st.columns(3)
    a.metric("Oggi", len(today_rows))
    b.metric("Prossimi 7 giorni", len(week_rows))
    c.metric("Lista attesa", len(waiting))
    if not rows:
        st.info("Nessun prossimo impegno nel periodo selezionato.")
        return

    day_map = {}
    for r in rows:
        day_map.setdefault(r.get("date", ""), []).append(r)

    st.markdown("#### Planning per giorno")
    for day in sorted(day_map.keys()):
        day_rows = day_map[day]
        slot_map = {}
        for r in day_rows:
            key = (r.get("time", ""), r.get("instructor", ""))
            slot_map.setdefault(key, []).append(r)
        with st.container(border=True):
            st.markdown(f"### {date_label_it(day)}")
            for idx, ((t, instr), group) in enumerate(sorted(slot_map.items(), key=lambda item: (item[0][0], item[0][1]))):
                conf = [x for x in group if x.get("status") == "Confermata"]
                wait = [x for x in group if x.get("status") == "Lista attesa"]
                posti = max(CAPACITY - len(conf), 0)
                st.markdown(f"**{t} · {instr}**")
                st.caption(f"Confermate: {len(conf)}/{CAPACITY} · Posti liberi: {posti} · Attesa: {len(wait)}")
                st.write("; ".join([x.get("name", "") for x in conf]) or "Nessun confermato")
                if wait:
                    st.caption("Lista attesa: " + "; ".join([x.get("name", "") for x in wait]))
                if idx < len(slot_map) - 1:
                    st.divider()
    st.markdown("#### Elenco rapido")
    st.dataframe(_planning_table(rows), use_container_width=True, hide_index=True)


def render_planning(data):
    st.subheader("Planning prossimi impegni")
    giorni = st.selectbox("Periodo", [7, 14, 30, 60], index=1, format_func=lambda x: f"Prossimi {x} giorni")
    if is_admin():
        vista = st.selectbox("Vista", ["Tutte", *INSTRUCTORS], key="planning_admin_view")
        instr = None if vista == "Tutte" else vista
        _render_planning_view(data, _planning_base_rows(data, giorni, instr), f"Planning {vista}")
        return
    instr = instructor_name_from_user()
    tab_miei, tab_tutti = st.tabs(["I miei impegni", "Tutti gli impegni"])
    with tab_miei:
        _render_planning_view(data, _planning_base_rows(data, giorni, instr), f"Prossimi impegni {instr}")
    with tab_tutti:
        _render_planning_view(data, _planning_base_rows(data, giorni, None), "Planning completo")
'''

    boot = "\n\n# -----------------------------\n# App bootstrap"
    for token in ["\n\ndef settlement_bookings", "\n\ndef unsettled_bookings", "\n\ndef render_settlements", "\n\ndef render_planning"]:
        if token in s:
            start = s.index(token)
            end = s.index(boot, start)
            s = s[:start] + module_code + s[end:]
            break
    else:
        s = s.replace(boot, module_code + boot, 1)

    s = s.replace('''def render_archive(data, sha):
    if not is_admin():
        st.error("Archivio economico riservato a BodyCenter.")
        return
    if render_archive_open_client(data, sha):''', '''def render_archive(data, sha):
    if not is_admin():
        render_instructor_archive(data)
        return
    if render_archive_open_client(data, sha):''')
    s = s.replace('''def render_archive(data, sha):
    if render_archive_open_client(data, sha):''', '''def render_archive(data, sha):
    if not is_admin():
        render_instructor_archive(data)
        return
    if render_archive_open_client(data, sha):''')

    s = re.sub(r'\ncol_access, col_logout = st\.columns\(\[4, 1\]\).*?st\.rerun\(\)', '', s, flags=re.S)
    menu_block = '''allowed_sections = visible_sections()
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
        s = s[:m.start()] + menu_block + s[m.end():]

    dispatch = '''if section == "Planning":
    render_planning(data)
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
