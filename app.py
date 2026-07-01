import base64
import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

APP_TITLE = "Prenotazioni Pilates Reformer"
CAPACITY = 4
LOCAL_DATA_PATH = "data/bookings.json"
LOGO_PATH = "assets/logo.png"
INSTRUCTORS = ["Grazia", "Alice"]
DARK = "#243142"
GREEN = "#496744"

SCHEDULE = {
    0: ["08:30", "09:30", "10:30", "17:00", "18:00", "19:00"],
    1: ["09:30", "10:30", "11:30", "12:45", "14:30", "19:00"],
    2: ["08:30", "09:30", "10:30", "11:30", "12:45", "14:30", "15:30", "16:30", "17:30", "18:30"],
    3: ["17:00", "18:00", "19:00"],
    4: ["14:00", "15:00", "16:00", "17:00", "18:00", "19:00"],
}
DAY_ABBR = {0: "Lun", 1: "Mar", 2: "Mer", 3: "Gio", 4: "Ven", 5: "Sab", 6: "Dom"}
DAY_NAMES = {0: "Lunedì", 1: "Martedì", 2: "Mercoledì", 3: "Giovedì", 4: "Venerdì", 5: "Sabato", 6: "Domenica"}
MONTH_NAMES = {1: "gennaio", 2: "febbraio", 3: "marzo", 4: "aprile", 5: "maggio", 6: "giugno", 7: "luglio", 8: "agosto", 9: "settembre", 10: "ottobre", 11: "novembre", 12: "dicembre"}

# Questo nome serve solo a impedire ai vecchi patcher runtime di riscrivere il file.
def render_planning():
    return None


def bc_secret(name, default=""):
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return os.environ.get(name, default)


def bc_github_enabled():
    return bool(bc_secret("GITHUB_TOKEN") and bc_secret("GITHUB_REPO") and bc_secret("GITHUB_BRANCH", "main"))


def bc_github_url():
    repo = bc_secret("GITHUB_REPO")
    return "https://api.github.com/repos/" + repo + "/contents/" + LOCAL_DATA_PATH


def bc_headers():
    return {
        "Authorization": "Bearer " + bc_secret("GITHUB_TOKEN"),
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def bc_parse_date(value):
    if isinstance(value, date):
        return value
    s = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    return pd.to_datetime(s, dayfirst=True).date()


def bc_date_key(d):
    return bc_parse_date(d).isoformat()


def bc_date_it(value):
    try:
        return bc_parse_date(value).strftime("%d-%m-%Y")
    except Exception:
        return ""


def bc_date_label(value):
    try:
        d = bc_parse_date(value)
        return f"{DAY_ABBR.get(d.weekday(), '')} {d.day} {MONTH_NAMES.get(d.month, '')} {str(d.year)[-2:]}"
    except Exception:
        return str(value or "")


def bc_money(value):
    try:
        return round(float(value or 0), 2)
    except Exception:
        return 0.0


def bc_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "sì", "si", "yes", "y"}


def bc_id(prefix=""):
    return prefix + datetime.now().strftime("%Y%m%d%H%M%S%f")


def bc_norm(x):
    return re.sub(r"\s+", " ", str(x or "").strip().lower())


def bc_client_key(first, last):
    return f"{bc_norm(first)}|{bc_norm(last)}"


def bc_full_name(c):
    if not c:
        return ""
    return f"{str(c.get('last_name','')).strip()} {str(c.get('first_name','')).strip()}".strip()


def bc_split_name(name):
    parts = str(name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[1:]), parts[0]


def bc_times_for(d):
    return SCHEDULE.get(bc_parse_date(d).weekday(), [])


def bc_mobile():
    try:
        headers = getattr(st, "context", None).headers
        ua = str(headers.get("user-agent", headers.get("User-Agent", ""))).lower()
    except Exception:
        ua = ""
    return any(t in ua for t in ["iphone", "android", "mobile", "ipad", "ipod"])


def bc_users():
    raw = bc_secret("USERS", "").strip()
    if raw:
        try:
            users = json.loads(raw)
            return {str(k).lower().strip(): v for k, v in users.items() if isinstance(v, dict)}
        except Exception as e:
            st.error(f"Configurazione USERS non valida nei Secrets: {e}")
            st.stop()
    return {"bodycenter": {"password": bc_secret("APP_PASSWORD", "pilates123"), "role": "admin"}}


def bc_current_user():
    return st.session_state.get("current_user", "bodycenter")


def bc_current_role():
    return st.session_state.get("current_role", "admin")


def bc_is_admin():
    return bc_current_role() == "admin"


def bc_current_instructor():
    u = bc_current_user().lower().strip()
    for name in INSTRUCTORS:
        if name.lower() == u:
            return name
    return ""


def bc_instr_share():
    try:
        return float(bc_secret("INSTRUCTOR_SHARE", "0.40"))
    except Exception:
        return 0.40


def bc_gym_share():
    try:
        return float(bc_secret("GYM_SHARE", "0.60"))
    except Exception:
        return 0.60


def bc_sections():
    if bc_is_admin():
        return ["Planning", "Settimana", "Prenota", "Clienti", "Cerca", "Incassi", "Archivio"]
    return ["Planning", "Prenota", "Clienti", "Cerca", "Incassi"]


def bc_go(section):
    st.session_state["section"] = section
    st.rerun()


def bc_load_data():
    if bc_github_enabled():
        r = requests.get(bc_github_url(), headers=bc_headers(), params={"ref": bc_secret("GITHUB_BRANCH", "main")}, timeout=20)
        if r.status_code == 404:
            data = {"bookings": [], "clients": [], "settlements": []}
            bc_save_data(data, None, "Initialize storage")
            return data, None
        r.raise_for_status()
        payload = r.json()
        return json.loads(base64.b64decode(payload["content"]).decode()), payload.get("sha")
    p = Path(LOCAL_DATA_PATH)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"bookings": [], "clients": [], "settlements": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    return json.loads(p.read_text(encoding="utf-8")), None


def bc_save_data(data, sha=None, message="Update data"):
    if bc_github_enabled():
        body = {
            "message": message,
            "content": base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode()).decode(),
            "branch": bc_secret("GITHUB_BRANCH", "main"),
        }
        if sha:
            body["sha"] = sha
        r = requests.put(bc_github_url(), headers=bc_headers(), json=body, timeout=20)
        if r.status_code == 409:
            st.error("Conflitto dati: ricarica la pagina e riprova.")
            st.stop()
        r.raise_for_status()
        return
    Path(LOCAL_DATA_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(LOCAL_DATA_PATH).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def bc_ensure_data(data):
    data.setdefault("bookings", [])
    data.setdefault("clients", [])
    data.setdefault("settlements", [])
    for c in data["clients"]:
        c.setdefault("id", bc_id("c_"))
        c.setdefault("first_name", "")
        c.setdefault("last_name", "")
        c.setdefault("phone", "")
        c.setdefault("email", "")
        c.setdefault("notes", "")
        c.setdefault("birth_date", "")
        c.setdefault("created_at", "")
    keys = {bc_client_key(c.get("first_name", ""), c.get("last_name", "")): c for c in data["clients"]}
    for b in data["bookings"]:
        b.setdefault("id", bc_id("b_"))
        b.setdefault("amount", 0)
        b.setdefault("paid", False)
        b.setdefault("gift", False)
        b.setdefault("note", "")
        b.setdefault("instructor", "")
        b.setdefault("email", "")
        b.setdefault("status", "Confermata")
        b.setdefault("settlement_id", "")
        b.setdefault("date", date.today().isoformat())
        b.setdefault("time", "")
        b.setdefault("paid_to_gym_at", "")
        b.setdefault("paid_to_gym_by", "")
        if not b.get("client_id"):
            first, last = bc_split_name(b.get("name", ""))
            k = bc_client_key(first, last)
            if k.strip("|") and k in keys:
                b["client_id"] = keys[k]["id"]
            elif k.strip("|"):
                c = {"id": bc_id("c_"), "first_name": first, "last_name": last, "phone": b.get("phone", ""), "email": b.get("email", ""), "notes": "", "birth_date": "", "created_at": datetime.now().isoformat(timespec="seconds")}
                data["clients"].append(c)
                keys[k] = c
                b["client_id"] = c["id"]
    return data


def bc_get_client(data, cid):
    return next((c for c in data.get("clients", []) if c.get("id") == cid), None)


def bc_client_options(data):
    return sorted([f"{bc_full_name(c)} | {c.get('phone','')} | {c.get('email','')} | {c.get('id')}" for c in data.get("clients", [])], key=str.lower)


def bc_option_to_client_id(option):
    return option.split("|")[-1].strip()


def bc_add_client(data, first, last, phone="", email="", notes="", birth_date=""):
    first, last, phone = first.strip(), last.strip(), phone.strip()
    if not first or not last or not phone:
        return False, "Inserisci cognome, nome e telefono.", None
    k = bc_client_key(first, last)
    for c in data.get("clients", []):
        if bc_client_key(c.get("first_name", ""), c.get("last_name", "")) == k:
            return False, "Cliente già presente.", c.get("id")
    cid = bc_id("c_")
    data["clients"].append({"id": cid, "first_name": first, "last_name": last, "phone": phone, "email": email.strip(), "notes": notes.strip(), "birth_date": birth_date.strip(), "created_at": datetime.now().isoformat(timespec="seconds")})
    return True, "Cliente salvato.", cid


def bc_update_client(data, cid, first, last, phone, email, birth, notes):
    c = bc_get_client(data, cid)
    if not c:
        return False, "Cliente non trovato."
    c.update({"first_name": first.strip(), "last_name": last.strip(), "phone": phone.strip(), "email": email.strip(), "birth_date": birth.strip(), "notes": notes.strip()})
    for b in data.get("bookings", []):
        if b.get("client_id") == cid:
            b["name"] = bc_full_name(c)
            b["phone"] = c.get("phone", "")
            b["email"] = c.get("email", "")
    return True, "Scheda cliente aggiornata."


def bc_is_gift(b):
    return bool(b.get("gift", False)) or "omaggio" in str(b.get("note", "")).lower()


def bc_slot_rows(data, d, t, include_cancelled=False, instructor=None):
    rows = []
    for b in data.get("bookings", []):
        if b.get("date") != bc_date_key(d) or b.get("time") != t:
            continue
        if instructor and b.get("instructor") != instructor:
            continue
        if not include_cancelled and b.get("status") == "Annullata":
            continue
        rows.append(b)
    return sorted(rows, key=lambda x: x.get("created_at", ""))


def bc_confirmed_count(data, d, t, exclude_id=None, instructor=None):
    return sum(1 for b in bc_slot_rows(data, d, t, instructor=instructor) if b.get("status") == "Confermata" and b.get("id") != exclude_id)


def bc_auto_status(data, d, t, instructor=None):
    return "Confermata" if bc_confirmed_count(data, d, t, instructor=instructor) < CAPACITY else "Lista attesa"


def bc_create_booking(data, cid, d, t, amount, paid, instructor, note, gift=False):
    c = bc_get_client(data, cid)
    if not c:
        raise ValueError("Cliente non trovato.")
    amount = 0.0 if gift else bc_money(amount)
    paid = True if gift else bool(paid)
    clean_note = note.strip()
    if gift and "omaggio" not in clean_note.lower():
        clean_note = (clean_note + " | " if clean_note else "") + "Seduta omaggio / prova"
    b = {"id": bc_id("b_"), "created_at": datetime.now().isoformat(timespec="seconds"), "client_id": cid, "date": bc_date_key(d), "day": DAY_NAMES[bc_parse_date(d).weekday()], "time": t, "name": bc_full_name(c), "phone": c.get("phone", ""), "email": c.get("email", ""), "note": clean_note, "status": bc_auto_status(data, d, t, instructor), "amount": amount, "paid": paid, "gift": bool(gift), "paid_to_gym_at": datetime.now().isoformat(timespec="seconds") if paid and not gift else "", "paid_to_gym_by": bc_current_user() if paid and not gift else "", "settlement_id": "", "instructor": instructor, "created_by": bc_current_user()}
    data["bookings"].append(b)
    return b


def bc_open_cash_rows(data, instructor=None):
    rows = []
    for b in data.get("bookings", []):
        if b.get("status") == "Annullata" or b.get("settlement_id"):
            continue
        if instructor and b.get("instructor") != instructor:
            continue
        rows.append(b)
    return rows


def bc_mark_gym_collected(data, booking_id):
    for b in data.get("bookings", []):
        if b.get("id") == booking_id:
            if bc_is_gift(b):
                return False, "Seduta omaggio: non c'è incasso."
            b["paid"] = True
            b["paid_to_gym_at"] = datetime.now().isoformat(timespec="seconds")
            b["paid_to_gym_by"] = bc_current_user()
            return True, "Incasso segnato come pagato alla palestra."
    return False, "Prenotazione non trovata."


def bc_update_amount(data, booking_id, new_amount, note=""):
    for b in data.get("bookings", []):
        if b.get("id") == booking_id:
            if b.get("settlement_id"):
                return False, "Quota già chiusa: non posso modificare l'importo."
            if bc_is_gift(b):
                return False, "Seduta omaggio: importo bloccato a € 0."
            old = bc_money(b.get("amount", 0))
            new = bc_money(new_amount)
            b["amount"] = new
            b["amount_updated_at"] = datetime.now().isoformat(timespec="seconds")
            b["amount_updated_by"] = bc_current_user()
            log = f"Importo modificato da € {old:.2f} a € {new:.2f} da {bc_current_user()}"
            if note.strip():
                log += f" - {note.strip()}"
            b["note"] = (b.get("note", "") + " | " if b.get("note") else "") + log
            return True, f"Importo aggiornato: € {old:.2f} → € {new:.2f}."
    return False, "Prenotazione non trovata."


def bc_mark_share(data, booking_id):
    for b in data.get("bookings", []):
        if b.get("id") == booking_id:
            if bc_is_gift(b):
                return False, "Seduta omaggio: non genera quota istruttrice."
            if not bc_bool(b.get("paid", False)):
                return False, "Prima deve risultare incassato dalla palestra."
            if b.get("settlement_id"):
                return False, "Quota già chiusa."
            sid = bc_id("sett_")
            amount = bc_money(b.get("amount", 0))
            b["settlement_id"] = sid
            b["share_paid_at"] = datetime.now().isoformat(timespec="seconds")
            b["share_paid_by"] = bc_current_user()
            data.setdefault("settlements", []).append({"id": sid, "created_at": b["share_paid_at"], "instructor": b.get("instructor", ""), "gross_amount": round(amount, 2), "instructor_amount": round(amount * bc_instr_share(), 2), "gym_amount": round(amount * bc_gym_share(), 2), "lessons": 1, "closed_by": bc_current_user(), "booking_id": booking_id})
            return True, "Quota 40% segnata come pagata/ricevuta."
    return False, "Prenotazione non trovata."


def bc_cancel_booking(data, booking_id, note=""):
    for b in data.get("bookings", []):
        if b.get("id") == booking_id:
            if b.get("settlement_id"):
                return False, "Prenotazione già liquidata: non annullarla da qui."
            b["status"] = "Annullata"
            b["cancelled_at"] = datetime.now().isoformat(timespec="seconds")
            b["cancelled_by"] = bc_current_user()
            if note.strip():
                b["note"] = (b.get("note", "") + " | " if b.get("note") else "") + f"Annullata da {bc_current_user()}: {note.strip()}"
            return True, "Prenotazione annullata."
    return False, "Prenotazione non trovata."


def bc_pay_label(b):
    tag = " · OMAGGIO" if bc_is_gift(b) else f" · € {bc_money(b.get('amount', 0)):.2f}"
    return f"{bc_date_it(b.get('date'))} · {b.get('time','')} · {b.get('instructor','')} · {b.get('name','')}{tag}"


def bc_cash_df(rows):
    return pd.DataFrame([{"Data": bc_date_it(x.get("date")), "Ora": x.get("time", ""), "Istruttrice": x.get("instructor", ""), "Cliente": x.get("name", ""), "Tipo": "Seduta omaggio" if bc_is_gift(x) else "Pagamento", "Importo": bc_money(x.get("amount", 0)), "Incassato palestra": "Sì" if bc_bool(x.get("paid", False)) and not bc_is_gift(x) else ("Omaggio" if bc_is_gift(x) else "No"), "Quota 40%": round(bc_money(x.get("amount", 0)) * bc_instr_share(), 2) if not bc_is_gift(x) else 0.0, "Note": x.get("note", "")} for x in rows])


def bc_header():
    st.markdown(f"""
    <style>
    .main .block-container {{max-width: 1350px; padding-top: 1.1rem;}}
    .bc-header {{display:flex; align-items:center; gap:28px; padding:24px 34px; border-radius:0 0 28px 28px; background:linear-gradient(90deg,#f1faf4,#f7fbf9); border:1px solid #dce9df; box-shadow:0 12px 32px rgba(36,49,66,.08); margin-bottom:20px;}}
    .bc-logo {{width:112px; max-height:112px; object-fit:contain;}}
    .bc-title {{font-size:44px; font-weight:800; color:{DARK}; line-height:1.05;}}
    .bc-subtitle {{font-size:17px; color:#5b6775; margin-top:14px;}}
    @media(max-width:700px) {{.bc-header{{padding:18px;gap:14px}}.bc-logo{{width:72px}}.bc-title{{font-size:28px}}.bc-subtitle{{font-size:14px}}}}
    </style>
    """, unsafe_allow_html=True)
    logo_html = ""
    if Path(LOGO_PATH).exists():
        encoded = base64.b64encode(Path(LOGO_PATH).read_bytes()).decode()
        logo_html = f"<img class='bc-logo' src='data:image/png;base64,{encoded}'>"
    st.markdown(f"<div class='bc-header'>{logo_html}<div><div class='bc-title'>{APP_TITLE}</div><div class='bc-subtitle'>Gestionale interno Body Center · clienti, prenotazioni, pagamenti</div></div></div>", unsafe_allow_html=True)


def bc_login():
    if st.session_state.get("authenticated", False):
        return True
    users = bc_users()
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
                bc_go("Planning")
            else:
                st.error("Utente o password non corretti")
    return False


def bc_render_incassi(data, sha):
    instr = None if bc_is_admin() else bc_current_instructor()
    rows = bc_open_cash_rows(data, instr)
    pay_rows = [b for b in rows if not bc_is_gift(b)]
    gift_rows = [b for b in rows if bc_is_gift(b)]
    da_incassare = [b for b in pay_rows if not bc_bool(b.get("paid", False))]
    incassati = [b for b in pay_rows if bc_bool(b.get("paid", False))]
    totale = sum(bc_money(b.get("amount", 0)) for b in pay_rows)
    da_incassare_tot = sum(bc_money(b.get("amount", 0)) for b in da_incassare)
    incassato = sum(bc_money(b.get("amount", 0)) for b in incassati)
    quota = incassato * bc_instr_share()

    st.subheader("Incassi")
    a, b, c, d = st.columns(4)
    a.metric("Incasso totale", f"€ {totale:.2f}")
    b.metric("Da incassare", f"€ {da_incassare_tot:.2f}")
    c.metric("Incassato dalla palestra", f"€ {incassato:.2f}")
    d.metric("Sedute omaggio", len(gift_rows))
    st.caption("Dopo ogni salvataggio questa schermata resta in Incassi: niente ritorno alla settimana.")

    editable = sorted(pay_rows, key=lambda x: (str(x.get("date", "")), str(x.get("time", "")), str(x.get("name", ""))))
    with st.expander("Modifica importo prenotazione / pacchetto sedute", expanded=True):
        st.caption("Esempio: cliente inserita a €30, poi paga più sedute: modifica l'importo totale a €140.")
        if editable:
            j = st.selectbox("Prenotazione da modificare", range(len(editable)), format_func=lambda k: bc_pay_label(editable[k]), key="edit_amount_select")
            current_amount = bc_money(editable[j].get("amount", 0))
            new_amount = st.number_input("Nuovo importo totale (€)", min_value=0.0, value=float(current_amount), step=1.0, format="%.2f", key="edit_amount_value")
            note_amount = st.text_input("Nota opzionale", placeholder="es. pacchetto 5 sedute", key="edit_amount_note")
            if st.button("Aggiorna importo", key="edit_amount_btn", use_container_width=bc_mobile()):
                ok, msg = bc_update_amount(data, editable[j].get("id"), new_amount, note_amount)
                if ok:
                    st.session_state["section"] = "Incassi"
                    bc_save_data(data, sha, "Update booking amount")
                    st.success(msg)
                    bc_go("Incassi")
                else:
                    st.error(msg)
        else:
            st.info("Nessuna prenotazione con importo modificabile.")

    st.markdown("#### 1. Da incassare")
    if da_incassare:
        st.dataframe(bc_cash_df(da_incassare), use_container_width=True, hide_index=True)
        i = st.selectbox("Seleziona pagamento incassato dalla palestra", range(len(da_incassare)), format_func=lambda k: bc_pay_label(da_incassare[k]), key="cash_collect_select")
        if st.button("Segna come incassato dalla palestra", key="cash_collect_btn", use_container_width=bc_mobile()):
            ok, msg = bc_mark_gym_collected(data, da_incassare[i].get("id"))
            if ok:
                st.session_state["section"] = "Incassi"
                bc_save_data(data, sha, "Mark gym cash collected")
                st.success(msg)
                bc_go("Incassi")
            else:
                st.error(msg)
    else:
        st.success("Nessun importo da incassare.")

    st.markdown("#### 2. Incassati dalla palestra")
    if incassati:
        st.metric("Totale incassato dalla palestra", f"€ {incassato:.2f}")
        st.dataframe(bc_cash_df(incassati), use_container_width=True, hide_index=True)
    else:
        st.info("Nessun incasso registrato dalla palestra.")

    st.markdown("#### 3. Quota 40% da pagare/ricevere")
    if incassati:
        label = "Totale quota 40% da pagare" if bc_is_admin() else "Totale quota 40% da ricevere"
        button_label = "Segna quota 40% pagata ad Alice/Grazia" if bc_is_admin() else "Segna quota 40% ricevuta"
        st.metric(label, f"€ {quota:.2f}")
        st.dataframe(bc_cash_df(incassati), use_container_width=True, hide_index=True)
        k = st.selectbox("Seleziona quota 40%", range(len(incassati)), format_func=lambda x: bc_pay_label(incassati[x]) + f" · quota € {bc_money(incassati[x].get('amount',0))*bc_instr_share():.2f}", key="share_select")
        if st.button(button_label, key="share_button", use_container_width=bc_mobile()):
            ok, msg = bc_mark_share(data, incassati[k].get("id"))
            if ok:
                st.session_state["section"] = "Incassi"
                bc_save_data(data, sha, "Mark instructor share paid")
                st.success(msg)
                bc_go("Incassi")
            else:
                st.error(msg)
    else:
        st.info("Nessuna quota da pagare/ricevere: prima il pagamento deve essere incassato dalla palestra.")

    st.markdown("#### 4. Sedute omaggio")
    if gift_rows:
        st.dataframe(bc_cash_df(gift_rows), use_container_width=True, hide_index=True)
    else:
        st.info("Nessuna seduta omaggio registrata.")

    hist = []
    for x in data.get("settlements", []):
        if instr and x.get("instructor") != instr:
            continue
        hist.append({"Data": x.get("created_at", ""), "Istruttrice": x.get("instructor", ""), "Quota 40%": bc_money(x.get("instructor_amount", 0)), "Quota BodyCenter 60%": bc_money(x.get("gym_amount", 0)), "Lezioni": int(x.get("lessons", 0) or 0)})
    st.markdown("### Storico quote 40% già pagate/ricevute")
    if hist:
        st.dataframe(pd.DataFrame(hist), use_container_width=True, hide_index=True)
    else:
        st.info("Nessuna quota già chiusa.")


def bc_render_booking(data, sha):
    st.subheader("Prenota")
    mode = st.radio("Cliente", ["Seleziona da archivio", "Nuovo cliente"], horizontal=True)
    cid = None
    if mode == "Seleziona da archivio":
        opts = bc_client_options(data)
        if opts:
            cid = bc_option_to_client_id(st.selectbox("Cliente", opts))
            c = bc_get_client(data, cid)
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
            ok, msg, cid = bc_add_client(data, first, last, phone, email, notes, birth)
            if ok:
                bc_save_data(data, sha, "Add client")
                bc_go("Prenota")
            else:
                st.error(msg)
    if cid:
        st.markdown("### Dati prenotazione")
        a, b = st.columns(2)
        d = bc_parse_date(a.date_input("Data", value=date.today(), min_value=date.today(), format="DD/MM/YYYY", key="booking_date"))
        ts = bc_times_for(d)
        if not ts:
            st.warning("Nessun orario previsto per questa data.")
            return
        t = b.selectbox("Orario", ts)
        default_instr = bc_current_instructor()
        default_index = INSTRUCTORS.index(default_instr) if default_instr in INSTRUCTORS else 0
        a, b, c = st.columns(3)
        gift = a.checkbox("Seduta omaggio / prova gratuita", key="booking_gift")
        amount = b.number_input("Importo (€)", min_value=0.0, value=0.0, step=1.0, format="%.2f", disabled=gift)
        paid = c.checkbox("Già incassato dalla palestra", disabled=gift)
        instr = st.selectbox("Istruttrice", INSTRUCTORS, index=default_index)
        note = st.text_area("Note prenotazione")
        n = bc_confirmed_count(data, d, t, instructor=instr)
        st.info(f"{instr} · {t}: {n}/{CAPACITY} confermate · stato: {'Seduta omaggio' if gift else bc_auto_status(data, d, t, instr)}")
        if st.button("Salva prenotazione", type="primary"):
            bk = bc_create_booking(data, cid, d, t, amount, paid, instr, note, gift=gift)
            bc_save_data(data, sha, f"Add booking {bk['name']}")
            bc_go("Planning")


def bc_planning_rows(data, days, instructor=None):
    today = date.today()
    end = today + timedelta(days=days - 1)
    out = []
    for b in data.get("bookings", []):
        if b.get("status") == "Annullata":
            continue
        if instructor and b.get("instructor") != instructor:
            continue
        try:
            d = bc_parse_date(b.get("date"))
        except Exception:
            continue
        if today <= d <= end:
            out.append(b)
    return sorted(out, key=lambda x: (str(x.get("date", "")), str(x.get("time", "")), str(x.get("instructor", "")), str(x.get("name", ""))))


def bc_h(x):
    return str(x or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def bc_planning_table(rows):
    return pd.DataFrame([{"Quando": f"{bc_date_label(b.get('date'))} · {b.get('time','')}", "Istruttrice": b.get("instructor", ""), "Cliente": b.get("name", ""), "Telefono": b.get("phone", ""), "Tipo": "Omaggio" if bc_is_gift(b) else "Pagamento", "Importo": bc_money(b.get("amount", 0)), "Incassato palestra": "Sì" if bc_bool(b.get("paid", False)) and not bc_is_gift(b) else ("Omaggio" if bc_is_gift(b) else "No")} for b in rows])


def bc_cancel_box(data, sha):
    rows = []
    for b in data.get("bookings", []):
        if b.get("status") == "Annullata" or b.get("settlement_id"):
            continue
        try:
            if bc_parse_date(b.get("date")) >= date.today():
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
            lab = f"{bc_date_it(b.get('date'))} · {b.get('time','')} · {b.get('instructor','')} · {b.get('name','')}"
            labels.append(lab)
            mp[lab] = b.get("id")
        choice = st.selectbox("Prenotazione", labels, key="cancel_booking_select")
        note = st.text_input("Motivo / nota opzionale", key="cancel_booking_note")
        okc = st.checkbox("Confermo l'annullamento", key="cancel_booking_confirm")
        if st.button("Annulla prenotazione selezionata", key="cancel_booking_button", type="secondary", use_container_width=bc_mobile()):
            if not okc:
                st.warning("Spunta la conferma prima di annullare.")
                return
            ok, msg = bc_cancel_booking(data, mp[choice], note)
            if ok:
                bc_save_data(data, sha, "Cancel booking")
                st.success(msg)
                bc_go("Planning")
            else:
                st.error(msg)


def bc_render_planning_grid(rows, title, days=14, show_instructor=True):
    st.markdown(f"### {title}")
    today = date.today()
    all_days = [(today + timedelta(days=i)).isoformat() for i in range(days)]
    by_day = {d: [] for d in all_days}
    for r in rows:
        by_day.setdefault(r.get("date", ""), []).append(r)
    a, b, c = st.columns(3)
    a.metric("Oggi", len([x for x in rows if x.get("date") == today.isoformat()]))
    b.metric(f"Prossimi {days} giorni", len(rows))
    c.metric("Omaggio", len([x for x in rows if bc_is_gift(x)]))
    cards = []
    for d in all_days:
        slot = {}
        for r in by_day.get(d, []):
            slot.setdefault((r.get("time", ""), r.get("instructor", "")), []).append(r)
        lines = []
        for (t, instr), group in sorted(slot.items(), key=lambda x: (x[0][0], x[0][1])):
            conf = [x for x in group if x.get("status") == "Confermata"]
            wait = [x for x in group if x.get("status") == "Lista attesa"]
            names = ", ".join([x.get("name", "") + (" (omaggio)" if bc_is_gift(x) else "") for x in conf]) or "—"
            instr_txt = f" <span>{bc_h(instr)}</span>" if show_instructor and instr else ""
            lines.append(f"<div class='slot'><b>{bc_h(t)}</b>{instr_txt} <em>{len(conf)}/{CAPACITY} · lib {max(CAPACITY-len(conf),0)}" + (f" · att {len(wait)}" if wait else "") + f"</em><br><small>{bc_h(names)}</small></div>")
        body = "".join(lines) if lines else "<div class='empty-text'>—</div>"
        cards.append(f"<div class='day-card{' empty' if not lines else ''}'><div class='day-title'>{bc_h(bc_date_label(d))}</div>{body}</div>")
    css = """
    <style>.plan-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:7px}.day-card{border:1px solid #d9dde3;border-radius:10px;padding:8px 10px;background:#fff;min-height:76px}.day-card.empty{background:#fafafa;color:#9aa0a6}.day-title{font-weight:700;font-size:.92rem;margin-bottom:5px}.slot{font-size:.84rem;line-height:1.18;margin:3px 0 5px;padding-bottom:4px;border-bottom:1px solid #eef0f2}.slot:last-child{border-bottom:0}.slot em{font-style:normal;color:#707782;font-size:.78rem}.slot small{font-size:.78rem}</style>
    """
    st.markdown(css + "<div class='plan-grid'>" + "".join(cards) + "</div>", unsafe_allow_html=True)
    if rows:
        with st.expander("Elenco rapido", expanded=False):
            st.dataframe(bc_planning_table(rows), use_container_width=True, hide_index=True)


def bc_render_planning(data, sha):
    st.subheader("Planning 14 giorni")
    bc_cancel_box(data, sha)
    with st.expander("Gestione incassi rapida", expanded=False):
        bc_render_incassi(data, sha)
    giorni = 14
    if bc_is_admin():
        vista = st.selectbox("Vista", ["Tutte", *INSTRUCTORS], key="planning_admin_view")
        instr = None if vista == "Tutte" else vista
        bc_render_planning_grid(bc_planning_rows(data, giorni, instr), f"Planning {vista}", giorni, show_instructor=True)
        return
    instr = bc_current_instructor()
    tab_all, tab_miei = st.tabs(["Planning completo", "I miei impegni"])
    with tab_all:
        bc_render_planning_grid(bc_planning_rows(data, giorni, None), "Planning completo", giorni, show_instructor=True)
    with tab_miei:
        bc_render_planning_grid(bc_planning_rows(data, giorni, instr), f"Prossimi impegni {instr}", giorni, show_instructor=False)


def bc_render_week(data, sha):
    st.subheader("Vista settimanale")
    start = st.date_input("Scegli la data di partenza", value=date.today(), format="DD/MM/YYYY")
    monday = bc_parse_date(start) - timedelta(days=bc_parse_date(start).weekday())
    for i in range(5):
        d = monday + timedelta(days=i)
        with st.container(border=True):
            st.markdown(f"### {bc_date_label(d)}")
            any_rows = False
            for t in bc_times_for(d):
                rows = bc_slot_rows(data, d, t)
                if rows:
                    any_rows = True
                    st.dataframe(pd.DataFrame([{"Ora": t, "Istruttrice": b.get("instructor", ""), "Cliente": b.get("name", ""), "Stato": b.get("status", ""), "Tipo": "Omaggio" if bc_is_gift(b) else "Pagamento", "Importo": bc_money(b.get("amount", 0)), "Incassato": "Sì" if bc_bool(b.get("paid", False)) else "No"} for b in rows]), use_container_width=True, hide_index=True)
            if not any_rows:
                st.caption("Nessuna prenotazione")


def bc_render_clients(data, sha):
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
            ok, msg, _ = bc_add_client(data, first, last, phone, email, notes, birth)
            if ok:
                bc_save_data(data, sha, "Add client")
                bc_go("Clienti")
            else:
                st.error(msg)
    df = pd.DataFrame([{"ID": c.get("id"), "Cognome": c.get("last_name", ""), "Nome": c.get("first_name", ""), "Telefono": c.get("phone", ""), "Email": c.get("email", ""), "Note": c.get("notes", "")} for c in data.get("clients", [])])
    if not df.empty:
        st.dataframe(df.drop(columns=["ID"], errors="ignore").sort_values(["Cognome", "Nome"]), use_container_width=True, hide_index=True)
    else:
        st.info("Nessun cliente.")
    opts = bc_client_options(data)
    if opts:
        st.markdown("### Modifica scheda cliente")
        cid = bc_option_to_client_id(st.selectbox("Cliente da modificare", opts, key="edit_client_select"))
        c = bc_get_client(data, cid)
        a, b = st.columns(2)
        last = a.text_input("Cognome", value=c.get("last_name", ""), key="edit_last")
        first = b.text_input("Nome", value=c.get("first_name", ""), key="edit_first")
        x, y = st.columns(2)
        phone = x.text_input("Telefono", value=c.get("phone", ""), key="edit_phone")
        email = y.text_input("Email", value=c.get("email", ""), key="edit_email")
        birth = st.text_input("Data di nascita", value=c.get("birth_date", ""), key="edit_birth")
        notes = st.text_area("Note", value=c.get("notes", ""), key="edit_notes")
        if st.button("Salva scheda cliente", key="save_client_edit"):
            ok, msg = bc_update_client(data, cid, first, last, phone, email, birth, notes)
            if ok:
                bc_save_data(data, sha, "Update client")
                bc_go("Clienti")
            else:
                st.error(msg)


def bc_render_search(data):
    st.subheader("Cerca")
    q = st.text_input("Cerca cliente, telefono, istruttrice, nota").strip().lower()
    rows = []
    for b in data.get("bookings", []):
        hay = " ".join(str(b.get(k, "")) for k in ["name", "phone", "email", "instructor", "note", "date", "time"]).lower()
        if not q or q in hay:
            rows.append({"Data": bc_date_it(b.get("date")), "Ora": b.get("time", ""), "Cliente": b.get("name", ""), "Telefono": b.get("phone", ""), "Istruttrice": b.get("instructor", ""), "Stato": b.get("status", ""), "Importo": bc_money(b.get("amount", 0)), "Tipo": "Omaggio" if bc_is_gift(b) else "Pagamento", "Note": b.get("note", "")})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def bc_render_archive(data, sha):
    st.subheader("Archivio prenotazioni")
    rows = []
    for b in data.get("bookings", []):
        rows.append({"Data": bc_date_it(b.get("date")), "Ora": b.get("time", ""), "Cliente": b.get("name", ""), "Telefono": b.get("phone", ""), "Istruttrice": b.get("instructor", ""), "Stato": b.get("status", ""), "Tipo": "Omaggio" if bc_is_gift(b) else "Pagamento", "Importo": bc_money(b.get("amount", 0)), "Incassato palestra": "Sì" if bc_bool(b.get("paid", False)) and not bc_is_gift(b) else ("Omaggio" if bc_is_gift(b) else "No"), "Quota chiusa": "Sì" if b.get("settlement_id") else "No", "Note": b.get("note", "")})
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("Archivio vuoto.")


def bc_run():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    bc_header()
    if not bc_login():
        return
    data, sha = bc_load_data()
    data = bc_ensure_data(data)
    allowed = bc_sections()
    if "section" not in st.session_state or st.session_state["section"] not in allowed:
        st.session_state["section"] = "Planning"
    section = st.radio("Sezione", allowed, horizontal=True, key="section", label_visibility="collapsed")
    col_access, col_logout = st.columns([4, 1])
    with col_access:
        st.caption(f"Accesso: {bc_current_user().capitalize()} · {'Admin' if bc_is_admin() else 'Istruttrice'}")
    with col_logout:
        if st.button("Logout", key="logout_user_button", use_container_width=True):
            for k in ["authenticated", "current_user", "current_role", "section"]:
                st.session_state.pop(k, None)
            st.rerun()
    st.divider()
    dispatch = {"Planning": bc_render_planning, "Settimana": bc_render_week, "Prenota": bc_render_booking, "Clienti": bc_render_clients, "Cerca": lambda d, s: bc_render_search(d), "Incassi": bc_render_incassi, "Archivio": bc_render_archive}
    dispatch[section](data, sha)


bc_run()
