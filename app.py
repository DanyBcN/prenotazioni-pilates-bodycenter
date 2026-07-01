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


def secret(name, default=""):
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return os.environ.get(name, default)


def github_enabled():
    return bool(secret("GITHUB_TOKEN") and secret("GITHUB_REPO") and secret("GITHUB_BRANCH", "main"))


def github_url():
    return "https://api.github.com/repos/" + secret("GITHUB_REPO") + "/contents/" + LOCAL_DATA_PATH


def github_headers():
    return {
        "Authorization": "Bearer " + secret("GITHUB_TOKEN"),
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def parse_date(value):
    if isinstance(value, date):
        return value
    s = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    return pd.to_datetime(s, dayfirst=True).date()


def date_key(d):
    return parse_date(d).isoformat()


def date_it(value):
    try:
        return parse_date(value).strftime("%d-%m-%Y")
    except Exception:
        return ""


def date_label(value):
    try:
        d = parse_date(value)
        return f"{DAY_ABBR.get(d.weekday(), '')} {d.day} {MONTH_NAMES.get(d.month, '')} {str(d.year)[-2:]}"
    except Exception:
        return str(value or "")


def money(value):
    try:
        return round(float(value or 0), 2)
    except Exception:
        return 0.0


def as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "sì", "si", "yes", "y"}


def new_id(prefix=""):
    return prefix + datetime.now().strftime("%Y%m%d%H%M%S%f")


def norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def client_key(first, last):
    return f"{norm(first)}|{norm(last)}"


def full_name(c):
    if not c:
        return ""
    return f"{str(c.get('last_name','')).strip()} {str(c.get('first_name','')).strip()}".strip()


def split_name(name):
    parts = str(name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[1:]), parts[0]


def times_for(d):
    return SCHEDULE.get(parse_date(d).weekday(), [])


def is_mobile():
    try:
        headers = getattr(st, "context", None).headers
        ua = str(headers.get("user-agent", headers.get("User-Agent", ""))).lower()
    except Exception:
        ua = ""
    return any(x in ua for x in ["iphone", "android", "mobile", "ipad", "ipod"])


def users_config():
    raw = secret("USERS", "").strip()
    if raw:
        try:
            users = json.loads(raw)
            return {str(k).lower().strip(): v for k, v in users.items() if isinstance(v, dict)}
        except Exception as e:
            st.error(f"Configurazione USERS non valida nei Secrets: {e}")
            st.stop()
    return {"bodycenter": {"password": secret("APP_PASSWORD", "pilates123"), "role": "admin"}}


def current_user():
    return st.session_state.get("current_user", "bodycenter")


def current_role():
    return st.session_state.get("current_role", "admin")


def is_admin():
    return current_role() == "admin"


def current_instructor():
    u = current_user().lower().strip()
    for name in INSTRUCTORS:
        if name.lower() == u:
            return name
    return ""


def instructor_share():
    try:
        return float(secret("INSTRUCTOR_SHARE", "0.40"))
    except Exception:
        return 0.40


def gym_share():
    try:
        return float(secret("GYM_SHARE", "0.60"))
    except Exception:
        return 0.60


def sections():
    if is_admin():
        return ["Planning", "Prenota", "Incassi", "Clienti", "Cerca", "Archivio"]
    return ["Planning", "Prenota", "Incassi", "Clienti"]


def go(section):
    st.session_state["_next_section"] = section
    st.rerun()


def load_data():
    if github_enabled():
        r = requests.get(github_url(), headers=github_headers(), params={"ref": secret("GITHUB_BRANCH", "main")}, timeout=20)
        if r.status_code == 404:
            data = {"bookings": [], "clients": [], "settlements": []}
            save_data(data, None, "Initialize storage")
            return data, None
        r.raise_for_status()
        payload = r.json()
        return json.loads(base64.b64decode(payload["content"]).decode()), payload.get("sha")
    p = Path(LOCAL_DATA_PATH)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"bookings": [], "clients": [], "settlements": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    return json.loads(p.read_text(encoding="utf-8")), None


def save_data(data, sha=None, message="Update data"):
    if github_enabled():
        body = {
            "message": message,
            "content": base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode()).decode(),
            "branch": secret("GITHUB_BRANCH", "main"),
        }
        if sha:
            body["sha"] = sha
        r = requests.put(github_url(), headers=github_headers(), json=body, timeout=20)
        if r.status_code == 409:
            st.error("Conflitto dati: ricarica la pagina e riprova.")
            st.stop()
        r.raise_for_status()
        return
    Path(LOCAL_DATA_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(LOCAL_DATA_PATH).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_data(data):
    data.setdefault("bookings", [])
    data.setdefault("clients", [])
    data.setdefault("settlements", [])
    for c in data["clients"]:
        c.setdefault("id", new_id("c_"))
        c.setdefault("first_name", "")
        c.setdefault("last_name", "")
        c.setdefault("phone", "")
        c.setdefault("email", "")
        c.setdefault("notes", "")
        c.setdefault("birth_date", "")
        c.setdefault("created_at", "")
    keys = {client_key(c.get("first_name", ""), c.get("last_name", "")): c for c in data["clients"]}
    for b in data["bookings"]:
        b.setdefault("id", new_id("b_"))
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
            first, last = split_name(b.get("name", ""))
            k = client_key(first, last)
            if k.strip("|") and k in keys:
                b["client_id"] = keys[k]["id"]
            elif k.strip("|"):
                c = {"id": new_id("c_"), "first_name": first, "last_name": last, "phone": b.get("phone", ""), "email": b.get("email", ""), "notes": "", "birth_date": "", "created_at": datetime.now().isoformat(timespec="seconds")}
                data["clients"].append(c)
                keys[k] = c
                b["client_id"] = c["id"]
    return data


def get_client(data, cid):
    return next((c for c in data.get("clients", []) if c.get("id") == cid), None)


def client_options(data):
    return sorted([f"{full_name(c)} | {c.get('phone','')} | {c.get('email','')} | {c.get('id')}" for c in data.get("clients", [])], key=str.lower)


def option_to_client_id(option):
    return option.split("|")[-1].strip()


def add_client(data, first, last, phone="", email="", notes="", birth_date=""):
    first, last, phone = first.strip(), last.strip(), phone.strip()
    if not first or not last or not phone:
        return False, "Inserisci cognome, nome e telefono.", None
    k = client_key(first, last)
    for c in data.get("clients", []):
        if client_key(c.get("first_name", ""), c.get("last_name", "")) == k:
            return False, "Cliente già presente.", c.get("id")
    cid = new_id("c_")
    data["clients"].append({"id": cid, "first_name": first, "last_name": last, "phone": phone, "email": email.strip(), "notes": notes.strip(), "birth_date": birth_date.strip(), "created_at": datetime.now().isoformat(timespec="seconds")})
    return True, "Cliente salvato.", cid


def update_client(data, cid, first, last, phone, email, birth, notes):
    c = get_client(data, cid)
    if not c:
        return False, "Cliente non trovato."
    c.update({"first_name": first.strip(), "last_name": last.strip(), "phone": phone.strip(), "email": email.strip(), "birth_date": birth.strip(), "notes": notes.strip()})
    for b in data.get("bookings", []):
        if b.get("client_id") == cid:
            b["name"] = full_name(c)
            b["phone"] = c.get("phone", "")
            b["email"] = c.get("email", "")
    return True, "Scheda cliente aggiornata."


def is_gift(b):
    return bool(b.get("gift", False)) or "omaggio" in str(b.get("note", "")).lower()


def slot_rows(data, d, t, include_cancelled=False, instructor=None):
    rows = []
    for b in data.get("bookings", []):
        if b.get("date") != date_key(d) or b.get("time") != t:
            continue
        if instructor and b.get("instructor") != instructor:
            continue
        if not include_cancelled and b.get("status") == "Annullata":
            continue
        rows.append(b)
    return sorted(rows, key=lambda x: x.get("created_at", ""))


def confirmed_count(data, d, t, exclude_id=None, instructor=None):
    return sum(1 for b in slot_rows(data, d, t, instructor=instructor) if b.get("status") == "Confermata" and b.get("id") != exclude_id)


def auto_status(data, d, t, instructor=None):
    return "Confermata" if confirmed_count(data, d, t, instructor=instructor) < CAPACITY else "Lista attesa"


def create_booking(data, cid, d, t, amount, paid, instructor, note, gift=False):
    c = get_client(data, cid)
    if not c:
        raise ValueError("Cliente non trovato.")
    amount = 0.0 if gift else money(amount)
    paid = True if gift else bool(paid)
    clean_note = note.strip()
    if gift and "omaggio" not in clean_note.lower():
        clean_note = (clean_note + " | " if clean_note else "") + "Seduta omaggio / prova"
    b = {"id": new_id("b_"), "created_at": datetime.now().isoformat(timespec="seconds"), "client_id": cid, "date": date_key(d), "day": DAY_NAMES[parse_date(d).weekday()], "time": t, "name": full_name(c), "phone": c.get("phone", ""), "email": c.get("email", ""), "note": clean_note, "status": auto_status(data, d, t, instructor), "amount": amount, "paid": paid, "gift": bool(gift), "paid_to_gym_at": datetime.now().isoformat(timespec="seconds") if paid and not gift else "", "paid_to_gym_by": current_user() if paid and not gift else "", "settlement_id": "", "instructor": instructor, "created_by": current_user()}
    data["bookings"].append(b)
    return b


def open_rows(data, instructor=None):
    rows = []
    for b in data.get("bookings", []):
        if b.get("status") == "Annullata" or b.get("settlement_id"):
            continue
        if instructor and b.get("instructor") != instructor:
            continue
        rows.append(b)
    return rows


def mark_paid(data, booking_id):
    for b in data.get("bookings", []):
        if b.get("id") == booking_id:
            if is_gift(b):
                return False, "Seduta omaggio: non c'è incasso."
            b["paid"] = True
            b["paid_to_gym_at"] = datetime.now().isoformat(timespec="seconds")
            b["paid_to_gym_by"] = current_user()
            return True, "Pagamento segnato come incassato dalla palestra."
    return False, "Prenotazione non trovata."


def update_amount(data, booking_id, new_amount, note=""):
    for b in data.get("bookings", []):
        if b.get("id") == booking_id:
            if b.get("settlement_id"):
                return False, "Quota già chiusa: non posso modificare l'importo."
            if is_gift(b):
                return False, "Seduta omaggio: togli prima la spunta omaggio."
            old = money(b.get("amount", 0))
            new = money(new_amount)
            b["amount"] = new
            b["amount_updated_at"] = datetime.now().isoformat(timespec="seconds")
            b["amount_updated_by"] = current_user()
            log = f"Importo modificato da € {old:.2f} a € {new:.2f} da {current_user()}"
            if note.strip():
                log += f" - {note.strip()}"
            b["note"] = (b.get("note", "") + " | " if b.get("note") else "") + log
            return True, "Importo aggiornato."
    return False, "Prenotazione non trovata."


def mark_gift(data, booking_id, note=""):
    for b in data.get("bookings", []):
        if b.get("id") == booking_id:
            if b.get("settlement_id"):
                return False, "Quota già chiusa: non posso trasformarla in omaggio."
            b["gift"] = True
            b["amount"] = 0.0
            b["paid"] = True
            b["paid_to_gym_at"] = ""
            b["paid_to_gym_by"] = current_user()
            b["amount_updated_at"] = datetime.now().isoformat(timespec="seconds")
            b["amount_updated_by"] = current_user()
            log = "Segnata come seduta omaggio / prova gratuita"
            if note.strip():
                log += f" - {note.strip()}"
            if "omaggio" not in str(b.get("note", "")).lower():
                b["note"] = (b.get("note", "") + " | " if b.get("note") else "") + log
            return True, "Prenotazione segnata come omaggio."
    return False, "Prenotazione non trovata."


def unmark_gift(data, booking_id, new_amount, paid=False, note=""):
    for b in data.get("bookings", []):
        if b.get("id") == booking_id:
            if b.get("settlement_id"):
                return False, "Quota già chiusa: non posso modificarla."
            b["gift"] = False
            b["amount"] = money(new_amount)
            b["paid"] = bool(paid)
            b["paid_to_gym_at"] = datetime.now().isoformat(timespec="seconds") if paid else ""
            b["paid_to_gym_by"] = current_user() if paid else ""
            b["amount_updated_at"] = datetime.now().isoformat(timespec="seconds")
            b["amount_updated_by"] = current_user()
            log = f"Tolto omaggio e impostato importo € {money(new_amount):.2f} da {current_user()}"
            if note.strip():
                log += f" - {note.strip()}"
            b["note"] = (b.get("note", "") + " | " if b.get("note") else "") + log
            return True, "Omaggio tolto e importo aggiornato."
    return False, "Prenotazione non trovata."


def mark_share(data, booking_id):
    for b in data.get("bookings", []):
        if b.get("id") == booking_id:
            if is_gift(b):
                return False, "Seduta omaggio: non genera quota istruttrice."
            if not as_bool(b.get("paid", False)):
                return False, "Prima deve risultare incassato dalla palestra."
            if b.get("settlement_id"):
                return False, "Quota già chiusa."
            sid = new_id("sett_")
            amount = money(b.get("amount", 0))
            b["settlement_id"] = sid
            b["share_paid_at"] = datetime.now().isoformat(timespec="seconds")
            b["share_paid_by"] = current_user()
            data.setdefault("settlements", []).append({"id": sid, "created_at": b["share_paid_at"], "instructor": b.get("instructor", ""), "gross_amount": round(amount, 2), "instructor_amount": round(amount * instructor_share(), 2), "gym_amount": round(amount * gym_share(), 2), "lessons": 1, "closed_by": current_user(), "booking_id": booking_id})
            return True, "Quota 40% segnata come pagata/ricevuta."
    return False, "Prenotazione non trovata."


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


def row_label(b):
    tag = " · OMAGGIO" if is_gift(b) else f" · € {money(b.get('amount', 0)):.2f}"
    return f"{date_it(b.get('date'))} · {b.get('time','')} · {b.get('instructor','')} · {b.get('name','')}{tag}"


def table_df(rows):
    return pd.DataFrame([{"Data": date_it(x.get("date")), "Ora": x.get("time", ""), "Istruttrice": x.get("instructor", ""), "Cliente": x.get("name", ""), "Tipo": "Omaggio" if is_gift(x) else "Pagamento", "Importo": money(x.get("amount", 0)), "Incassato palestra": "Sì" if as_bool(x.get("paid", False)) and not is_gift(x) else ("Omaggio" if is_gift(x) else "No"), "Quota 40%": round(money(x.get("amount", 0)) * instructor_share(), 2) if not is_gift(x) else 0.0, "Note": x.get("note", "")} for x in rows])


def header():
    st.markdown(f"""
    <style>
    .main .block-container {{max-width: 1350px; padding-top: 1.1rem;}}
    .bc-header {{display:flex; align-items:center; gap:28px; padding:22px 32px; border-radius:0 0 28px 28px; background:linear-gradient(90deg,#f1faf4,#f7fbf9); border:1px solid #dce9df; box-shadow:0 12px 32px rgba(36,49,66,.08); margin-bottom:18px;}}
    .bc-logo {{width:104px; max-height:104px; object-fit:contain;}}
    .bc-title {{font-size:42px; font-weight:800; color:{DARK}; line-height:1.05;}}
    .bc-subtitle {{font-size:17px; color:#5b6775; margin-top:12px;}}
    @media(max-width:700px) {{.bc-header{{padding:16px;gap:12px}}.bc-logo{{width:68px}}.bc-title{{font-size:26px}}.bc-subtitle{{font-size:13px}}}}
    </style>
    """, unsafe_allow_html=True)
    logo = ""
    if Path(LOGO_PATH).exists():
        encoded = base64.b64encode(Path(LOGO_PATH).read_bytes()).decode()
        logo = f"<img class='bc-logo' src='data:image/png;base64,{encoded}'>"
    st.markdown(f"<div class='bc-header'>{logo}<div><div class='bc-title'>{APP_TITLE}</div><div class='bc-subtitle'>Gestionale Body Center · prenotazioni e incassi</div></div></div>", unsafe_allow_html=True)


def login():
    if st.session_state.get("authenticated", False):
        return True
    users = users_config()
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
                go("Planning")
            else:
                st.error("Utente o password non corretti")
    return False


def render_incassi(data, sha):
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

    st.subheader("Incassi")
    a, b, c, d = st.columns(4)
    a.metric("Totale aperto", f"€ {totale:.2f}")
    b.metric("Da incassare", f"€ {da_incassare:.2f}")
    c.metric("Incassato palestra", f"€ {incassato:.2f}")
    d.metric("Omaggio", len(gift_rows))

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
                    ok, msg = mark_gift(data, selected.get("id"), note)
                elif current_gift and not gift_now:
                    ok, msg = unmark_gift(data, selected.get("id"), new_amount, mark_now, note)
                else:
                    ok, msg = update_amount(data, selected.get("id"), new_amount, note)
                    if ok and mark_now and not as_bool(selected.get("paid", False)):
                        ok, msg = mark_paid(data, selected.get("id"))
                if ok:
                    save_data(data, sha, "Save booking payment status")
                    st.success("Salvato.")
                    go("Incassi")
                else:
                    st.error(msg)
        else:
            st.info("Nessuna prenotazione modificabile.")

    st.markdown("### Quota 40%")
    with st.container(border=True):
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
    with st.expander("Storico quote già chiuse", expanded=False):
        st.dataframe(pd.DataFrame(hist), use_container_width=True, hide_index=True) if hist else st.info("Nessuna quota chiusa.")


def render_booking(data, sha):
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
                save_data(data, sha, "Add client")
                go("Prenota")
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
        default_instr = current_instructor()
        default_index = INSTRUCTORS.index(default_instr) if default_instr in INSTRUCTORS else 0
        a, b, c = st.columns(3)
        gift = a.checkbox("Seduta omaggio / prova gratuita", key="booking_gift")
        amount = b.number_input("Importo (€)", min_value=0.0, value=0.0, step=1.0, format="%.2f", disabled=gift)
        paid = c.checkbox("Già incassato dalla palestra", disabled=gift)
        instr = st.selectbox("Istruttrice", INSTRUCTORS, index=default_index)
        note = st.text_area("Note prenotazione")
        n = confirmed_count(data, d, t, instructor=instr)
        st.info(f"{instr} · {t}: {n}/{CAPACITY} confermate · stato: {'Seduta omaggio' if gift else auto_status(data, d, t, instr)}")
        if st.button("Salva prenotazione", type="primary"):
            bk = create_booking(data, cid, d, t, amount, paid, instr, note, gift=gift)
            save_data(data, sha, f"Add booking {bk['name']}")
            go("Planning")


def planning_rows(data, days, instructor=None):
    today = date.today()
    end = today + timedelta(days=days - 1)
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


def html_escape(x):
    return str(x or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def planning_table(rows):
    return pd.DataFrame([{"Quando": f"{date_label(b.get('date'))} · {b.get('time','')}", "Istruttrice": b.get("instructor", ""), "Cliente": b.get("name", ""), "Telefono": b.get("phone", ""), "Tipo": "Omaggio" if is_gift(b) else "Pagamento", "Importo": money(b.get("amount", 0)), "Incassato palestra": "Sì" if as_bool(b.get("paid", False)) and not is_gift(b) else ("Omaggio" if is_gift(b) else "No")} for b in rows])


def cancel_box(data, sha):
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
        if st.button("Annulla prenotazione selezionata", key="cancel_booking_button", type="secondary", use_container_width=is_mobile()):
            if not okc:
                st.warning("Spunta la conferma prima di annullare.")
                return
            ok, msg = cancel_booking(data, mp[choice], note)
            if ok:
                save_data(data, sha, "Cancel booking")
                st.success(msg)
                go("Planning")
            else:
                st.error(msg)


def render_planning_grid(rows, title, days=14, show_instructor=True):
    st.markdown(f"### {title}")
    today = date.today()
    all_days = [(today + timedelta(days=i)).isoformat() for i in range(days)]
    by_day = {d: [] for d in all_days}
    for r in rows:
        by_day.setdefault(r.get("date", ""), []).append(r)
    a, b, c = st.columns(3)
    a.metric("Oggi", len([x for x in rows if x.get("date") == today.isoformat()]))
    b.metric(f"Prossimi {days} giorni", len(rows))
    c.metric("Omaggio", len([x for x in rows if is_gift(x)]))
    cards = []
    for d in all_days:
        slot = {}
        for r in by_day.get(d, []):
            slot.setdefault((r.get("time", ""), r.get("instructor", "")), []).append(r)
        lines = []
        for (t, instr), group in sorted(slot.items(), key=lambda x: (x[0][0], x[0][1])):
            conf = [x for x in group if x.get("status") == "Confermata"]
            wait = [x for x in group if x.get("status") == "Lista attesa"]
            names = ", ".join([x.get("name", "") + (" (omaggio)" if is_gift(x) else "") for x in conf]) or "—"
            instr_txt = f" <span>{html_escape(instr)}</span>" if show_instructor and instr else ""
            lines.append(f"<div class='slot'><b>{html_escape(t)}</b>{instr_txt} <em>{len(conf)}/{CAPACITY} · lib {max(CAPACITY-len(conf),0)}" + (f" · att {len(wait)}" if wait else "") + f"</em><br><small>{html_escape(names)}</small></div>")
        body = "".join(lines) if lines else "<div class='empty-text'>—</div>"
        cards.append(f"<div class='day-card{' empty' if not lines else ''}'><div class='day-title'>{html_escape(date_label(d))}</div>{body}</div>")
    css = """
    <style>.plan-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:7px}.day-card{border:1px solid #d9dde3;border-radius:10px;padding:8px 10px;background:#fff;min-height:76px}.day-card.empty{background:#fafafa;color:#9aa0a6}.day-title{font-weight:700;font-size:.92rem;margin-bottom:5px}.slot{font-size:.84rem;line-height:1.18;margin:3px 0 5px;padding-bottom:4px;border-bottom:1px solid #eef0f2}.slot:last-child{border-bottom:0}.slot em{font-style:normal;color:#707782;font-size:.78rem}.slot small{font-size:.78rem}</style>
    """
    st.markdown(css + "<div class='plan-grid'>" + "".join(cards) + "</div>", unsafe_allow_html=True)
    if rows:
        with st.expander("Elenco rapido", expanded=False):
            st.dataframe(planning_table(rows), use_container_width=True, hide_index=True)


def render_planning(data, sha):
    st.subheader("Planning 14 giorni")
    if st.button("Apri Incassi", type="primary", use_container_width=is_mobile()):
        go("Incassi")
    cancel_box(data, sha)
    giorni = 14
    if is_admin():
        vista = st.selectbox("Vista", ["Tutte", *INSTRUCTORS], key="planning_admin_view")
        instr = None if vista == "Tutte" else vista
        render_planning_grid(planning_rows(data, giorni, instr), f"Planning {vista}", giorni, show_instructor=True)
        return
    instr = current_instructor()
    tab_all, tab_miei = st.tabs(["Planning completo", "I miei impegni"])
    with tab_all:
        render_planning_grid(planning_rows(data, giorni, None), "Planning completo", giorni, show_instructor=True)
    with tab_miei:
        render_planning_grid(planning_rows(data, giorni, instr), f"Prossimi impegni {instr}", giorni, show_instructor=False)


def render_clients(data, sha):
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
        cid = option_to_client_id(st.selectbox("Cliente da modificare", opts, key="edit_client_select"))
        c = get_client(data, cid)
        a, b = st.columns(2)
        last = a.text_input("Cognome", value=c.get("last_name", ""), key="edit_last")
        first = b.text_input("Nome", value=c.get("first_name", ""), key="edit_first")
        x, y = st.columns(2)
        phone = x.text_input("Telefono", value=c.get("phone", ""), key="edit_phone")
        email = y.text_input("Email", value=c.get("email", ""), key="edit_email")
        birth = st.text_input("Data di nascita", value=c.get("birth_date", ""), key="edit_birth")
        notes = st.text_area("Note", value=c.get("notes", ""), key="edit_notes")
        if st.button("Salva scheda cliente", key="save_client_edit"):
            ok, msg = update_client(data, cid, first, last, phone, email, birth, notes)
            if ok:
                save_data(data, sha, "Update client")
                go("Clienti")
            else:
                st.error(msg)


def render_search(data):
    st.subheader("Cerca")
    q = st.text_input("Cerca cliente, telefono, istruttrice, nota").strip().lower()
    rows = []
    for b in data.get("bookings", []):
        hay = " ".join(str(b.get(k, "")) for k in ["name", "phone", "email", "instructor", "note", "date", "time"]).lower()
        if not q or q in hay:
            rows.append({"Data": date_it(b.get("date")), "Ora": b.get("time", ""), "Cliente": b.get("name", ""), "Telefono": b.get("phone", ""), "Istruttrice": b.get("instructor", ""), "Stato": b.get("status", ""), "Importo": money(b.get("amount", 0)), "Tipo": "Omaggio" if is_gift(b) else "Pagamento", "Note": b.get("note", "")})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_archive(data, sha):
    st.subheader("Archivio prenotazioni")
    rows = []
    for b in data.get("bookings", []):
        rows.append({"Data": date_it(b.get("date")), "Ora": b.get("time", ""), "Cliente": b.get("name", ""), "Telefono": b.get("phone", ""), "Istruttrice": b.get("instructor", ""), "Stato": b.get("status", ""), "Tipo": "Omaggio" if is_gift(b) else "Pagamento", "Importo": money(b.get("amount", 0)), "Incassato palestra": "Sì" if as_bool(b.get("paid", False)) and not is_gift(b) else ("Omaggio" if is_gift(b) else "No"), "Quota chiusa": "Sì" if b.get("settlement_id") else "No", "Note": b.get("note", "")})
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("Archivio vuoto.")


def run():
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
    dispatch[section](data, sha)


run()
