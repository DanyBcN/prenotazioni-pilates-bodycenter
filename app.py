import base64
import html
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
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

try:
    from st_aggrid import AgGrid, DataReturnMode, GridOptionsBuilder, GridUpdateMode
    AGGRID_AVAILABLE = True
except Exception:
    AGGRID_AVAILABLE = False

APP_TITLE = "Prenotazioni Pilates Reformer"
CAPACITY = 4
LOCAL_DATA_PATH = "data/bookings.json"
LOGO_PATH = "assets/logo.png"
INSTRUCTORS = ["Grazia", "Alice"]
GREEN = "#496744"
DARK = "#243142"
LIGHT_GREEN = "#eef6f2"
SECTIONS = ["📅 Settimana", "➕ Prenota", "👤 Clienti", "🔎 Cerca", "📋 Archivio"]

SCHEDULE = {
    0: ["08:30", "09:30", "10:30", "17:00", "18:00", "19:00"],
    1: ["09:30", "10:30", "11:30", "12:45", "14:30", "19:00"],
    2: ["08:30", "09:30", "10:30", "11:30", "12:45", "14:30", "15:30", "16:30", "17:30", "18:30"],
    3: ["17:00", "18:00", "19:00"],
    4: ["14:00", "15:00", "16:00", "17:00", "18:00", "19:00"],
}
DAY_NAMES = {0: "Lunedì", 1: "Martedì", 2: "Mercoledì", 3: "Giovedì", 4: "Venerdì", 5: "Sabato", 6: "Domenica"}


def get_secret(name, default=""):
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return os.environ.get(name, default)


def github_enabled():
    return bool(get_secret("GITHUB_TOKEN") and get_secret("GITHUB_REPO") and get_secret("GITHUB_BRANCH", "main"))


def github_headers():
    return {
        "Authorization": f"Bearer {get_secret('GITHUB_TOKEN')}",
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
    Path(LOCAL_DATA_PATH).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_data():
    if github_enabled():
        r = requests.get(github_file_url(), headers=github_headers(), params={"ref": get_secret("GITHUB_BRANCH", "main")}, timeout=20)
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


def money(value):
    try:
        return round(float(value or 0), 2)
    except Exception:
        return 0.0


def to_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "sì", "si", "yes"}


def new_id(prefix=""):
    return prefix + datetime.now().strftime("%Y%m%d%H%M%S%f")


def norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def client_key(first, last):
    return f"{norm(first)}|{norm(last)}"


def full_name(c):
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
    keys = {client_key(c.get("first_name", ""), c.get("last_name", "")): c for c in data["clients"]}
    for b in data["bookings"]:
        b.setdefault("id", new_id("b_"))
        b.setdefault("amount", 0)
        b.setdefault("paid", False)
        b.setdefault("note", "")
        b.setdefault("instructor", "")
        b.setdefault("email", "")
        if b.get("client_id"):
            continue
        first, last = split_name(b.get("name", ""))
        k = client_key(first, last)
        if k.strip("|") and k in keys:
            b["client_id"] = keys[k]["id"]
        elif k.strip("|"):
            c = {
                "id": new_id("c_"), "first_name": first, "last_name": last,
                "phone": b.get("phone", ""), "email": b.get("email", ""),
                "notes": "", "birth_date": "", "anamnesis": "", "goals": "",
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            data["clients"].append(c)
            keys[k] = c
            b["client_id"] = c["id"]
    return data


def client_options(data):
    return sorted([f"{full_name(c)} | {c.get('phone','')} | {c.get('email','')} | {c.get('id')}" for c in data.get("clients", [])], key=str.lower)


def option_to_client_id(option):
    return option.split("|")[-1].strip()


def add_client(data, first, last, phone="", email="", notes="", birth_date="", anamnesis="", goals=""):
    first, last = first.strip(), last.strip()
    if not first or not last:
        return False, "Inserisci nome e cognome.", None
    k = client_key(first, last)
    for c in data.get("clients", []):
        if client_key(c.get("first_name", ""), c.get("last_name", "")) == k:
            return False, "Cliente già presente: nome e cognome devono essere univoci.", c.get("id")
    cid = new_id("c_")
    data["clients"].append({
        "id": cid, "first_name": first, "last_name": last, "phone": phone.strip(), "email": email.strip(),
        "notes": notes.strip(), "birth_date": birth_date.strip(), "anamnesis": anamnesis.strip(), "goals": goals.strip(),
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
        "first_name": first, "last_name": last, "phone": phone.strip(), "email": email.strip(),
        "birth_date": birth.strip(), "notes": notes.strip(), "anamnesis": anamnesis.strip(), "goals": goals.strip(),
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
        rows.append({"ID": c.get("id"), "Cognome": c.get("last_name", ""), "Nome": c.get("first_name", ""), "Ultima lezione": date_it(lv) if lv else "", "_last": lv or date(1900, 1, 1)})
    if not rows:
        return pd.DataFrame(columns=["ID", "Cognome", "Nome", "Ultima lezione", "_last"])
    df = pd.DataFrame(rows)
    if sort_by == "Ultima visita":
        return df.sort_values(["_last", "Cognome", "Nome"], ascending=[False, True, True]).reset_index(drop=True)
    return df.sort_values(["Cognome", "Nome"]).reset_index(drop=True)


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
    return sorted([b for b in data.get("bookings", []) if b.get("date") == date_key(d) and b.get("time") == t and (include_cancelled or b.get("status") != "Annullata")], key=lambda x: x.get("created_at", ""))


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
        "id": new_id("b_"), "created_at": datetime.now().isoformat(timespec="seconds"), "client_id": cid,
        "date": date_key(d), "day": DAY_NAMES[d.weekday()], "time": t, "name": full_name(c),
        "phone": c.get("phone", ""), "email": c.get("email", ""), "note": note.strip(),
        "status": auto_status(data, d, t), "amount": money(amount), "paid": bool(paid),
        "instructor": instructor, "created_by": "staff",
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


def archive_df(data):
    rows = []
    for b in data.get("bookings", []):
        c = get_client(data, b.get("client_id"))
        rows.append({
            "Elimina": False, "Data": date_it(b.get("date")), "Giorno": b.get("day"), "Ora": b.get("time"),
            "Cliente": full_name(c) if c else b.get("name", ""), "Telefono": (c or {}).get("phone", b.get("phone", "")),
            "Email": (c or {}).get("email", b.get("email", "")), "Istruttrice": b.get("instructor", ""),
            "Stato": b.get("status"), "Importo": money(b.get("amount", 0)), "Pagato": bool(b.get("paid", False)),
            "Note cliente": (c or {}).get("notes", ""), "Note prenotazione": b.get("note", ""),
            "Inserita il": b.get("created_at"), "ID": b.get("id"), "Client ID": b.get("client_id"),
        })
    cols = ["Elimina", "Data", "Giorno", "Ora", "Cliente", "Telefono", "Email", "Istruttrice", "Stato", "Importo", "Pagato", "Note cliente", "Note prenotazione", "Inserita il", "ID", "Client ID"]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    df["_sort"] = pd.to_datetime(df["Data"], dayfirst=True, errors="coerce")
    return df.sort_values(["_sort", "Ora", "Cliente"]).drop(columns=["_sort"]).reset_index(drop=True)


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
    dd = pd.to_datetime(df["Data"], dayfirst=True, errors="coerce").dt.date
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
        vals = {"amount": money(r.get("Importo", 0)), "paid": to_bool(r.get("Pagato", False)), "note": str(r.get("Note prenotazione", "") or "")}
        changed = False
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
    export = df.drop(columns=["Elimina", "ID", "Client ID"], errors="ignore")
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        export.to_excel(writer, index=False, sheet_name="Archivio")
        ws = writer.sheets["Archivio"]
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(max(max(len(str(c.value)) if c.value is not None else 0 for c in col) + 2, 10), 38)
    bio.seek(0)
    return bio.getvalue()


def _pdf_paragraph(value, style):
    text = "" if value is None else str(value)
    text = html.escape(text).replace("\n", "<br/>")
    return Paragraph(text, style)


def make_pdf(df, label=""):
    bio = BytesIO()
    doc = SimpleDocTemplate(bio, pagesize=landscape(A4), rightMargin=.6*cm, leftMargin=.6*cm, topMargin=.7*cm, bottomMargin=.7*cm)
    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle("cell", fontName="Helvetica", fontSize=6, leading=7.2, alignment=TA_CENTER, wordWrap="CJK")
    header_style = ParagraphStyle("header", fontName="Helvetica-Bold", fontSize=6, leading=7.2, alignment=TA_CENTER, textColor=colors.white, wordWrap="CJK")
    total, paid, unpaid, per = summary(df)
    elems = []
    if Path(LOGO_PATH).exists():
        elems.append(Image(LOGO_PATH, width=2.0*cm, height=3.0*cm))
    elems += [Paragraph("Archivio prenotazioni Pilates - Body Center", styles["Title"]), Paragraph(label, styles["Normal"]), Paragraph(f"Generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]), Spacer(1, .25*cm)]
    totals = Table([["Totale complessivo", "Totale pagato", "Totale non pagato"], [f"€ {total:.2f}", f"€ {paid:.2f}", f"€ {unpaid:.2f}"]], colWidths=[5*cm]*3)
    totals.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor(GREEN)), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("ALIGN", (0,0), (-1,-1), "CENTER"), ("GRID", (0,0), (-1,-1), .25, colors.lightgrey)]))
    elems += [totals, Spacer(1, .25*cm), Paragraph("Totali per istruttrice", styles["Heading2"])]
    instr_data = [["Istruttrice", "Totale complessivo", "Totale pagato", "Totale non pagato"]] + [[r["Istruttrice"], f"€ {r['Totale complessivo']:.2f}", f"€ {r['Totale pagato']:.2f}", f"€ {r['Totale non pagato']:.2f}"] for _, r in per.iterrows()]
    instr = Table(instr_data, colWidths=[4*cm]*4)
    instr.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor(DARK)), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("GRID", (0,0), (-1,-1), .25, colors.lightgrey), ("ALIGN", (0,0), (-1,-1), "CENTER")]))
    elems += [instr, Spacer(1, .35*cm)]
    cols = ["Data", "Ora", "Cliente", "Telefono", "Email", "Istruttrice", "Stato", "Importo", "Pagato", "Note cliente", "Note prenotazione"]
    pdf = df[cols].copy() if not df.empty else pd.DataFrame(columns=cols)
    pdf["Pagato"] = pdf["Pagato"].map(lambda x: "Sì" if to_bool(x) else "No")
    pdf["Importo"] = pdf["Importo"].map(lambda x: f"€ {money(x):.2f}")
    pdf = pdf.fillna("").astype(str)
    rows = [[_pdf_paragraph(c, header_style) for c in cols]]
    for _, row in pdf.iterrows():
        rows.append([_pdf_paragraph(row[c], cell_style) for c in cols])
    tab = Table(rows, repeatRows=1, colWidths=[1.35*cm, .95*cm, 2.8*cm, 1.7*cm, 2.5*cm, 1.5*cm, 1.35*cm, 1.25*cm, 1.0*cm, 5.0*cm, 5.0*cm])
    tab.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor(GREEN)), ("GRID", (0,0), (-1,-1), .25, colors.lightgrey), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("ALIGN", (0,0), (-1,-1), "CENTER"), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f8faf8")])]))
    elems.append(tab)
    doc.build(elems)
    bio.seek(0)
    return bio.getvalue()


def app_css():
    st.markdown(f"""
    <style>
    [data-testid="stSidebar"], [data-testid="collapsedControl"] {{ display: none !important; }}
    .stApp {{ background: #fbfcfb; }}
    div[data-testid="stMetric"] {{ background:#fff; border:1px solid #e6e9e6; border-radius:14px; padding:12px; }}
    .ag-theme-streamlit, .ag-theme-balham {{ --ag-row-hover-color: {LIGHT_GREEN}; --ag-selected-row-background-color: #dceee4; }}
    .ag-row, .ag-cell {{ cursor: pointer !important; text-align:center !important; justify-content:center !important; align-items:center !important; }}
    .ag-cell-wrapper {{ justify-content:center !important; }}
    .ag-header-cell-label {{ justify-content:center !important; font-weight: 700; text-align:center !important; }}
    .ag-header-cell-text {{ margin:auto; }}
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


def selected_row_from_response(response):
    selected = response.get("selected_rows", [])
    if selected is None:
        return None
    if isinstance(selected, pd.DataFrame):
        if selected.empty:
            return None
        return selected.iloc[0].to_dict()
    if isinstance(selected, list) and selected:
        return selected[0]
    return None


def client_grid(df, key):
    show = df[["ID", "Cognome", "Nome", "Ultima lezione"]].copy()
    if not AGGRID_AVAILABLE:
        event = st.dataframe(show.drop(columns=["ID"]), use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key=key)
        rows = getattr(getattr(event, "selection", None), "rows", []) or []
        return show.iloc[rows[0]].to_dict() if rows else None
    gb = GridOptionsBuilder.from_dataframe(show)
    gb.configure_column("ID", hide=True)
    gb.configure_default_column(sortable=True, filter=True, resizable=True, cellStyle={"textAlign": "center"})
    gb.configure_selection(selection_mode="single", use_checkbox=False)
    gb.configure_grid_options(rowHeight=42, suppressRowClickSelection=False, rowSelection="single")
    response = AgGrid(show, gridOptions=gb.build(), height=min(480, 80 + 43 * max(len(show), 3)), fit_columns_on_grid_load=True, update_mode=GridUpdateMode.SELECTION_CHANGED, data_return_mode=DataReturnMode.FILTERED_AND_SORTED, allow_unsafe_jscode=True, custom_css={".ag-row": {"cursor": "pointer !important"}, ".ag-row-hover": {"background-color": f"{LIGHT_GREEN} !important"}, ".ag-cell": {"display": "flex", "align-items": "center", "justify-content": "center", "text-align": "center"}, ".ag-header-cell-label": {"justify-content": "center", "text-align": "center"}}, key=key)
    return selected_row_from_response(response)


def archive_grid(df, key):
    columns = ["Elimina", "Data", "Giorno", "Ora", "Cliente", "Telefono", "Email", "Istruttrice", "Stato", "Importo", "Pagato", "Note cliente", "Note prenotazione", "Inserita il", "ID", "Client ID"]
    show = df[columns].copy()
    if not AGGRID_AVAILABLE:
        edited = st.data_editor(show.drop(columns=["ID", "Client ID"], errors="ignore"), use_container_width=True, hide_index=True, key=key)
        edited["ID"] = show["ID"].values
        edited["Client ID"] = show["Client ID"].values
        return edited, None
    gb = GridOptionsBuilder.from_dataframe(show)
    gb.configure_default_column(sortable=True, filter=True, resizable=True, cellStyle={"textAlign": "center"})
    gb.configure_column("ID", hide=True)
    gb.configure_column("Client ID", hide=True)
    gb.configure_column("Elimina", editable=True, width=95, pinned="left", cellStyle={"textAlign": "center"})
    gb.configure_column("Data", editable=False, width=115)
    gb.configure_column("Giorno", editable=False, width=120)
    gb.configure_column("Ora", editable=False, width=90)
    gb.configure_column("Cliente", editable=False, minWidth=190, cellStyle={"fontWeight": "600", "color": "#1f5c8f", "cursor": "pointer", "textAlign": "center"})
    gb.configure_column("Telefono", editable=False, width=140)
    gb.configure_column("Email", editable=True, minWidth=210, cellStyle={"backgroundColor": "#fffdf0", "textAlign": "center"})
    gb.configure_column("Istruttrice", editable=False, width=120)
    gb.configure_column("Stato", editable=False, width=130)
    gb.configure_column("Importo", editable=True, type=["numericColumn"], width=115, cellStyle={"backgroundColor": "#fffdf0", "textAlign": "center"})
    gb.configure_column("Pagato", editable=True, width=105, cellStyle={"backgroundColor": "#fffdf0", "textAlign": "center"})
    gb.configure_column("Note cliente", editable=True, minWidth=240, wrapText=True, autoHeight=True, cellStyle={"backgroundColor": "#fffdf0", "textAlign": "center"})
    gb.configure_column("Note prenotazione", editable=True, minWidth=240, wrapText=True, autoHeight=True, cellStyle={"backgroundColor": "#fffdf0", "textAlign": "center"})
    gb.configure_column("Inserita il", editable=False, width=170)
    gb.configure_selection(selection_mode="single", use_checkbox=False)
    gb.configure_grid_options(rowHeight=44, suppressRowClickSelection=False, rowSelection="single")
    response = AgGrid(show, gridOptions=gb.build(), height=540, fit_columns_on_grid_load=False, update_mode=GridUpdateMode.SELECTION_CHANGED | GridUpdateMode.VALUE_CHANGED, data_return_mode=DataReturnMode.AS_INPUT, allow_unsafe_jscode=True, custom_css={".ag-row": {"cursor": "pointer !important"}, ".ag-row-hover": {"background-color": f"{LIGHT_GREEN} !important"}, ".ag-cell": {"display": "flex", "align-items": "center", "justify-content": "center", "text-align": "center"}, ".ag-header-cell-label": {"justify-content": "center", "text-align": "center"}}, key=key)
    return pd.DataFrame(response.get("data", show)), selected_row_from_response(response)


def render_client_card(data, sha, cid, prefix="client"):
    c = get_client(data, cid)
    if not c:
        st.error("Cliente non trovato.")
        return
    st.markdown(f"### Scheda anagrafica: {full_name(c)}")
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
    if st.button("Salva scheda cliente", type="primary", key=f"{prefix}_save_{cid}"):
        ok, msg = update_client_record(data, cid, first, last, phone, email, birth, notes, anam, goals)
        if ok:
            save_data(data, sha, "Update client record")
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)
    hist = []
    for bkg in data.get("bookings", []):
        if bkg.get("client_id") == cid:
            hist.append({"Data": date_it(bkg.get("date")), "Ora": bkg.get("time"), "Istruttrice": bkg.get("instructor"), "Stato": bkg.get("status"), "Importo": money(bkg.get("amount", 0)), "Pagato": bool(bkg.get("paid", False)), "Note prenotazione": bkg.get("note", "")})
    if hist:
        st.markdown("#### Storico lezioni")
        st.dataframe(pd.DataFrame(hist).sort_values(["Data", "Ora"]), use_container_width=True, hide_index=True)


def request_section(section):
    st.session_state["_next_section"] = section


def render_header():
    c1, c2 = st.columns([1, 6])
    with c1:
        if Path(LOGO_PATH).exists():
            st.image(LOGO_PATH, width=130)
    with c2:
        st.markdown(f"<h1 style='margin-bottom:0;color:{DARK};'>Prenotazioni Pilates Reformer</h1>", unsafe_allow_html=True)
        st.caption("Gestionale interno Body Center · clienti, prenotazioni, pagamenti")


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
                            save_data(data, sha, "Conferma")
                            st.rerun()
                        if b2.button("Attesa", key=f"w{bkg['id']}") and change_status(data, bkg["id"], "Lista attesa"):
                            save_data(data, sha, "Attesa")
                            st.rerun()
                        if c.button("Annulla", key=f"x{bkg['id']}") and change_status(data, bkg["id"], "Annullata"):
                            save_data(data, sha, "Annulla")
                            st.rerun()


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
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    if cid:
        st.markdown("### Dati prenotazione")
        a, b = st.columns(2)
        d = parse_date(a.date_input("Data", value=date.today(), min_value=date.today(), format="DD/MM/YYYY", key="bd"))
        ts = times_for(d)
        if ts:
            t = b.selectbox("Orario", ts)
            a, b, c = st.columns(3)
            amount = a.number_input("Importo (€)", min_value=0.0, value=0.0, step=1.0, format="%.2f")
            paid = b.checkbox("Pagato")
            instr = c.selectbox("Istruttrice", INSTRUCTORS)
            note = st.text_area("Note prenotazione")
            st.info(f"Stato automatico: {auto_status(data, d, t)}")
            if st.button("Salva prenotazione", type="primary"):
                bk = create_booking(data, cid, d, t, amount, paid, instr, note)
                save_data(data, sha, f"Add booking {bk['name']}")
                request_section("📋 Archivio")
                st.session_state["archive_nonce"] = int(st.session_state.get("archive_nonce", 0)) + 1
                st.success(f"Prenotazione salvata: {bk['status']}.")
                st.rerun()


def render_clients(data, sha):
    st.subheader("Archivio clienti")
    with st.expander("➕ Inserisci nuovo cliente"):
        a, b = st.columns(2)
        last = a.text_input("Cognome", key="cl")
        first = b.text_input("Nome", key="cf")
        c, d = st.columns(2)
        phone = c.text_input("Telefono", key="cp")
        email = d.text_input("Email", key="ce")
        birth = st.text_input("Data di nascita", placeholder="gg-mm-aaaa", key="cb")
        notes = st.text_area("Note cliente", key="cn")
        if st.button("Salva cliente"):
            ok, msg, _ = add_client(data, first, last, phone, email, notes, birth)
            if ok:
                save_data(data, sha, "Add client")
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    sort_by = st.radio("Ordina per", ["Alfabetico", "Ultima visita"], horizontal=True)
    dfc = clients_df(data, sort_by)
    if dfc.empty:
        st.info("Nessun cliente presente.")
        return
    q = st.text_input("Cerca cliente").lower().strip()
    view = dfc[dfc.apply(lambda r: q in " ".join(map(str, r.values)).lower(), axis=1)] if q else dfc
    st.caption("Tabella clienti: clicca una riga per aprire la scheda qui sotto.")
    selected = client_grid(view, "client_grid")
    if selected:
        st.session_state["open_client_id"] = selected.get("ID")
    cid_open = st.session_state.get("open_client_id")
    if cid_open:
        st.divider()
        render_client_card(data, sha, cid_open, prefix="clienti")


def render_search(data):
    st.subheader("Cerca")
    q = st.text_input("Cerca per nome, telefono o email").lower().strip()
    dfa = archive_df(data)
    if q and not dfa.empty:
        res = dfa[dfa.apply(lambda r: q in " ".join(map(str, r.values)).lower(), axis=1)]
        st.dataframe(res.drop(columns=["Elimina", "ID", "Client ID"], errors="ignore"), use_container_width=True, hide_index=True)


def render_archive(data, sha):
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
    st.dataframe(per, use_container_width=True, hide_index=True)
    status = st.multiselect("Filtra stato archivio", ["Confermata", "Lista attesa", "Annullata"], default=["Confermata", "Lista attesa"])
    only = st.checkbox("Mostra in tabella solo il periodo selezionato", value=True)
    df = dfp.copy() if only else dfa.copy()
    if status:
        df = df[df["Stato"].isin(status)]
    st.markdown("#### Modifica importi, pagamenti e note")
    st.caption("Colonne editabili evidenziate: Email, Importo, Pagato, Note cliente e Note prenotazione. Clicca una riga per aprire la scheda cliente sotto.")
    grid_key = f"archive_grid_{st.session_state.get('archive_nonce', 0)}"
    edited, selected = archive_grid(df, grid_key)
    if selected and selected.get("Client ID"):
        st.session_state["open_client_id"] = selected.get("Client ID")
    cid_open = st.session_state.get("open_client_id")
    if cid_open:
        st.divider()
        render_client_card(data, sha, cid_open, prefix="archivio")
    a, b = st.columns(2)
    if a.button("Salva modifiche importi/pagamenti/note"):
        n = update_archive(data, edited)
        if n:
            save_data(data, sha, "Update archive")
            st.session_state["archive_nonce"] = int(st.session_state.get("archive_nonce", 0)) + 1
            st.success(f"Aggiornate {n} righe/prenotazioni.")
            st.rerun()
        else:
            st.info("Nessuna modifica da salvare.")
    ids = edited.loc[edited.get("Elimina", False).apply(to_bool) == True, "ID"].dropna().astype(str).tolist() if not edited.empty else []
    if b.button("Elimina selezionate", type="primary"):
        if not ids:
            st.error("Non hai selezionato nessuna prenotazione da eliminare.")
        else:
            n = delete_bookings(data, ids)
            save_data(data, sha, "Delete bookings")
            request_section("📋 Archivio")
            st.session_state["archive_nonce"] = int(st.session_state.get("archive_nonce", 0)) + 1
            st.success(f"Eliminate {n} prenotazioni.")
            st.rerun()
    a, b = st.columns(2)
    a.download_button("Scarica Excel", data=make_excel(edited), file_name="prenotazioni_pilates.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    b.download_button("Scarica PDF archivio", data=make_pdf(edited, label), file_name="archivio_prenotazioni_pilates.pdf", mime="application/pdf")


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
if not AGGRID_AVAILABLE:
    st.warning("AgGrid non è ancora installato: fai Reboot app da Streamlit Cloud.")

if "_next_section" in st.session_state:
    st.session_state["section"] = st.session_state.pop("_next_section")
if "section" not in st.session_state or st.session_state["section"] not in SECTIONS:
    st.session_state["section"] = "📅 Settimana"

section = st.radio("Sezione", SECTIONS, horizontal=True, key="section", label_visibility="collapsed")
st.divider()

if section == "📅 Settimana":
    render_week(data, sha)
elif section == "➕ Prenota":
    render_booking(data, sha)
elif section == "👤 Clienti":
    render_clients(data, sha)
elif section == "🔎 Cerca":
    render_search(data)
elif section == "📋 Archivio":
    render_archive(data, sha)
