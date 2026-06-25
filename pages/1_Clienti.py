import base64
import html
import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st

DATA_PATH = "data/bookings.json"
LOGO_PATH = "assets/logo.png"


def get_secret(name, default=""):
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return os.environ.get(name, default)


def github_enabled():
    return bool(get_secret("GITHUB_TOKEN") and get_secret("GITHUB_REPO") and get_secret("GITHUB_BRANCH", "main"))


def headers():
    return {"Authorization": f"Bearer {get_secret('GITHUB_TOKEN')}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


def url():
    return f"https://api.github.com/repos/{get_secret('GITHUB_REPO')}/contents/{DATA_PATH}"


def load_data():
    if github_enabled():
        r = requests.get(url(), headers=headers(), params={"ref": get_secret("GITHUB_BRANCH", "main")}, timeout=20)
        r.raise_for_status()
        p = r.json()
        return json.loads(base64.b64decode(p["content"]).decode("utf-8")), p.get("sha")
    p = Path(DATA_PATH)
    return json.loads(p.read_text(encoding="utf-8")), None


def save_data(data, sha):
    if github_enabled():
        body = {
            "message": "Update client record",
            "content": base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode()).decode(),
            "branch": get_secret("GITHUB_BRANCH", "main"),
            "sha": sha,
        }
        r = requests.put(url(), headers=headers(), json=body, timeout=20)
        r.raise_for_status()
    else:
        Path(DATA_PATH).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_date(value):
    if isinstance(value, date):
        return value
    s = str(value or "").strip()
    if not s:
        raise ValueError("empty date")
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return pd.to_datetime(s, dayfirst=True).date()


def date_it(value):
    try:
        return parse_date(value).strftime("%d-%m-%Y")
    except Exception:
        return ""


def norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def key(first, last):
    return f"{norm(first)}|{norm(last)}"


def full_name(c):
    return f"{c.get('last_name', '').strip()} {c.get('first_name', '').strip()}".strip()


def age_from_birth(value):
    if not value:
        return ""
    try:
        b = parse_date(value)
        today = date.today()
        return today.year - b.year - ((today.month, today.day) < (b.month, b.day))
    except Exception:
        return ""


def last_visit(data, client_id):
    dates = []
    for b in data.get("bookings", []):
        if b.get("client_id") == client_id and b.get("status") != "Annullata":
            try:
                dates.append(parse_date(b.get("date")))
            except Exception:
                pass
    return max(dates) if dates else None


def ensure_clients(data):
    data.setdefault("clients", [])
    data.setdefault("bookings", [])
    for c in data["clients"]:
        c.setdefault("birth_date", "")
        c.setdefault("notes", "")
        c.setdefault("anamnesis", "")
        c.setdefault("goals", "")
        c.setdefault("phone", "")
        c.setdefault("email", "")
    return data


def clients_table(data, sort_by):
    rows = []
    for c in data.get("clients", []):
        lv = last_visit(data, c.get("id"))
        rows.append({"ID": c.get("id"), "Cognome": c.get("last_name", ""), "Nome": c.get("first_name", ""), "Ultima lezione": date_it(lv) if lv else "", "_last": lv or date(1900, 1, 1)})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    if sort_by == "Ultima visita":
        return df.sort_values(["_last", "Cognome", "Nome"], ascending=[False, True, True]).reset_index(drop=True)
    return df.sort_values(["Cognome", "Nome"]).reset_index(drop=True)


def get_client(data, cid):
    return next((c for c in data.get("clients", []) if c.get("id") == cid), None)


def update_client(data, cid, first, last, phone, email, birth, notes, anamnesis, goals):
    c = get_client(data, cid)
    if not c:
        return False, "Cliente non trovato."
    first = first.strip()
    last = last.strip()
    if not first or not last:
        return False, "Nome e cognome sono obbligatori."
    new_key = key(first, last)
    for other in data.get("clients", []):
        if other.get("id") != cid and key(other.get("first_name", ""), other.get("last_name", "")) == new_key:
            return False, "Esiste già un altro cliente con lo stesso nome e cognome."
    c.update({"first_name": first, "last_name": last, "phone": phone.strip(), "email": email.strip(), "birth_date": birth.strip(), "notes": notes.strip(), "anamnesis": anamnesis.strip(), "goals": goals.strip()})
    for b in data.get("bookings", []):
        if b.get("client_id") == cid:
            b["name"] = full_name(c)
            b["phone"] = c.get("phone", "")
            b["email"] = c.get("email", "")
    return True, "Scheda cliente aggiornata."


st.set_page_config(page_title="Archivio clienti", page_icon="👤", layout="wide")

if Path(LOGO_PATH).exists():
    st.image(LOGO_PATH, width=110)
st.title("Archivio clienti")
st.caption("Clicca una riga della tabella per aprire direttamente la scheda cliente.")

pwd = st.sidebar.text_input("Password", type="password")
if pwd != get_secret("APP_PASSWORD", "pilates123"):
    st.info("Inserisci la password nella barra laterale.")
    st.stop()

try:
    data, sha = load_data()
    data = ensure_clients(data)
except Exception as e:
    st.error(f"Errore caricamento dati: {e}")
    st.stop()

sort_by = st.radio("Ordina per", ["Alfabetico", "Ultima visita"], horizontal=True)
q = st.text_input("Cerca cliente").strip().lower()
df = clients_table(data, sort_by)
if q and not df.empty:
    df = df[df.apply(lambda r: q in " ".join(map(str, r.values)).lower(), axis=1)].reset_index(drop=True)

if df.empty:
    st.info("Nessun cliente presente.")
    st.stop()

visible_df = df[["Cognome", "Nome", "Ultima lezione"]]
event = st.dataframe(
    visible_df,
    use_container_width=True,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    key="client_row_selection",
)

selected_rows = []
try:
    selected_rows = event.selection.rows
except Exception:
    selected_rows = []

if not selected_rows:
    st.info("Seleziona una riga della tabella per aprire la scheda cliente.")
    st.stop()

selected_id = df.iloc[selected_rows[0]]["ID"]
c = get_client(data, selected_id)
if not c:
    st.error("Cliente non trovato.")
    st.stop()

st.subheader(f"Scheda anagrafica: {full_name(c)}")
a, b = st.columns(2)
last = a.text_input("Cognome", value=c.get("last_name", ""))
first = b.text_input("Nome", value=c.get("first_name", ""))
a, b, c3 = st.columns(3)
phone = a.text_input("Telefono", value=c.get("phone", ""))
email = b.text_input("Email", value=c.get("email", ""))
birth = c3.text_input("Data di nascita", value=date_it(c.get("birth_date", "")), placeholder="gg-mm-aaaa")
st.caption(f"Età: {age_from_birth(birth) if birth else ''}")
notes = st.text_area("Note cliente", value=c.get("notes", ""))
anamnesis = st.text_area("Anamnesi / problematiche", value=c.get("anamnesis", ""), height=140)
goals = st.text_area("Obiettivi", value=c.get("goals", ""), height=100)

if st.button("Salva scheda cliente", type="primary"):
    ok, msg = update_client(data, selected_id, first, last, phone, email, birth, notes, anamnesis, goals)
    if ok:
        save_data(data, sha)
        st.success(msg)
        st.rerun()
    else:
        st.error(msg)

history = []
for bkg in data.get("bookings", []):
    if bkg.get("client_id") == selected_id:
        history.append({"Data": date_it(bkg.get("date")), "Ora": bkg.get("time", ""), "Istruttrice": bkg.get("instructor", ""), "Stato": bkg.get("status", ""), "Importo": bkg.get("amount", 0), "Pagato": bool(bkg.get("paid", False)), "Note": bkg.get("note", "")})
if history:
    st.markdown("### Storico lezioni")
    st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True)
