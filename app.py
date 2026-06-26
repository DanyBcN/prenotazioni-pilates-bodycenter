import base64
import json
import os
import re
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

APP_TITLE = "Prenotazioni Pilates Reformer"
CAPACITY = 4
LOCAL_DATA_PATH = "data/bookings.json"
LOGO_PATH = "assets/logo.png"
INSTRUCTORS = ["Grazia", "Alice"]
GREEN = "#496744"
DARK = "#243142"
LIGHT_GREEN = "#eef6f2"
SECTIONS = ["Settimana", "Prenota", "Clienti", "Cerca", "Archivio"]

SCHEDULE = {
    0: ["08:30", "09:30", "10:30", "17:00", "18:00", "19:00"],
    1: ["09:30", "10:30", "11:30", "12:45", "14:30", "19:00"],
    2: ["08:30", "09:30", "10:30", "11:30", "12:45", "14:30", "15:30", "16:30", "17:30", "18:30"],
    3: ["17:00", "18:00", "19:00"],
    4: ["14:00", "15:00", "16:00", "17:00", "18:00", "19:00"],
}
DAY_NAMES = {0: "Lunedì", 1: "Martedì", 2: "Mercoledì", 3: "Giovedì", 4: "Venerdì", 5: "Sabato", 6: "Domenica"}
DAY_ABBR = {0: "Lun", 1: "Mar", 2: "Mer", 3: "Gio", 4: "Ven", 5: "Sab", 6: "Dom"}
MONTH_NAMES = {1: "gennaio", 2: "febbraio", 3: "marzo", 4: "aprile", 5: "maggio", 6: "giugno", 7: "luglio", 8: "agosto", 9: "settembre", 10: "ottobre", 11: "novembre", 12: "dicembre"}


# -----------------------------
# Base helpers
# -----------------------------

def get_secret(name, default=""):
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return os.environ.get(name, default)


def github_enabled():
    return bool(get_secret("GITHUB_TOKEN") and get_secret("GITHUB_REPO") and get_secret("GITHUB_BRANCH", "main"))


def github_headers():
    return {
        "Auth" + "orization": ("B" + "earer ") + get_secret("GITHUB_TOKEN"),
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def github_file_url():
    return f"https://api.github.com/repos/{get_secret('GITHUB_REPO')}/contents/{LOCAL_DATA_PATH}"


def save_data(data, sha=None, message="Update data"):
    if github_enabled():
        body = {
            "message": message,
            "content": base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode()).decode(),
            "branch": get_secret("GITHUB_BRANCH", "main"),
        }
        if sha:
            body["sha"] = sha
        r = requests.put(github_file_url(), headers=github_headers(), json=body, timeout=20)
        if r.status_code == 409:
            st.error("Conflitto dati: ricarica la pagina e riprova.")
            st.stop()
        r.raise_for_status()
        return

    Path(LOCAL_DATA_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(LOCAL_DATA_PATH).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_data():
    if github_enabled():
        r = requests.get(
            github_file_url(),
            headers=github_headers(),
            params={"ref": get_secret("GITHUB_BRANCH", "main")},
            timeout=20,
        )
        if r.status_code == 404:
            data = {"bookings": [], "clients": []}
            save_data(data, None, "Initialize storage")
            return data, None
        r.raise_for_status()
        payload = r.json()
        return json.loads(base64.b64decode(payload["content"]).decode()), payload.get("sha")

    p = Path(LOCAL_DATA_PATH)
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"bookings": [], "clients": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    return json.loads(p.read_text(encoding="utf-8")), None


def parse_date(value):
    if isinstance(value, date):
        return value
    s = str(value or "").strip()
    if not s:
        raise ValueError("data vuota")
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return pd.to_datetime(s, dayfirst=True).date()


def date_key(d):
    return d.isoformat()


def date_it(value):
    try:
        return parse_date(value).strftime("%d-%m-%Y")
    except Exception:
        return ""


def date_label_it(value):
    try:
        d = parse_date(value)
        return f"{DAY_ABBR.get(d.weekday(), '')} {d.day} {MONTH_NAMES.get(d.month, d.strftime('%m'))} {str(d.year)[-2:]}"
    except Exception:
        return str(value or "")


def money(value):
    try:
        return round(float(value or 0), 2)
    except Exception:
        return 0.0


def to_bool(value):
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
    return f"{str(c.get('last_name', '')).strip()} {str(c.get('first_name', '')).strip()}".strip()


def split_name(name):
    parts = str(name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[1:]), parts[0]


def age_from_birth(value):
    if not value:
        return ""
    try:
        b = parse_date(value)
        today = date.today()
        return today.year - b.year - ((today.month, today.day) < (b.month, b.day))
    except Exception:
        return ""


def is_mobile_client():
    try:
        headers = getattr(st, "context", None).headers
        ua = str(headers.get("user-agent", headers.get("User-Agent", ""))).lower()
    except Exception:
        ua = ""
    return any(t in ua for t in ["iphone", "android", "mobile", "ipad", "ipod"])


# -----------------------------
# Data model
# -----------------------------

def get_client(data, cid):
    return next((c for c in data.get("clients", []) if c.get("id") == cid), None)


def ensure_data(data):
    data.setdefault("bookings", [])
    data.setdefault("clients", [])

    for c in data["clients"]:
        c.setdefault("id", new_id("c_"))
        c.setdefault("first_name", "")
        c.setdefault("last_name", "")
        c.setdefault("phone", "")
        c.setdefault("email", "")
        c.setdefault("notes", "")
        c.setdefault("birth_date", "")
        c.setdefault("anamnesis", "")
        c.setdefault("goals", "")
        c.setdefault("created_at", "")

    keys = {client_key(c.get("first_name", ""), c.get("last_name", "")): c for c in data["clients"]}
    for b in data["bookings"]:
        b.setdefault("id", new_id("b_"))
        b.setdefault("amount", 0)
        b.setdefault("paid", False)
        b.setdefault("note", "")
        b.setdefault("instructor", "")
        b.setdefault("email", "")
        b.setdefault("status", "Confermata")
        b.setdefault("date", date.today().isoformat())
        b.setdefault("time", "")
        if b.get("client_id"):
            continue
        first, last = split_name(b.get("name", ""))
        k = client_key(first, last)
        if k.strip("|") and k in keys:
            b["client_id"] = keys[k]["id"]
        elif k.strip("|"):
            c = {
                "id": new_id("c_"),
                "first_name": first,
                "last_name": last,
                "phone": b.get("phone", ""),
                "email": b.get("email", ""),
                "notes": "",
                "birth_date": "",
                "anamnesis": "",
                "goals": "",
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            data["clients"].append(c)
            keys[k] = c
            b["client_id"] = c["id"]
    return data


def client_options(data):
    return sorted(
        [f"{full_name(c)} | {c.get('phone','')} | {c.get('email','')} | {c.get('id')}" for c in data.get("clients", [])],
        key=str.lower,
    )


def option_to_client_id(option):
    return option.split("|")[-1].strip()


def add_client(data, first, last, phone="", email="", notes="", birth_date="", anamnesis="", goals=""):
    first, last, phone = first.strip(), last.strip(), phone.strip()
    if not first or not last or not phone:
        return False, "Inserisci cognome, nome e telefono.", None
    k = client_key(first, last)
    for c in data.get("clients", []):
        if client_key(c.get("first_name", ""), c.get("last_name", "")) == k:
            return False, "Cliente già presente: nome e cognome devono essere univoci.", c.get("id")
    cid = new_id("c_")
    data["clients"].append({
        "id": cid,
        "first_name": first,
        "last_name": last,
        "phone": phone,
        "email": email.strip(),
        "notes": notes.strip(),
        "birth_date": birth_date.strip(),
        "anamnesis": anamnesis.strip(),
        "goals": goals.strip(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    })
    return True, "Cliente salvato.", cid


def update_client_record(data, cid, first, last, phone, email, birth, notes, anamnesis, goals):
    c = get_client(data, cid)
    if not c:
        return False, "Cliente non trovato."
    first, last = first.strip(), last.strip()
    if not first or not last:
        return False, "Nome e cognome sono obbligatori."
    k = client_key(first, last)
    for other in data.get("clients", []):
        if other.get("id") != cid and client_key(other.get("first_name", ""), other.get("last_name", "")) == k:
            return False, "Esiste già un altro cliente con lo stesso nome e cognome."

    c.update({
        "first_name": first,
        "last_name": last,
        "phone": phone.strip(),
        "email": email.strip(),
        "birth_date": birth.strip(),
        "notes": notes.strip(),
        "anamnesis": anamnesis.strip(),
        "goals": goals.strip(),
    })
    for b in data.get("bookings", []):
        if b.get("client_id") == cid:
            b["name"] = full_name(c)
            b["phone"] = c.get("phone", "")
            b["email"] = c.get("email", "")
    return True, "Scheda cliente aggiornata."


def last_visit(data, cid):
    dates = []
    for b in data.get("bookings", []):
        if b.get("client_id") == cid and b.get("status") != "Annullata":
            try:
                dates.append(parse_date(b.get("date")))
            except Exception:
                pass
    return max(dates) if dates else None


def clients_df(data, sort_by="Alfabetico"):
    rows = []
    for c in data.get("clients", []):
        lv = last_visit(data, c.get("id"))
        rows.append({
            "ID": c.get("id"),
            "Cognome": c.get("last_name", ""),
            "Nome": c.get("first_name", ""),
            "Telefono": c.get("phone", ""),
            "Email": c.get("email", ""),
            "Ultima lezione": date_it(lv) if lv else "",
            "_last": lv or date(1900, 1, 1),
        })
    if not rows:
        return pd.DataFrame(columns=["ID", "Cognome", "Nome", "Telefono", "Email", "Ultima lezione", "_last"])
    df = pd.DataFrame(rows)
    if sort_by == "Ultima visita":
        return df.sort_values(["_last", "Cognome", "Nome"], ascending=[False, True, True]).reset_index(drop=True)
    return df.sort_values(["Cognome", "Nome"]).reset_index(drop=True)


# -----------------------------
# Bookings
# -----------------------------

def times_for(d):
    return SCHEDULE.get(d.weekday(), [])


def next_days(start, n=5):
    out, d = [], start
    while len(out) < n:
        if d.weekday() in SCHEDULE:
            out.append(d)
        d += timedelta(days=1)
    return out


def slot_rows(data, d, t, include_cancelled=False):
    return sorted(
        [b for b in data.get("bookings", []) if b.get("date") == date_key(d) and b.get("time") == t and (include_cancelled or b.get("status") != "Annullata")],
        key=lambda x: x.get("created_at", ""),
    )


def confirmed_count(data, d, t, exclude_id=None):
    return sum(1 for b in slot_rows(data, d, t) if b.get("status") == "Confermata" and b.get("id") != exclude_id)


def auto_status(data, d, t):
    return "Confermata" if confirmed_count(data, d, t) < CAPACITY else "Lista attesa"


def slot_status(data, d, t):
    rows = slot_rows(data, d, t)
    conf = [b for b in rows if b.get("status") == "Confermata"]
    wait = [b for b in rows if b.get("status") == "Lista attesa"]
    return len(conf), len(wait), conf, wait


def status_icon(status):
    return {"Confermata": "✅", "Lista attesa": "⏳", "Annullata": "❌"}.get(status, "")


def create_booking(data, cid, d, t, amount, paid, instructor, note):
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
        "status": auto_status(data, d, t),
        "amount": money(amount),
        "paid": bool(paid),
        "instructor": instructor,
        "created_by": "staff",
    }
    data["bookings"].append(b)
    return b


def change_status(data, bid, status):
    for b in data.get("bookings", []):
        if b.get("id") == bid:
            d, t = parse_date(b["date"]), b["time"]
            if status == "Confermata" and confirmed_count(data, d, t, bid) >= CAPACITY:
                st.error("Lezione già piena (4/4).")
                return False
            b["status"] = status
            return True
    return False


def delete_bookings(data, ids):
    ids = set(ids)
    old = len(data.get("bookings", []))
    data["bookings"] = [b for b in data.get("bookings", []) if b.get("id") not in ids]
    return old - len(data["bookings"])


# -----------------------------
# Archive / export
# -----------------------------

def archive_df(data):
    rows = []
    for b in data.get("bookings", []):
        c = get_client(data, b.get("client_id"))
        rows.append({
            "Elimina": False,
            "Data": date_label_it(b.get("date")),
            "Data ISO": b.get("date", ""),
            "Ora": b.get("time", ""),
            "Cliente": full_name(c) if c else b.get("name", ""),
            "Telefono": (c or {}).get("phone", b.get("phone", "")),
            "Email": (c or {}).get("email", b.get("email", "")),
            "Istruttrice": b.get("instructor", ""),
            "Stato": b.get("status", ""),
            "Importo": money(b.get("amount", 0)),
            "Pagato": bool(b.get("paid", False)),
            "Note cliente": (c or {}).get("notes", ""),
            "ID": b.get("id"),
            "Client ID": b.get("client_id"),
        })
    cols = ["Elimina", "Data", "Data ISO", "Ora", "Cliente", "Telefono", "Email", "Istruttrice", "Stato", "Importo", "Pagato", "Note cliente", "ID", "Client ID"]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    df["_sort"] = pd.to_datetime(df["Data ISO"], errors="coerce")
    return df.sort_values(["Cliente", "_sort", "Ora"]).drop(columns=["_sort"]).reset_index(drop=True)


def period_range(opt):
    today = date.today()
    if opt == "Anno in corso":
        return date(today.year, 1, 1), date(today.year, 12, 31)
    if opt == "Ultimi 3 mesi":
        return today - timedelta(days=90), today
    if opt == "Ultimi 6 mesi":
        return today - timedelta(days=180), today
    if opt == "Ultimo anno":
        return today - timedelta(days=365), today
    return today.replace(day=1), today


def filter_period(df, start, end):
    if df.empty:
        return df.copy()
    dd = pd.to_datetime(df["Data ISO"], errors="coerce").dt.date
    return df[(dd >= start) & (dd <= end)].copy()


def summary(df):
    if df.empty:
        return 0, 0, 0, pd.DataFrame(columns=["Istruttrice", "Totale complessivo", "Totale pagato", "Totale non pagato"])
    w = df.copy()
    w["Importo"] = pd.to_numeric(w["Importo"], errors="coerce").fillna(0)
    w = w[w["Stato"] != "Annullata"]
    total = float(w["Importo"].sum())
    paid = float(w.loc[w["Pagato"] == True, "Importo"].sum())
    rows = []
    for i in INSTRUCTORS:
        s = w[w["Istruttrice"] == i]
        it = float(s["Importo"].sum())
        ip = float(s.loc[s["Pagato"] == True, "Importo"].sum())
        rows.append({"Istruttrice": i, "Totale complessivo": it, "Totale pagato": ip, "Totale non pagato": it - ip})
    return total, paid, total - paid, pd.DataFrame(rows)


def update_archive(data, edited_df):
    n = 0
    by_id = {b.get("id"): b for b in data.get("bookings", [])}
    for _, r in edited_df.iterrows():
        b = by_id.get(r.get("ID"))
        if not b:
            continue
        changed = False
        vals = {"amount": money(r.get("Importo", 0)), "paid": to_bool(r.get("Pagato", False))}
        for k, v in vals.items():
            if b.get(k) != v:
                b[k] = v
                changed = True
        c = get_client(data, r.get("Client ID"))
        if c:
            email = str(r.get("Email", "") or "").strip()
            note_cliente = str(r.get("Note cliente", "") or "").strip()
            if c.get("email", "") != email:
                c["email"] = email
                b["email"] = email
                changed = True
            if c.get("notes", "") != note_cliente:
                c["notes"] = note_cliente
                changed = True
        if changed:
            n += 1
    return n


def make_excel(df):
    bio = BytesIO()
    export = df.drop(columns=["Elimina", "ID", "Client ID", "Data ISO"], errors="ignore")
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        export.to_excel(writer, index=False, sheet_name="Archivio")
        ws = writer.sheets["Archivio"]
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(max(max(len(str(c.value)) if c.value is not None else 0 for c in col) + 2, 10), 38)
    bio.seek(0)
    return bio.getvalue()


def make_pdf(df, label=""):
    bio = BytesIO()
    doc = SimpleDocTemplate(bio, pagesize=landscape(A4), rightMargin=.6*cm, leftMargin=.6*cm, topMargin=.7*cm, bottomMargin=.7*cm)
    styles = getSampleStyleSheet()
    elems = []
    if Path(LOGO_PATH).exists():
        elems.append(Image(LOGO_PATH, width=2.0*cm, height=3.0*cm))
    elems += [Paragraph("Archivio prenotazioni Pilates - Body Center", styles["Title"]), Paragraph(label, styles["Normal"]), Spacer(1, .25*cm)]

    total, paid, unpaid, per = summary(df)
    incassi = [["Riepilogo incassi", "Importo"], ["Totale complessivo", f"€ {total:.2f}"], ["Totale pagato", f"€ {paid:.2f}"], ["Totale non pagato", f"€ {unpaid:.2f}"]]
    inc_tab = Table(incassi, colWidths=[6*cm, 4*cm])
    inc_tab.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(GREEN)), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), .25, colors.lightgrey), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]))
    elems += [inc_tab, Spacer(1, .25*cm)]

    per_rows = [["Istruttrice", "Totale complessivo", "Totale pagato", "Totale non pagato"]]
    for _, r in per.iterrows():
        per_rows.append([r["Istruttrice"], f"€ {money(r['Totale complessivo']):.2f}", f"€ {money(r['Totale pagato']):.2f}", f"€ {money(r['Totale non pagato']):.2f}"])
    per_tab = Table(per_rows, colWidths=[4*cm, 4*cm, 4*cm, 4*cm])
    per_tab.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6f8f68")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), .25, colors.lightgrey), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]))
    elems += [per_tab, Spacer(1, .35*cm)]

    cols = ["Data", "Ora", "Cliente", "Telefono", "Email", "Istruttrice", "Stato", "Importo", "Pagato", "Note cliente"]
    pdf = df[cols].copy() if not df.empty else pd.DataFrame(columns=cols)
    pdf["Pagato"] = pdf["Pagato"].map(lambda x: "Sì" if to_bool(x) else "No")
    pdf["Importo"] = pdf["Importo"].map(lambda x: f"€ {money(x):.2f}")
    table_data = [cols] + pdf.fillna("").astype(str).values.tolist()
    tab = Table(table_data, repeatRows=1)
    tab.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(GREEN)), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), .25, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]))
    elems.append(tab)
    doc.build(elems)
    bio.seek(0)
    return bio.getvalue()


# -----------------------------
# UI
# -----------------------------

def app_css():
    st.markdown(f"""
    <style>
    [data-testid="stSidebar"], [data-testid="collapsedControl"] {{ display:none !important; }}
    .stApp {{ background:#fbfcfb; }}
    .block-container {{ padding-top:1rem !important; max-width:1240px !important; }}
    div[data-testid="stMetric"] {{ background:#fff; border:1px solid #e6e9e6; border-radius:14px; padding:12px; }}
    div[data-testid="stRadio"] > div {{ gap:.65rem !important; flex-wrap:wrap !important; }}
    div[data-testid="stRadio"] label {{ min-height:42px !important; padding:.55rem 1rem !important; border-radius:999px !important; border:1px solid #dce6dc !important; background:#fff !important; box-shadow:0 3px 10px rgba(36,49,66,.045) !important; }}
    div[data-testid="stRadio"] input[type="radio"] {{ display:none !important; }}
    div[data-testid="stRadio"] label:has(input:checked) {{ background:{GREEN} !important; border-color:{GREEN} !important; }}
    div[data-testid="stRadio"] label:has(input:checked) p {{ color:#fff !important; }}
    @media (max-width:760px) {{
        .block-container {{ padding-left:.65rem !important; padding-right:.65rem !important; padding-top:.45rem !important; max-width:100% !important; }}
        h1 {{ font-size:1.75rem !important; line-height:1.08 !important; }}
        img {{ max-width:88px !important; height:auto !important; }}
        div[data-testid="stRadio"] > div {{ display:grid !important; grid-template-columns:1fr 1fr !important; gap:.45rem !important; }}
        div[data-testid="stRadio"] label {{ width:100% !important; min-height:42px !important; padding:.45rem .55rem !important; border-radius:14px !important; overflow:visible !important; }}
        div[data-testid="stRadio"] label p {{ font-size:.86rem !important; font-weight:800 !important; white-space:normal !important; overflow:visible !important; text-overflow:clip !important; line-height:1.1 !important; }}
    }}
    </style>
    """, unsafe_allow_html=True)


def login():
    if st.session_state.get("authenticated", False):
        return True
    left, center, right = st.columns([1.4, 1.2, 1.4])
    with center:
        st.markdown("### Accesso staff")
        st.caption("Inserisci la password per accedere al gestionale.")
        pwd = st.text_input("Password", type="password", key="main_login_password")
        if st.button("Accedi", type="primary", use_container_width=True):
            if pwd == get_secret("APP_PASSWORD", "pilates123"):
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Password non corretta")
    return False


def render_header():
    logo_html = ""
    if Path(LOGO_PATH).exists():
        logo_b64 = base64.b64encode(Path(LOGO_PATH).read_bytes()).decode("ascii")
        logo_html = f"<img src='data:image/png;base64,{logo_b64}' style='width:118px;height:118px;object-fit:contain;'>"
    st.markdown(f"""
    <div style='display:flex;align-items:center;gap:22px;background:linear-gradient(135deg,#f8fbf8 0%,#eef6f1 100%);border:1px solid #dfe8df;border-radius:24px;padding:18px 22px;margin:4px 0 16px 0;box-shadow:0 8px 24px rgba(36,49,66,.06);'>
        <div>{logo_html}</div>
        <div>
            <h1 style='margin:0;color:#243142;font-size:clamp(2rem,4vw,3rem);font-weight:850;line-height:1.04;letter-spacing:-.035em;'>Prenotazioni Pilates Reformer</h1>
            <p style='margin:7px 0 0 0;color:#6f7780;font-size:1rem;'>Gestionale interno Body Center · clienti, prenotazioni, pagamenti</p>
        </div>
    </div>
    """, unsafe_allow_html=True)


def save_and_rerun(data, sha, message):
    save_data(data, sha, message)
    st.rerun()


def render_client_form(data, sha, cid, prefix, close_key=None):
    c = get_client(data, cid)
    if not c:
        st.error("Cliente non trovato.")
        return

    st.markdown(f"### Scheda cliente: {full_name(c)}")
    a, b = st.columns(2)
    last = a.text_input("Cognome", value=c.get("last_name", ""), key=f"{prefix}_last_{cid}")
    first = b.text_input("Nome", value=c.get("first_name", ""), key=f"{prefix}_first_{cid}")
    a, b, c3 = st.columns(3)
    phone = a.text_input("Telefono", value=c.get("phone", ""), key=f"{prefix}_phone_{cid}")
    email = b.text_input("Email", value=c.get("email", ""), key=f"{prefix}_email_{cid}")
    birth = c3.text_input("Data di nascita", value=date_it(c.get("birth_date", "")), placeholder="gg-mm-aaaa", key=f"{prefix}_birth_{cid}")
    st.caption(f"Età: {age_from_birth(birth) if birth else ''}")
    notes = st.text_area("Note cliente", value=c.get("notes", ""), key=f"{prefix}_notes_{cid}")
    anam = st.text_area("Anamnesi / problematiche", value=c.get("anamnesis", ""), height=140, key=f"{prefix}_anam_{cid}")
    goals = st.text_area("Obiettivi", value=c.get("goals", ""), height=100, key=f"{prefix}_goals_{cid}")

    if st.button("Salva scheda cliente", type="primary", key=f"{prefix}_save_{cid}", use_container_width=is_mobile_client()):
        ok, msg = update_client_record(data, cid, first, last, phone, email, birth, notes, anam, goals)
        if ok:
            if close_key:
                st.session_state.pop(close_key, None)
            save_data(data, sha, "Update client record")
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)

    if not is_mobile_client():
        hist = []
        for bkg in data.get("bookings", []):
            if bkg.get("client_id") == cid:
                hist.append({"Data": date_it(bkg.get("date")), "Ora": bkg.get("time"), "Istruttrice": bkg.get("instructor"), "Stato": bkg.get("status"), "Importo": money(bkg.get("amount", 0)), "Pagato": bool(bkg.get("paid", False)), "Note prenotazione": bkg.get("note", "")})
        if hist:
            st.markdown("#### Storico lezioni")
            st.dataframe(pd.DataFrame(hist).sort_values(["Data", "Ora"]), use_container_width=True, hide_index=True)


def render_week(data, sha):
    st.subheader("Vista settimanale")
    today = date.today()
    start = max(parse_date(st.date_input("Scegli la data di partenza", value=today, min_value=today, format="DD/MM/YYYY")), today)
    for d in next_days(start, 5):
        st.markdown(f"### {DAY_NAMES[d.weekday()]} {d.strftime('%d/%m/%Y')}")
        cols = st.columns(3)
        for i, t in enumerate(times_for(d)):
            with cols[i % 3]:
                n, _, conf, wait = slot_status(data, d, t)
                label = f"{t} — {n}/{CAPACITY}"
                st.error(label) if n >= CAPACITY else st.info(label) if n == 0 else st.success(label)
                for j, bkg in enumerate(conf, 1):
                    st.write(f"{j}. {bkg.get('name','')} · {bkg.get('instructor','')} · € {money(bkg.get('amount',0)):.2f} · {'pagato' if bkg.get('paid') else 'non pagato'}")
                if wait:
                    st.caption("Lista d'attesa:")
                    for bkg in wait:
                        st.caption(f"• {bkg.get('name','')} · {bkg.get('phone','')}")
                with st.expander("Gestisci"):
                    for bkg in slot_rows(data, d, t, True):
                        st.markdown(f"**{status_icon(bkg.get('status'))} {bkg.get('name','')}** — {bkg.get('phone','')}")
                        a, b2, c = st.columns(3)
                        if a.button("Conferma", key=f"c{bkg['id']}") and change_status(data, bkg["id"], "Confermata"):
                            save_and_rerun(data, sha, "Conferma")
                        if b2.button("Attesa", key=f"w{bkg['id']}") and change_status(data, bkg["id"], "Lista attesa"):
                            save_and_rerun(data, sha, "Attesa")
                        if c.button("Annulla", key=f"x{bkg['id']}") and change_status(data, bkg["id"], "Annullata"):
                            save_and_rerun(data, sha, "Annulla")


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
        a, b, c = st.columns(3)
        amount = a.number_input("Importo (€)", min_value=0.0, value=0.0, step=1.0, format="%.2f")
        paid = b.checkbox("Pagato")
        instr = c.selectbox("Istruttrice", INSTRUCTORS)
        note = st.text_area("Note prenotazione")
        st.info(f"Stato automatico: {auto_status(data, d, t)}")
        if st.button("Salva prenotazione", type="primary"):
            bk = create_booking(data, cid, d, t, amount, paid, instr, note)
            st.session_state["_next_section"] = "Archivio"
            save_and_rerun(data, sha, f"Add booking {bk['name']}")


def render_clients(data, sha):
    st.subheader("Clienti")
    with st.expander("➕ Inserisci nuovo cliente"):
        a, b = st.columns(2)
        last = a.text_input("Cognome", key="new_client_last")
        first = b.text_input("Nome", key="new_client_first")
        c, d = st.columns(2)
        phone = c.text_input("Telefono", key="new_client_phone")
        email = d.text_input("Email", key="new_client_email")
        birth = st.text_input("Data di nascita", placeholder="gg-mm-aaaa", key="new_client_birth")
        notes = st.text_area("Note cliente", key="new_client_notes")
        if st.button("Salva cliente"):
            ok, msg, _ = add_client(data, first, last, phone, email, notes, birth)
            if ok:
                save_and_rerun(data, sha, "Add client")
            else:
                st.error(msg)

    sort_by = st.radio("Ordina per", ["Alfabetico", "Ultima visita"], horizontal=True, key="client_sort")
    dfc = clients_df(data, sort_by)
    if dfc.empty:
        st.info("Nessun cliente presente.")
        return
    q = st.text_input("Cerca cliente").lower().strip()
    view = dfc[dfc.apply(lambda r: q in " ".join(map(str, r.values)).lower(), axis=1)] if q else dfc

    if is_mobile_client():
        open_cid = st.session_state.get("client_open_id")
        if open_cid:
            if st.button("← Torna ai clienti", use_container_width=True, key="client_mobile_back"):
                st.session_state.pop("client_open_id", None)
                st.rerun()
            render_client_form(data, sha, open_cid, prefix="clienti_mobile", close_key="client_open_id")
            return
        for _, r in view.iterrows():
            cid = r.get("ID")
            c = get_client(data, cid) or {}
            with st.container(border=True):
                st.markdown(f"**{full_name(c)}**")
                st.caption(f"📅 Ultima lezione: {r.get('Ultima lezione') or 'Nessuna'}")
                if c.get("phone"):
                    st.markdown(f"📞 [{c.get('phone')}](tel:{c.get('phone')})")
                if c.get("email"):
                    st.caption(f"✉️ {c.get('email')}")
                if st.button("Apri scheda cliente", key=f"client_mobile_open_{cid}", use_container_width=True):
                    st.session_state["client_open_id"] = cid
                    st.rerun()
        return

    display = view.drop(columns=["ID", "_last"], errors="ignore")
    st.dataframe(display, use_container_width=True, hide_index=True)
    opts = ["—"] + [f"{r.Cognome} {r.Nome} | {r.ID}" for _, r in view.iterrows()]
    choice = st.selectbox("Apri scheda cliente", opts)
    if choice != "—":
        cid = choice.split("|")[-1].strip()
        st.divider()
        render_client_form(data, sha, cid, prefix="clienti_pc")


def render_search(data):
    st.subheader("Cerca")
    q = st.text_input("Cerca per nome, telefono o email").lower().strip()
    if not q:
        return
    dfa = archive_df(data)
    res = dfa[dfa.apply(lambda r: q in " ".join(map(str, r.values)).lower(), axis=1)] if not dfa.empty else dfa
    if res.empty:
        st.info("Nessun risultato.")
        return
    if is_mobile_client():
        for _, r in res.iterrows():
            with st.container(border=True):
                st.markdown(f"**{r.get('Cliente','')}**")
                st.caption(f"📅 {r.get('Data','')} · 🕒 {r.get('Ora','')} · {r.get('Stato','')}")
                st.caption(f"📞 {r.get('Telefono','')} · € {money(r.get('Importo',0)):.2f}")
    else:
        st.dataframe(res.drop(columns=["Elimina", "ID", "Client ID", "Data ISO"], errors="ignore"), use_container_width=True, hide_index=True)


def render_archive_open_client(data, sha):
    open_cid = st.session_state.get("archive_open_client_id")
    if not open_cid:
        return False
    if st.button("← Torna all’Archivio", key="archive_back_to_list", use_container_width=is_mobile_client()):
        st.session_state.pop("archive_open_client_id", None)
        st.rerun()
    render_client_form(data, sha, open_cid, prefix="archivio_page", close_key="archive_open_client_id")
    return True


def render_archive_mobile(df, data, sha):
    open_cid = st.session_state.get("archive_open_client_id")
    if open_cid:
        if st.button("← Torna alle schede", key="archive_mobile_back", use_container_width=True):
            st.session_state.pop("archive_open_client_id", None)
            st.rerun()
        render_client_form(data, sha, open_cid, prefix="archivio_mobile", close_key="archive_open_client_id")
        return

    if df.empty:
        st.info("Nessuna prenotazione nel filtro selezionato.")
        return

    st.markdown("#### Schede archivio")
    for i, (_, r) in enumerate(df.reset_index(drop=True).iterrows()):
        cid = str(r.get("Client ID", "") or "")
        bid = str(r.get("ID", i) or i)
        with st.container(border=True):
            st.markdown(f"**{r.get('Cliente','')}**")
            st.caption(f"📅 {r.get('Data','')} · 🕒 {r.get('Ora','')} · {r.get('Stato','')}")
            st.caption(f"👩‍🏫 {r.get('Istruttrice','')} · 💶 € {money(r.get('Importo',0)):.2f} · {'Pagato' if to_bool(r.get('Pagato', False)) else 'Non pagato'}")
            tel = str(r.get("Telefono", "") or "")
            email = str(r.get("Email", "") or "")
            note = str(r.get("Note cliente", "") or "")
            if tel:
                st.markdown(f"📞 [{tel}](tel:{tel})")
            if email:
                st.caption(f"✉️ {email}")
            if note:
                st.caption(f"📝 {note}")
            if cid:
                if st.button("Apri scheda cliente", key=f"archive_mobile_open_{bid}_{i}", use_container_width=True):
                    st.session_state["archive_open_client_id"] = cid
                    st.rerun()


def render_archive(data, sha):
    if render_archive_open_client(data, sha):
        return
    st.subheader("Archivio, pagamenti e statistiche")
    dfa = archive_df(data)
    if dfa.empty:
        st.info("Nessuna prenotazione presente.")
        return

    opt = st.selectbox("Scegli periodo", ["Anno in corso", "Mese selezionato", "Periodo personalizzato", "Ultimi 3 mesi", "Ultimi 6 mesi", "Ultimo anno"], index=0)
    today = date.today()
    if opt == "Mese selezionato":
        m = parse_date(st.date_input("Mese di riferimento", value=today, format="DD/MM/YYYY"))
        start = m.replace(day=1)
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    elif opt == "Periodo personalizzato":
        a, b = st.columns(2)
        start = parse_date(a.date_input("Dal", value=date(today.year, 1, 1), format="DD/MM/YYYY"))
        end = parse_date(b.date_input("Al", value=date(today.year, 12, 31), format="DD/MM/YYYY"))
    else:
        start, end = period_range(opt)

    dfp = filter_period(dfa, start, end)
    label = f"Periodo: {start.strftime('%d-%m-%Y')} - {end.strftime('%d-%m-%Y')}"
    st.caption(label)
    total, paid, unpaid, per = summary(dfp)
    a, b, c = st.columns(3)
    a.metric("Totale complessivo", f"€ {total:.2f}")
    b.metric("Totale pagato", f"€ {paid:.2f}")
    c.metric("Totale non pagato", f"€ {unpaid:.2f}")

    status = st.multiselect("Filtra stato archivio", ["Confermata", "Lista attesa", "Annullata"], default=["Confermata", "Lista attesa"])
    only = st.checkbox("Mostra solo il periodo selezionato", value=True)
    df = dfp.copy() if only else dfa.copy()
    if status:
        df = df[df["Stato"].isin(status)]

    if is_mobile_client():
        render_archive_mobile(df, data, sha)
        return

    st.dataframe(per, use_container_width=True, hide_index=True)
    st.markdown("#### Modifica importi, pagamenti e note")
    edit_cols = ["Elimina", "Data", "Ora", "Cliente", "Telefono", "Email", "Istruttrice", "Stato", "Importo", "Pagato", "Note cliente", "ID", "Client ID", "Data ISO"]
    edited = st.data_editor(
        df[edit_cols],
        use_container_width=True,
        hide_index=True,
        disabled=["Data", "Ora", "Cliente", "Telefono", "Istruttrice", "Stato", "ID", "Client ID", "Data ISO"],
        column_config={
            "ID": None,
            "Client ID": None,
            "Data ISO": None,
            "Importo": st.column_config.NumberColumn("Importo", format="€ %.2f"),
        },
        key=f"archive_editor_{st.session_state.get('archive_nonce', 0)}",
    )

    a, b = st.columns(2)
    if a.button("Salva modifiche importi/pagamenti/note"):
        n = update_archive(data, edited)
        if n:
            st.session_state["archive_nonce"] = int(st.session_state.get("archive_nonce", 0)) + 1
            save_and_rerun(data, sha, "Update archive")
        else:
            st.info("Nessuna modifica da salvare.")

    ids = edited.loc[edited.get("Elimina", False).apply(to_bool) == True, "ID"].dropna().astype(str).tolist() if not edited.empty else []
    if b.button("Elimina selezionate", type="primary"):
        if not ids:
            st.error("Non hai selezionato nessuna prenotazione da eliminare.")
        else:
            n = delete_bookings(data, ids)
            st.session_state["archive_nonce"] = int(st.session_state.get("archive_nonce", 0)) + 1
            save_and_rerun(data, sha, "Delete bookings")

    opts = ["—"] + [f"{r.Cliente} | {r['Client ID']}" for _, r in df.dropna(subset=["Client ID"]).drop_duplicates("Client ID").iterrows()]
    choice = st.selectbox("Apri scheda cliente", opts, key="archive_open_select")
    if choice != "—":
        st.session_state["archive_open_client_id"] = choice.split("|")[-1].strip()
        st.rerun()

    a, b = st.columns(2)
    a.download_button("Scarica Excel", data=make_excel(edited), file_name="prenotazioni_pilates.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    b.download_button("Scarica PDF archivio", data=make_pdf(edited, label), file_name="archivio_prenotazioni_pilates.pdf", mime="application/pdf")


# -----------------------------
# App bootstrap
# -----------------------------

st.set_page_config(page_title=APP_TITLE, page_icon="🧘", layout="wide", initial_sidebar_state="collapsed")
app_css()
render_header()

if not login():
    st.stop()

try:
    data, sha = load_data()
    data = ensure_data(data)
except Exception as e:
    st.error(f"Errore caricamento dati: {e}")
    st.stop()

if not github_enabled():
    st.warning("Modalità locale: per condivisione usa i Secrets GitHub su Streamlit.")

if "_next_section" in st.session_state:
    st.session_state["section"] = st.session_state.pop("_next_section")
if "section" not in st.session_state or st.session_state["section"] not in SECTIONS:
    st.session_state["section"] = "Settimana"

section = st.radio("Sezione", SECTIONS, horizontal=True, key="section", label_visibility="collapsed")
if st.session_state.get("_last_section") != section:
    st.session_state.pop("client_open_id", None)
    st.session_state.pop("archive_open_client_id", None)
    st.session_state.pop("archive_open_select", None)
    st.session_state["_last_section"] = section
st.divider()

if section == "Settimana":
    render_week(data, sha)
elif section == "Prenota":
    render_booking(data, sha)
elif section == "Clienti":
    render_clients(data, sha)
elif section == "Cerca":
    render_search(data)
elif section == "Archivio":
    render_archive(data, sha)
