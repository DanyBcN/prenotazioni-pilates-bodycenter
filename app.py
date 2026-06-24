import base64
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
import requests
import streamlit as st


CAPACITY = 4
APP_TITLE = "Prenotazioni Pilates Reformer"
LOCAL_DATA_PATH = "data/bookings.json"

SCHEDULE = {
    0: ["08:30", "09:30", "10:30", "17:00", "18:00", "19:00"],
    1: ["09:30", "10:30", "11:30", "12:45", "14:30", "19:00"],
    2: ["08:30", "09:30", "10:30", "11:30", "12:45", "14:30", "15:30", "16:30", "17:30", "18:30"],
    3: ["17:00", "18:00", "19:00"],
    4: ["14:00", "15:00", "16:00", "17:00", "18:00", "19:00"],
}

DAY_NAMES = {0: "Lunedì", 1: "Martedì", 2: "Mercoledì", 3: "Giovedì", 4: "Venerdì", 5: "Sabato", 6: "Domenica"}


def get_secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return os.environ.get(name, default)


def github_enabled() -> bool:
    return bool(get_secret("GITHUB_TOKEN") and get_secret("GITHUB_REPO") and get_secret("GITHUB_BRANCH", "main"))


def github_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {get_secret('GITHUB_TOKEN')}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def github_file_url() -> str:
    return f"https://api.github.com/repos/{get_secret('GITHUB_REPO')}/contents/{LOCAL_DATA_PATH}"


def load_data() -> Tuple[Dict[str, Any], str | None]:
    if github_enabled():
        r = requests.get(
            github_file_url(),
            headers=github_headers(),
            params={"ref": get_secret("GITHUB_BRANCH", "main")},
            timeout=20,
        )
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
            st.error("Conflitto: la tua socia ha appena salvato una modifica. Ricarica la pagina e riprova.")
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


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def new_id() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S%f")


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
    return sum(
        1 for b in get_bookings_for_slot(data, d, time)
        if b.get("status") == "Confermata" and b.get("id") != exclude_id
    )


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


st.set_page_config(page_title=APP_TITLE, page_icon="🧘", layout="wide")
st.title("🧘 Prenotazioni Pilates Reformer")
st.caption("Gestionale interno Body Center · uso staff · capienza massima 4 persone")

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
    selected = st.date_input("Scegli una data della settimana", value=date.today(), format="DD/MM/YYYY")
    start = week_start(parse_date(selected))
    days = [start + timedelta(days=i) for i in range(5)]

    for d in days:
        st.markdown(f"### {DAY_NAMES[d.weekday()]} {d.strftime('%d/%m/%Y')}")
        times = available_times_for_day(d)
        cols = st.columns(3)

        for idx, t in enumerate(times):
            with cols[idx % 3]:
                n_conf, n_wait, conf, wait = slot_status(data, d, t)
                label = f"{t} — {n_conf}/{CAPACITY}"
                if n_conf >= CAPACITY:
                    st.error(label)
                elif n_conf == 0:
                    st.info(label)
                else:
                    st.success(label)

                for i, b in enumerate(conf, 1):
                    st.write(f"{i}. {b.get('name','')} · {b.get('phone','')}")
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
                        st.markdown(f"**{status_icon(b.get('status'))} {b.get('name','')}** — {b.get('phone','')}")
                        if b.get("note"):
                            st.caption(b.get("note"))

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

    c1, c2 = st.columns(2)
    with c1:
        d = st.date_input("Data", value=date.today(), format="DD/MM/YYYY", key="new_date")
    d = parse_date(d)

    times = available_times_for_day(d)
    if not times:
        st.warning("In questa data non sono previsti corsi.")
    else:
        with c2:
            t = st.selectbox("Orario", times)

        n_conf, n_wait, conf, wait = slot_status(data, d, t)
        st.write(f"Posti confermati: **{n_conf}/{CAPACITY}**")
        if n_conf >= CAPACITY:
            st.warning("Lezione piena: il nuovo inserimento andrà automaticamente in lista d'attesa.")

        name = st.text_input("Nome cliente")
        phone = st.text_input("Telefono")
        note = st.text_area("Note", placeholder="es. recupero, prova, pagato, eventuali indicazioni")

        proposed = auto_status(data, d, t)
        st.info(f"Stato automatico: {proposed}")

        if st.button("Salva prenotazione", type="primary"):
            if not name.strip():
                st.error("Inserisci il nome.")
            else:
                status = auto_status(data, d, t)
                booking = {
                    "id": new_id(),
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                    "date": date_key(d),
                    "day": DAY_NAMES[d.weekday()],
                    "time": t,
                    "name": name.strip(),
                    "phone": phone.strip(),
                    "note": note.strip(),
                    "status": status,
                    "created_by": "staff",
                }
                data["bookings"].append(booking)
                try:
                    save_data(data, sha, f"Add booking {booking['name']} {booking['date']} {booking['time']}")
                    st.success(f"Prenotazione salvata: {status}.")
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
                rows.append({
                    "Data": b.get("date"),
                    "Giorno": b.get("day"),
                    "Ora": b.get("time"),
                    "Nome": b.get("name"),
                    "Telefono": b.get("phone"),
                    "Stato": b.get("status"),
                    "Note": b.get("note"),
                })

    if query and rows:
        st.dataframe(pd.DataFrame(rows).sort_values(["Data", "Ora"]), use_container_width=True, hide_index=True)
    elif query:
        st.info("Nessun risultato.")


with tab4:
    st.subheader("Archivio e statistiche")

    rows = []
    for b in data.get("bookings", []):
        rows.append({
            "Data": b.get("date"),
            "Giorno": b.get("day"),
            "Ora": b.get("time"),
            "Nome": b.get("name"),
            "Telefono": b.get("phone"),
            "Stato": b.get("status"),
            "Note": b.get("note"),
            "Inserita il": b.get("created_at"),
        })

    if not rows:
        st.info("Nessuna prenotazione presente.")
    else:
        df = pd.DataFrame(rows).sort_values(["Data", "Ora", "Nome"])
        month = st.date_input("Statistiche mese", value=date.today(), format="DD/MM/YYYY", key="stats_month")
        month_prefix = parse_date(month).strftime("%Y-%m")
        df_month = df[df["Data"].astype(str).str.startswith(month_prefix)]

        c1, c2, c3 = st.columns(3)
        c1.metric("Confermate mese", int((df_month["Stato"] == "Confermata").sum()))
        c2.metric("Lista attesa mese", int((df_month["Stato"] == "Lista attesa").sum()))
        c3.metric("Annullate mese", int((df_month["Stato"] == "Annullata").sum()))

        status_filter = st.multiselect(
            "Filtra stato",
            ["Confermata", "Lista attesa", "Annullata"],
            default=["Confermata", "Lista attesa"],
        )
        if status_filter:
            df = df[df["Stato"].isin(status_filter)]

        st.dataframe(df, use_container_width=True, hide_index=True)
        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("Scarica Excel/CSV", data=csv, file_name="prenotazioni_pilates.csv", mime="text/csv")
