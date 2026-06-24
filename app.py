import base64
import json
import os
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
import requests
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

CAPACITY = 4
APP_TITLE = "Prenotazioni Pilates Reformer"
LOCAL_DATA_PATH = "data/bookings.json"
INSTRUCTORS = ["Grazia", "Alice"]
GREEN = "#52A68A"
DARK = "#243142"

SCHEDULE = {
    0: ["08:30", "09:30", "10:30", "17:00", "18:00", "19:00"],
    1: ["09:30", "10:30", "11:30", "12:45", "14:30", "19:00"],
    2: ["08:30", "09:30", "10:30", "11:30", "12:45", "14:30", "15:30", "16:30", "17:30", "18:30"],
    3: ["17:00", "18:00", "19:00"],
    4: ["14:00", "15:00", "16:00", "17:00", "18:00", "19:00"],
}
DAY_NAMES = {0: "Lunedì", 1: "Martedì", 2: "Mercoledì", 3: "Giovedì", 4: "Venerdì", 5: "Sabato", 6: "Domenica"}


def render_logo_header() -> None:
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:18px; margin-bottom:4px;">
          <div style="width:96px; height:72px; background:{GREEN}; border-radius:50%; display:flex; flex-direction:column; align-items:center; justify-content:center; color:white; font-weight:900; letter-spacing:-2px; line-height:0.85; box-shadow:0 2px 10px rgba(0,0,0,.10);">
            <div style="font-size:26px;">BODY</div>
            <div style="font-size:20px; transform:skew(-10deg);">CENTER</div>
          </div>
          <div>
            <div style="font-size:42px; font-weight:800; color:{DARK}; line-height:1.1;">Prenotazioni Pilates Reformer</div>
            <div style="font-size:14px; color:#777; margin-top:6px;">Gestionale interno Body Center · uso staff · capienza massima 4 persone</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return os.environ.get(name, default)


def github_enabled() -> bool:
    return bool(get_secret("GITHUB_TOKEN") and get_secret("GITHUB_REPO") and get_secret("GITHUB_BRANCH", "main"))


def github_headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {get_secret('GITHUB_TOKEN')}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


def github_file_url() -> str:
    return f"https://api.github.com/repos/{get_secret('GITHUB_REPO')}/contents/{LOCAL_DATA_PATH}"


def load_data() -> Tuple[Dict[str, Any], str | None]:
    if github_enabled():
        r = requests.get(github_file_url(), headers=github_headers(), params={"ref": get_secret("GITHUB_BRANCH", "main")}, timeout=20)
        if r.status_code == 404:
            data = {"bookings": []}
            save_data(data, sha=None, message="Initialize bookings storage")
            return data, None
        r.raise_for_status()
        payload = r.json()
        content = base64.b64decode(payload["content"]).decode("utf-8")
        return json.loads(content), payload.get("sha")

    path = Path(LOCAL_DATA_PATH)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"bookings": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8")), None


def save_data(data: Dict[str, Any], sha: str | None = None, message: str = "Update bookings") -> None:
    if github_enabled():
        encoded = base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")).decode("utf-8")
        body = {"message": message, "content": encoded, "branch": get_secret("GITHUB_BRANCH", "main")}
        if sha:
            body["sha"] = sha
        r = requests.put(github_file_url(), headers=github_headers(), json=body, timeout=20)
        if r.status_code == 409:
            st.error("Conflitto: un'altra modifica è stata salvata. Ricarica la pagina e riprova.")
            st.stop()
        r.raise_for_status()
        return
    Path(LOCAL_DATA_PATH).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_date(d: date | str) -> date:
    if isinstance(d, date):
        return d
    return datetime.strptime(d, "%Y-%m-%d").date()


def date_key(d: date) -> str:
    return d.isoformat()


def next_working_days(start: date, n: int = 5) -> List[date]:
    days = []
    d = start
    while len(days) < n:
        if d.weekday() in SCHEDULE:
            days.append(d)
        d += timedelta(days=1)
    return days


def new_id() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S%f")


def money(v) -> float:
    try:
        return round(float(v or 0), 2)
    except Exception:
        return 0.0


def available_times_for_day(d: date) -> List[str]:
    return SCHEDULE.get(d.weekday(), [])


def get_bookings_for_slot(data: Dict[str, Any], d: date, time: str, include_cancelled: bool = False) -> List[Dict[str, Any]]:
    rows = []
    for b in data.get("bookings", []):
        if b.get("date") == date_key(d) and b.get("time") == time:
            if include_cancelled or b.get("status") != "Annullata":
                rows.append(b)
    return sorted(rows, key=lambda x: x.get("created_at", ""))


def confirmed_count(data: Dict[str, Any], d: date, time: str, exclude_id: str | None = None) -> int:
    return sum(1 for b in get_bookings_for_slot(data, d, time) if b.get("status") == "Confermata" and b.get("id") != exclude_id)


def slot_status(data: Dict[str, Any], d: date, time: str) -> Tuple[int, int, List[Dict[str, Any]], List[Dict[str, Any]]]:
    rows = get_bookings_for_slot(data, d, time)
    conf = [b for b in rows if b.get("status") == "Confermata"]
    wait = [b for b in rows if b.get("status") == "Lista attesa"]
    return len(conf), len(wait), conf, wait


def auto_status(data: Dict[str, Any], d: date, time: str) -> str:
    return "Confermata" if confirmed_count(data, d, time) < CAPACITY else "Lista attesa"


def status_icon(status: str) -> str:
    return {"Confermata": "✅", "Lista attesa": "⏳", "Annullata": "❌"}.get(status, "")


def login() -> bool:
    st.sidebar.header("Accesso staff")
    pwd = st.sidebar.text_input("Password", type="password")
    expected = get_secret("APP_PASSWORD", "pilates123")
    if pwd == expected:
        st.sidebar.success("Accesso consentito")
        return True
    if pwd:
        st.sidebar.error("Password non corretta")
    return False


def change_status(data: Dict[str, Any], booking_id: str, new_status: str) -> bool:
    for b in data.get("bookings", []):
        if b.get("id") == booking_id:
            d = parse_date(b["date"])
            t = b["time"]
            if new_status == "Confermata" and confirmed_count(data, d, t, exclude_id=booking_id) >= CAPACITY:
                st.error("Non puoi confermare: la lezione è già piena (4/4).")
                return False
            b["status"] = new_status
            return True
    st.error("Prenotazione non trovata.")
    return False


def delete_bookings(data: Dict[str, Any], ids: List[str]) -> int:
    ids = set(ids)
    old_len = len(data.get("bookings", []))
    data["bookings"] = [b for b in data.get("bookings", []) if b.get("id") not in ids]
    return old_len - len(data["bookings"])


def build_archive_rows(data: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for b in data.get("bookings", []):
        amount = money(b.get("amount", 0))
        paid = bool(b.get("paid", False))
        rows.append({
            "Eliminazione": False,
            "ID": b.get("id"),
            "Data": b.get("date"),
            "Giorno": b.get("day"),
            "Ora": b.get("time"),
            "Nome": b.get("name"),
            "Telefono": b.get("phone"),
            "Istruttrice": b.get("instructor", ""),
            "Stato": b.get("status"),
            "Importo": amount,
            "Pagato": paid,
            "Note": b.get("note"),
            "Inserita il": b.get("created_at"),
        })
    if not rows:
        return pd.DataFrame(columns=["Eliminazione", "ID", "Data", "Giorno", "Ora", "Nome", "Telefono", "Istruttrice", "Stato", "Importo", "Pagato", "Note", "Inserita il"])
    return pd.DataFrame(rows).sort_values(["Data", "Ora", "Nome"])


def payment_summary(df: pd.DataFrame) -> Tuple[float, float, float, pd.DataFrame]:
    if df.empty:
        per_instr = pd.DataFrame(columns=["Istruttrice", "Totale", "Pagato", "Non pagato"])
        return 0.0, 0.0, 0.0, per_instr
    work = df.copy()
    work["Importo"] = pd.to_numeric(work["Importo"], errors="coerce").fillna(0.0)
    work["Pagato"] = work["Pagato"].astype(bool)
    work = work[work["Stato"] != "Annullata"]
    total = float(work["Importo"].sum())
    paid_total = float(work.loc[work["Pagato"] == True, "Importo"].sum())
    unpaid_total = total - paid_total
    rows = []
    for instr in INSTRUCTORS:
        sub = work[work["Istruttrice"].fillna("") == instr]
        itotal = float(sub["Importo"].sum())
        ipaid = float(sub.loc[sub["Pagato"] == True, "Importo"].sum())
        rows.append({"Istruttrice": instr, "Totale": itotal, "Pagato": ipaid, "Non pagato": itotal - ipaid})
    return total, paid_total, unpaid_total, pd.DataFrame(rows)


def make_excel(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Archivio")
        ws = writer.sheets["Archivio"]
        for col in ws.columns:
            max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max(max_len + 2, 10), 35)
    output.seek(0)
    return output.getvalue()


def make_pdf(df: pd.DataFrame, title: str = "Archivio prenotazioni Pilates") -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=0.8 * cm, leftMargin=0.8 * cm, topMargin=0.8 * cm, bottomMargin=0.8 * cm)
    styles = getSampleStyleSheet()
    total, paid_total, unpaid_total, per_instr = payment_summary(df)
    elements = [
        Paragraph(f"<font color='{GREEN}'><b>BODY CENTER</b></font>", styles["Title"]),
        Paragraph(title, styles["Heading1"]),
        Paragraph(f"Generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]),
        Spacer(1, 0.25 * cm),
    ]
    totals_data = [
        ["Totale complessivo", "Totale pagato", "Totale non pagato"],
        [f"€ {total:.2f}", f"€ {paid_total:.2f}", f"€ {unpaid_total:.2f}"],
    ]
    totals_table = Table(totals_data, colWidths=[5 * cm, 5 * cm, 5 * cm])
    totals_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#52A68A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
    ]))
    elements += [totals_table, Spacer(1, 0.25 * cm)]
    instr_data = [["Istruttrice", "Totale", "Pagato", "Non pagato"]] + [[r["Istruttrice"], f"€ {r['Totale']:.2f}", f"€ {r['Pagato']:.2f}", f"€ {r['Non pagato']:.2f}"] for _, r in per_instr.iterrows()]
    instr_table = Table(instr_data, colWidths=[4 * cm, 4 * cm, 4 * cm, 4 * cm])
    instr_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243142")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ]))
    elements += [Paragraph("Totali per istruttrice", styles["Heading2"]), instr_table, Spacer(1, 0.35 * cm)]
    visible_cols = ["Data", "Giorno", "Ora", "Nome", "Telefono", "Istruttrice", "Stato", "Importo", "Pagato", "Note"]
    pdf_df = df[visible_cols].copy() if not df.empty else pd.DataFrame(columns=visible_cols)
    pdf_df["Pagato"] = pdf_df["Pagato"].map(lambda x: "Sì" if bool(x) else "No")
    pdf_df["Importo"] = pdf_df["Importo"].map(lambda x: f"€ {money(x):.2f}")
    pdf_df = pdf_df.fillna("").astype(str)
    table_data = [visible_cols] + pdf_df.values.tolist()
    table = Table(table_data, repeatRows=1, colWidths=[1.8*cm, 1.8*cm, 1.2*cm, 3.4*cm, 2.4*cm, 2.0*cm, 1.8*cm, 1.5*cm, 1.3*cm, 5.8*cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f5c8f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
    ]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def update_payment_from_editor(data: Dict[str, Any], edited_df: pd.DataFrame) -> int:
    updates = 0
    by_id = {b.get("id"): b for b in data.get("bookings", [])}
    for _, row in edited_df.iterrows():
        bid = row.get("ID")
        if bid in by_id:
            new_amount = money(row.get("Importo", 0))
            new_paid = bool(row.get("Pagato", False))
            if money(by_id[bid].get("amount", 0)) != new_amount or bool(by_id[bid].get("paid", False)) != new_paid:
                by_id[bid]["amount"] = new_amount
                by_id[bid]["paid"] = new_paid
                updates += 1
    return updates


st.set_page_config(page_title=APP_TITLE, page_icon="🧘", layout="wide")
render_logo_header()

if not github_enabled():
    st.warning("Modalità locale: utile per prova. Per usarla online con tua socia, configura i Secrets GitHub su Streamlit.")

if not login():
    st.info("Inserisci la password nella barra laterale.")
    st.stop()

try:
    data, sha = load_data()
except Exception as e:
    st.error(f"Errore caricamento dati: {e}")
    st.stop()

tab1, tab2, tab3, tab4 = st.tabs(["📅 Settimana", "➕ Prenota", "🔎 Cerca cliente", "📋 Archivio"])

with tab1:
    st.subheader("Vista settimanale")
    today = date.today()
    selected = st.date_input("Scegli la data di partenza", value=today, min_value=today, format="DD/MM/YYYY")
    selected = max(parse_date(selected), today)
    days = next_working_days(selected, 5)
    st.caption("La vista settimanale parte da oggi e non mostra date passate. L'archivio mantiene invece tutte le prenotazioni, anche passate.")
    for d in days:
        st.markdown(f"### {DAY_NAMES[d.weekday()]} {d.strftime('%d/%m/%Y')}")
        cols = st.columns(3)
        for idx, t in enumerate(available_times_for_day(d)):
            with cols[idx % 3]:
                n_conf, _, conf, wait = slot_status(data, d, t)
                label = f"{t} — {n_conf}/{CAPACITY}"
                if n_conf >= CAPACITY:
                    st.error(label)
                elif n_conf == 0:
                    st.info(label)
                else:
                    st.success(label)
                for i, b in enumerate(conf, 1):
                    paid_txt = "pagato" if bool(b.get("paid", False)) else "non pagato"
                    istr = b.get("instructor", "")
                    st.write(f"{i}. {b.get('name','')} · {istr} · € {money(b.get('amount', 0)):.2f} · {paid_txt}")
                if not conf:
                    st.caption("Nessun prenotato")
                if wait:
                    st.caption("Lista d'attesa:")
                    for b in wait:
                        st.caption(f"• {b.get('name','')} · {b.get('phone','')}")
                with st.expander("Gestisci"):
                    rows = get_bookings_for_slot(data, d, t, include_cancelled=True)
                    if not rows:
                        st.caption("Nessuna prenotazione da gestire.")
                    for b in rows:
                        st.markdown(f"**{status_icon(b.get('status'))} {b.get('name','')}** — {b.get('phone','')} — {b.get('instructor','')}")
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            if st.button("Conferma", key=f"confirm_{b['id']}"):
                                if change_status(data, b["id"], "Confermata"):
                                    save_data(data, sha, "Conferma prenotazione")
                                    st.rerun()
                        with c2:
                            if st.button("Attesa", key=f"wait_{b['id']}"):
                                if change_status(data, b["id"], "Lista attesa"):
                                    save_data(data, sha, "Sposta in lista attesa")
                                    st.rerun()
                        with c3:
                            if st.button("Annulla", key=f"cancel_{b['id']}"):
                                if change_status(data, b["id"], "Annullata"):
                                    save_data(data, sha, "Annulla prenotazione")
                                    st.rerun()

with tab2:
    st.subheader("Nuova prenotazione")
    today = date.today()
    c1, c2 = st.columns(2)
    with c1:
        d = st.date_input("Data", value=today, min_value=today, format="DD/MM/YYYY", key="new_date")
    d = parse_date(d)
    times = available_times_for_day(d)
    if not times:
        st.warning("In questa data non sono previsti corsi.")
    else:
        with c2:
            t = st.selectbox("Orario", times)
        n_conf, _, _, _ = slot_status(data, d, t)
        st.write(f"Posti confermati: **{n_conf}/{CAPACITY}**")
        if n_conf >= CAPACITY:
            st.warning("Lezione piena: il nuovo inserimento andrà automaticamente in lista d'attesa.")
        name = st.text_input("Nome cliente")
        phone = st.text_input("Telefono")
        c3, c4, c5 = st.columns(3)
        with c3:
            amount = st.number_input("Importo (€)", min_value=0.0, value=0.0, step=1.0, format="%.2f")
        with c4:
            paid = st.checkbox("Pagato")
        with c5:
            instructor = st.selectbox("Istruttrice", INSTRUCTORS)
        note = st.text_area("Note", placeholder="es. recupero, prova, eventuali indicazioni")
        proposed = auto_status(data, d, t)
        st.info(f"Stato automatico: {proposed}")
        if st.button("Salva prenotazione", type="primary"):
            if not name.strip():
                st.error("Inserisci il nome.")
            else:
                booking = {"id": new_id(), "created_at": datetime.now().isoformat(timespec="seconds"), "date": date_key(d), "day": DAY_NAMES[d.weekday()], "time": t, "name": name.strip(), "phone": phone.strip(), "note": note.strip(), "status": auto_status(data, d, t), "amount": money(amount), "paid": bool(paid), "instructor": instructor, "created_by": "staff"}
                data["bookings"].append(booking)
                try:
                    save_data(data, sha, f"Add booking {booking['name']} {booking['date']} {booking['time']}")
                    st.success(f"Prenotazione salvata: {booking['status']}.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore salvataggio: {e}")

with tab3:
    st.subheader("Cerca cliente")
    query = st.text_input("Cerca per nome o telefono").strip().lower()
    rows = []
    if query:
        for b in data.get("bookings", []):
            haystack = f"{b.get('name','')} {b.get('phone','')}".lower()
            if query in haystack:
                rows.append({"Data": b.get("date"), "Giorno": b.get("day"), "Ora": b.get("time"), "Nome": b.get("name"), "Telefono": b.get("phone"), "Istruttrice": b.get("instructor", ""), "Stato": b.get("status"), "Importo": money(b.get("amount", 0)), "Pagato": bool(b.get("paid", False)), "Note": b.get("note")})
    if query and rows:
        st.dataframe(pd.DataFrame(rows).sort_values(["Data", "Ora"]), use_container_width=True, hide_index=True)
    elif query:
        st.info("Nessun risultato.")

with tab4:
    st.subheader("Archivio, pagamenti e statistiche")
    df_all = build_archive_rows(data)
    if df_all.empty:
        st.info("Nessuna prenotazione presente.")
    else:
        month = st.date_input("Statistiche mese", value=date.today(), format="DD/MM/YYYY", key="stats_month")
        month_prefix = parse_date(month).strftime("%Y-%m")
        df_month = df_all[df_all["Data"].astype(str).str.startswith(month_prefix)].copy()
        total, paid_total, unpaid_total, per_instr = payment_summary(df_month)
        c1, c2, c3 = st.columns(3)
        c1.metric("Totale complessivo", f"€ {total:.2f}")
        c2.metric("Totale pagato", f"€ {paid_total:.2f}")
        c3.metric("Totale non pagato", f"€ {unpaid_total:.2f}")
        c4, c5, c6 = st.columns(3)
        c4.metric("Confermate mese", int((df_month["Stato"] == "Confermata").sum()))
        c5.metric("Lista attesa mese", int((df_month["Stato"] == "Lista attesa").sum()))
        c6.metric("Annullate mese", int((df_month["Stato"] == "Annullata").sum()))
        st.markdown("#### Totali per istruttrice")
        st.dataframe(per_instr, use_container_width=True, hide_index=True)
        unpaid = df_month[(df_month["Pagato"] == False) & (pd.to_numeric(df_month["Importo"], errors="coerce").fillna(0) > 0) & (df_month["Stato"] != "Annullata")]
        if not unpaid.empty:
            st.warning("Clienti con importo non pagato: " + ", ".join(unpaid["Nome"].fillna("").astype(str).unique()))
        status_filter = st.multiselect("Filtra stato", ["Confermata", "Lista attesa", "Annullata"], default=["Confermata", "Lista attesa"])
        df = df_all.copy()
        if status_filter:
            df = df[df["Stato"].isin(status_filter)]
        st.caption("L'archivio mostra tutte le prenotazioni, comprese quelle passate. Puoi modificare Importo/Pagato e cancellare righe selezionate.")
        editor_cols = ["Eliminazione", "Data", "Giorno", "Ora", "Nome", "Telefono", "Istruttrice", "Stato", "Importo", "Pagato", "Note", "Inserita il", "ID"]
        edited = st.data_editor(df[editor_cols], use_container_width=True, hide_index=True, column_config={"Eliminazione": st.column_config.CheckboxColumn("Eliminazione"), "Pagato": st.column_config.CheckboxColumn("Pagato"), "Importo": st.column_config.NumberColumn("Importo (€)", min_value=0.0, step=1.0, format="%.2f"), "ID": None}, disabled=["Data", "Giorno", "Ora", "Nome", "Telefono", "Istruttrice", "Stato", "Note", "Inserita il"], key="archive_editor")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Salva modifiche importi/pagamenti"):
                n = update_payment_from_editor(data, edited)
                if n:
                    try:
                        save_data(data, sha, "Update payment data")
                        st.success(f"Aggiornate {n} prenotazioni.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore salvataggio: {e}")
                else:
                    st.info("Nessuna modifica da salvare.")
        with col_b:
            to_delete = edited.loc[edited["Eliminazione"] == True, "ID"].dropna().astype(str).tolist()
            if st.button("Elimina selezionate", type="primary"):
                if not to_delete:
                    st.error("Non hai selezionato nessuna prenotazione da eliminare.")
                else:
                    n = delete_bookings(data, to_delete)
                    try:
                        save_data(data, sha, "Delete selected bookings")
                        st.success(f"Eliminate {n} prenotazioni.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore salvataggio: {e}")
        visible_df = edited.drop(columns=["Eliminazione", "ID"], errors="ignore")
        excel_bytes = make_excel(visible_df)
        pdf_bytes = make_pdf(visible_df, title="Archivio prenotazioni Pilates - Body Center")
        d1, d2 = st.columns(2)
        with d1:
            st.download_button("Scarica Excel", data=excel_bytes, file_name="prenotazioni_pilates.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with d2:
            st.download_button("Scarica PDF archivio", data=pdf_bytes, file_name="archivio_prenotazioni_pilates.pdf", mime="application/pdf")
