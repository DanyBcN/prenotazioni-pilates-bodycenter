import base64
import copy
import json
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple

import pandas as pd
import requests
import streamlit as st


# =========================
# CONFIGURAZIONE BASE
# =========================

CAPACITY = 4
APP_TITLE = "Prenotazioni Pilates Reformer"
LOCAL_DATA_PATH = "data/bookings.json"

SCHEDULE = {
    0: ["08:30", "09:30", "10:30", "17:00", "18:00", "19:00"],  # Lunedì
    1: ["09:30", "10:30", "11:30", "12:45", "14:30", "19:00"],  # Martedì
    2: ["08:30", "09:30", "10:30", "11:30", "12:45", "14:30", "15:30", "16:30", "17:30", "18:30"],  # Mercoledì
    3: ["17:00", "18:00", "19:00"],  # Giovedì
    4: ["14:00", "15:00", "16:00", "17:00", "18:00", "19:00"],  # Venerdì
}

DAY_NAMES = {
    0: "Lunedì",
    1: "Martedì",
    2: "Mercoledì",
    3: "Giovedì",
    4: "Venerdì",
    5: "Sabato",
    6: "Domenica",
}


# =========================
# STORAGE: GitHub JSON
# =========================

def get_secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return os.environ.get(name, default)


def github_enabled() -> bool:
    return all([
        get_secret("GITHUB_TOKEN"),
        get_secret("GITHUB_REPO"),
        get_secret("GITHUB_BRANCH", "main"),
    ])


def github_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {get_secret('GITHUB_TOKEN')}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def github_file_url() -> str:
    repo = get_secret("GITHUB_REPO")
    return f"https://api.github.com/repos/{repo}/contents/{LOCAL_DATA_PATH}"


def load_data() -> Tuple[Dict[str, Any], str | None]:
    """Ritorna dati e SHA file GitHub, se disponibile."""
    if github_enabled():
        params = {"ref": get_secret("GITHUB_BRANCH", "main")}
        r = requests.get(github_file_url(), headers=github_headers(), params=params, timeout=20)

        if r.status_code == 404:
            data = {"bookings": []}
            save_data(data, sha=None, message="Initialize bookings storage")
            return data, None

        r.raise_for_status()
        payload = r.json()
        content = base64.b64decode(payload["content"]).decode("utf-8")
        return json.loads(content), payload.get("sha")

    # Fallback locale
    path = Path(LOCAL_DATA_PATH)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"bookings": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8")), None


def save_data(data: Dict[str, Any], sha: str | None = None, message: str = "Update bookings") -> None:
    if github_enabled():
        encoded = base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")).decode("utf-8")
        body = {
            "message": message,
            "content": encoded,
            "branch": get_secret("GITHUB_BRANCH", "main"),
        }
        if sha:
            body["sha"] = sha

        r = requests.put(github_file_url(), headers=github_headers(), json=body, timeout=20)
        if r.status_code == 409:
            st.error("Conflitto di salvataggio: qualcun altro ha modificato le prenotazioni. Ricarica la pagina e riprova.")
            st.stop()
        r.raise_for_status()
        return

    Path(LOCAL_DATA_PATH).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# =========================
# UTILITY
# =========================

def parse_date(d: date | str) -> date:
    if isinstance(d, date):
        return d
    return datetime.strptime(d, "%Y-%m-%d").date()


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def date_key(d: date) -> str:
    return d.isoformat()


def new_id() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S%f")


def status_icon(status: str) -> str:
    return {
        "Confermata": "✅",
        "Lista attesa": "⏳",
        "Annullata": "❌",
    }.get(status, "")


def get_bookings_for_slot(data: Dict[str, Any], d: date, time: str, include_cancelled: bool = False) -> List[Dict[str, Any]]:
    out = []
    for b in data.get("bookings", []):
        if b.get("date") == date_key(d) and b.get("time") == time:
            if include_cancelled or b.get("status") != "Annullata":
                out.append(b)
    return sorted(out, key=lambda x: x.get("created_at", ""))


def confirmed_count(data: Dict[str, Any], d: date, time: str) -> int:
    return sum(1 for b in get_bookings_for_slot(data, d, time) if b.get("status") == "Confermata")


def next_status(data: Dict[str, Any], d: date, time: str) -> str:
    return "Confermata" if confirmed_count(data, d, time) < CAPACITY else "Lista attesa"


def available_times_for_day(d: date) -> List[str]:
    return SCHEDULE.get(d.weekday(), [])


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


# =========================
# UI
# =========================

st.set_page_config(page_title=APP_TITLE, page_icon="🧘", layout="wide")

st.title("🧘 Prenotazioni Pilates Reformer")
st.caption("Gestionale interno Body Center · uso staff · capienza 4 persone per lezione")

if not github_enabled():
    st.warning(
        "Modalità locale: utile per prova. Per usarla online con tua socia, configura i secrets GitHub su Streamlit."
    )

if not login():
    st.info("Inserisci la password nella barra laterale.")
    st.stop()

try:
    data, sha = load_data()
except Exception as e:
    st.error(f"Errore caricamento dati: {e}")
    st.stop()

tab1, tab2, tab3 = st.tabs(["📅 Settimana", "➕ Nuova prenotazione", "📋 Archivio"])


with tab1:
    st.subheader("Vista settimanale")

    selected = st.date_input("Scegli una data della settimana", value=date.today(), format="DD/MM/YYYY")
    start = week_start(parse_date(selected))
    days = [start + timedelta(days=i) for i in range(5)]

    for d in days:
        st.markdown(f"### {DAY_NAMES[d.weekday()]} {d.strftime('%d/%m/%Y')}")
        times = available_times_for_day(d)

        if not times:
            st.write("Nessun corso.")
            continue

        cols = st.columns(3)
        for idx, t in enumerate(times):
            with cols[idx % 3]:
                slot_bookings = get_bookings_for_slot(data, d, t)
                conf = [b for b in slot_bookings if b["status"] == "Confermata"]
                wait = [b for b in slot_bookings if b["status"] == "Lista attesa"]

                label = f"{t} — {len(conf)}/{CAPACITY}"
                if len(conf) >= CAPACITY:
                    st.error(label)
                elif len(conf) == 0:
                    st.info(label)
                else:
                    st.success(label)

                if conf:
                    for n, b in enumerate(conf, 1):
                        st.write(f"{n}. {b['name']} · {b.get('phone','')}")
                else:
                    st.caption("Nessun prenotato")

                if wait:
                    st.caption("Lista attesa:")
                    for b in wait:
                        st.caption(f"• {b['name']} · {b.get('phone','')}")

                with st.expander("Gestisci"):
                    all_slot = get_bookings_for_slot(data, d, t, include_cancelled=True)
                    if not all_slot:
                        st.caption("Nessuna prenotazione da gestire.")
                    for b in all_slot:
                        st.markdown(f"**{status_icon(b['status'])} {b['name']}** — {b.get('phone','')}")
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            if st.button("Conferma", key=f"conf_{b['id']}"):
                                b["status"] = "Confermata"
                                save_data(data, sha, "Conferma prenotazione")
                                st.rerun()
                        with c2:
                            if st.button("Attesa", key=f"wait_{b['id']}"):
                                b["status"] = "Lista attesa"
                                save_data(data, sha, "Lista attesa prenotazione")
                                st.rerun()
                        with c3:
                            if st.button("Annulla", key=f"ann_{b['id']}"):
                                b["status"] = "Annullata"
                                save_data(data, sha, "Annulla prenotazione")
                                st.rerun()


with tab2:
    st.subheader("Inserisci prenotazione")

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

        name = st.text_input("Nome cliente")
        phone = st.text_input("Telefono")
        note = st.text_area("Note", placeholder="es. recupero, prova, pagato, eventuali indicazioni")

        current = confirmed_count(data, d, t)
        st.write(f"Posti attualmente occupati: **{current}/{CAPACITY}**")
        suggested = next_status(data, d, t)
        status = st.selectbox("Stato", ["Confermata", "Lista attesa"], index=0 if suggested == "Confermata" else 1)

        if st.button("Salva prenotazione", type="primary"):
            if not name.strip():
                st.error("Inserisci il nome.")
            else:
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
    st.subheader("Archivio prenotazioni")

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

    if rows:
        df = pd.DataFrame(rows).sort_values(["Data", "Ora", "Nome"])
        status_filter = st.multiselect("Filtra stato", ["Confermata", "Lista attesa", "Annullata"], default=["Confermata", "Lista attesa"])
        if status_filter:
            df = df[df["Stato"].isin(status_filter)]
        st.dataframe(df, use_container_width=True, hide_index=True)

        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("Scarica Excel/CSV", data=csv, file_name="prenotazioni_pilates.csv", mime="text/csv")
    else:
        st.info("Nessuna prenotazione presente.")