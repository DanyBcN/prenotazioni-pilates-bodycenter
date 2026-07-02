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

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
except Exception:
    colors = None
    A4 = landscape = getSampleStyleSheet = cm = SimpleDocTemplate = Paragraph = Spacer = Table = TableStyle = Image = None

APP_TITLE = "Prenotazioni Pilates Reformer"
DATA_PATH = "data/bookings.json"
BACKUP_DIR = "data/backups"
LOGO_PATH = "assets/logo.png"
INSTRUCTORS = ["Grazia", "Alice"]
CAPACITY = 4
PLANNING_DAYS = 92
SHARE_INSTRUCTOR = 0.40
SHARE_GYM = 0.60
AUDIT_LOG_LIMIT = 1000

SCHEDULE = {
    0: ["08:30", "09:30", "10:30", "17:00", "18:00", "19:00"],
    1: ["09:30", "10:30", "11:30", "12:45", "14:30", "19:00"],
    2: ["08:30", "09:30", "10:30", "11:30", "12:45", "14:30", "15:30", "16:30", "17:30", "18:30"],
    3: ["17:00", "18:00", "19:00"],
    4: ["14:00", "15:00", "16:00", "17:00", "18:00", "19:00"],
}
DAY_ABBR = {0: "Lun", 1: "Mar", 2: "Mer", 3: "Gio", 4: "Ven", 5: "Sab", 6: "Dom"}
DAY_FULL = {0: "Lunedì", 1: "Martedì", 2: "Mercoledì", 3: "Giovedì", 4: "Venerdì", 5: "Sabato", 6: "Domenica"}
MONTHS = {1: "gennaio", 2: "febbraio", 3: "marzo", 4: "aprile", 5: "maggio", 6: "giugno", 7: "luglio", 8: "agosto", 9: "settembre", 10: "ottobre", 11: "novembre", 12: "dicembre"}


def secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return os.environ.get(name, default)


def github_enabled() -> bool:
    return bool(secret("GITHUB_TOKEN") and secret("GITHUB_REPO") and secret("GITHUB_BRANCH", "main"))


def github_url() -> str:
    return f"https://api.github.com/repos/{secret('GITHUB_REPO')}/contents/{DATA_PATH}"


def github_headers() -> dict:
    return {
        "Authorization": f"Bearer {secret('GITHUB_TOKEN')}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def parse_date(value) -> date:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except Exception:
            pass
    return pd.to_datetime(text, dayfirst=True).date()


def date_key(value) -> str:
    return parse_date(value).isoformat()


def date_it(value) -> str:
    try:
        return parse_date(value).strftime("%d/%m/%Y")
    except Exception:
        return ""


def date_label(value) -> str:
    try:
        d = parse_date(value)
        return f"{DAY_ABBR[d.weekday()]} {d.day} {MONTHS[d.month]} {str(d.year)[-2:]}"
    except Exception:
        return str(value or "")


def money(value) -> float:
    try:
        return round(float(value or 0), 2)
    except Exception:
        return 0.0


def yes(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "si", "sì", "yes", "y"}


def new_id(prefix: str = "") -> str:
    return prefix + datetime.now().strftime("%Y%m%d%H%M%S%f")


def normalize(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def client_key(first: str, last: str) -> str:
    return f"{normalize(first)}|{normalize(last)}"


def full_name(client: dict) -> str:
    if not client:
        return ""
    return f"{str(client.get('last_name', '')).strip()} {str(client.get('first_name', '')).strip()}".strip()


def split_name(name: str):
    parts = str(name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[1:]), parts[0]


def is_gift(booking: dict) -> bool:
    return bool(booking.get("gift", False)) or "omaggio" in str(booking.get("note", "")).lower()


def instructor_share() -> float:
    try:
        return float(secret("INSTRUCTOR_SHARE", str(SHARE_INSTRUCTOR)))
    except Exception:
        return SHARE_INSTRUCTOR


def gym_share() -> float:
    try:
        return float(secret("GYM_SHARE", str(SHARE_GYM)))
    except Exception:
        return SHARE_GYM


def users_config() -> dict:
    raw = secret("USERS", "").strip()
    if raw:
        try:
            users = json.loads(raw)
            return {str(k).lower().strip(): v for k, v in users.items() if isinstance(v, dict)}
        except Exception as exc:
            st.error(f"Secret USERS non valido: {exc}")
            st.stop()
    return {"bodycenter": {"password": secret("APP_PASSWORD", "pilates123"), "role": "admin"}}


def current_user() -> str:
    return st.session_state.get("current_user", "bodycenter")


def current_role() -> str:
    return st.session_state.get("current_role", "admin")


def is_admin() -> bool:
    return current_role() == "admin"


def current_instructor() -> str:
    user = current_user().lower().strip()
    return next((name for name in INSTRUCTORS if name.lower() == user), "")


def allowed_sections():
    if is_admin():
        return ["Planning", "Prenota", "Incassi", "Clienti", "Cerca", "Archivio"]
    return ["Planning", "Prenota", "Incassi", "Clienti"]


def navigate(section: str):
    st.session_state["_next_section"] = section
    st.rerun()


def audit_event(data: dict, action: str, target_type: str = "", target_id: str = "", details: dict | None = None):
    entry = {
        "id": new_id("audit_"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "user": current_user(),
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "details": details or {},
    }
    data.setdefault("audit_log", []).append(entry)
    data["audit_log"] = data["audit_log"][-AUDIT_LOG_LIMIT:]
    return entry


def backup_local_data():
    path = Path(DATA_PATH)
    if not path.exists():
        return
    backup_dir = Path(BACKUP_DIR)
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"bookings_{timestamp}.json"
    backup_path.write_bytes(path.read_bytes())


def load_data():
    if st.session_state.get("_fresh_data") is not None:
        return st.session_state.pop("_fresh_data"), st.session_state.pop("_fresh_sha", None)

    if github_enabled():
        response = requests.get(
            github_url(),
            headers=github_headers(),
            params={"ref": secret("GITHUB_BRANCH", "main")},
            timeout=20,
        )
        if response.status_code == 404:
            data = {"bookings": [], "clients": [], "settlements": []}
            save_data(data, None, "Initialize storage")
            return data, None
        response.raise_for_status()
        payload = response.json()
        return json.loads(base64.b64decode(payload["content"]).decode("utf-8")), payload.get("sha")

    path = Path(DATA_PATH)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"bookings": [], "clients": [], "settlements": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8")), None


def save_data(data: dict, sha=None, message: str = "Update data"):
    if github_enabled():
        body = {
            "message": message,
            "content": base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")).decode("ascii"),
            "branch": secret("GITHUB_BRANCH", "main"),
        }
        if sha:
            body["sha"] = sha
        response = requests.put(github_url(), headers=github_headers(), json=body, timeout=20)
        if response.status_code == 409:
            st.error("Conflitto di salvataggio: ricarica la pagina e riprova.")
            st.stop()
        response.raise_for_status()
        st.session_state["_fresh_data"] = data
        try:
            st.session_state["_fresh_sha"] = response.json().get("content", {}).get("sha")
        except Exception:
            st.session_state["_fresh_sha"] = None
        return

    Path(DATA_PATH).parent.mkdir(parents=True, exist_ok=True)
    backup_local_data()
    Path(DATA_PATH).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    st.session_state["_fresh_data"] = data


def ensure_data(data: dict) -> dict:
    data.setdefault("bookings", [])
    data.setdefault("clients", [])
    data.setdefault("settlements", [])
    data.setdefault("audit_log", [])

    for client in data["clients"]:
        client.setdefault("id", new_id("c_"))
        client.setdefault("first_name", "")
        client.setdefault("last_name", "")
        client.setdefault("phone", "")
        client.setdefault("email", "")
        client.setdefault("notes", "")
        client.setdefault("birth_date", "")
        client.setdefault("created_at", "")

    existing = {client_key(c.get("first_name", ""), c.get("last_name", "")): c for c in data["clients"]}

    for booking in data["bookings"]:
        booking.setdefault("id", new_id("b_"))
        booking.setdefault("created_at", "")
        booking.setdefault("date", date.today().isoformat())
        booking.setdefault("day", "")
        booking.setdefault("time", "")
        booking.setdefault("name", "")
        booking.setdefault("phone", "")
        booking.setdefault("email", "")
        booking.setdefault("note", "")
        booking.setdefault("status", "Confermata")
        booking.setdefault("amount", 0)
        booking.setdefault("paid", False)
        booking.setdefault("gift", False)
        booking.setdefault("paid_to_gym_at", "")
        booking.setdefault("paid_to_gym_by", "")
        booking.setdefault("settlement_id", "")
        booking.setdefault("instructor", "")
        booking.setdefault("created_by", "")

        if not booking.get("client_id"):
            first, last = split_name(booking.get("name", ""))
            key = client_key(first, last)
            if key.strip("|") and key in existing:
                booking["client_id"] = existing[key]["id"]
            elif key.strip("|"):
                client = {
                    "id": new_id("c_"),
                    "first_name": first,
                    "last_name": last,
                    "phone": booking.get("phone", ""),
                    "email": booking.get("email", ""),
                    "notes": "",
                    "birth_date": "",
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                }
                data["clients"].append(client)
                existing[key] = client
                booking["client_id"] = client["id"]

    return data


def get_client(data: dict, client_id: str):
    return next((c for c in data.get("clients", []) if c.get("id") == client_id), None)


def client_options(data: dict):
    return sorted(
        [f"{full_name(c)} | {c.get('phone', '')} | {c.get('email', '')} | {c.get('id')}" for c in data.get("clients", [])],
        key=str.lower,
    )


def option_to_client_id(option: str) -> str:
    return option.split("|")[-1].strip()


def add_client(data: dict, first: str, last: str, phone: str, email: str = "", notes: str = "", birth: str = ""):
    first, last, phone = first.strip(), last.strip(), phone.strip()
    if not first or not last or not phone:
        return False, "Inserisci nome, cognome e telefono.", None
    key = client_key(first, last)
    for client in data["clients"]:
        if client_key(client.get("first_name", ""), client.get("last_name", "")) == key:
            return False, "Cliente già presente.", client.get("id")
    client_id = new_id("c_")
    data["clients"].append(
        {
            "id": client_id,
            "first_name": first,
            "last_name": last,
            "phone": phone,
            "email": email.strip(),
            "notes": notes.strip(),
            "birth_date": birth.strip(),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    audit_event(data, "add_client", "client", client_id, {"name": f"{last} {first}".strip(), "phone": phone})
    return True, "Cliente salvato.", client_id


def update_client(data: dict, client_id: str, first: str, last: str, phone: str, email: str, birth: str, notes: str):
    client = get_client(data, client_id)
    if not client:
        return False, "Cliente non trovato."
    before = {
        "first_name": client.get("first_name", ""),
        "last_name": client.get("last_name", ""),
        "phone": client.get("phone", ""),
        "email": client.get("email", ""),
        "birth_date": client.get("birth_date", ""),
        "notes": client.get("notes", ""),
    }
    client.update(
        {
            "first_name": first.strip(),
            "last_name": last.strip(),
            "phone": phone.strip(),
            "email": email.strip(),
            "birth_date": birth.strip(),
            "notes": notes.strip(),
        }
    )
    for booking in data["bookings"]:
        if booking.get("client_id") == client_id:
            booking["name"] = full_name(client)
            booking["phone"] = client.get("phone", "")
            booking["email"] = client.get("email", "")
    audit_event(
        data,
        "update_client",
        "client",
        client_id,
        {
            "before": before,
            "after": {
                "first_name": client.get("first_name", ""),
                "last_name": client.get("last_name", ""),
                "phone": client.get("phone", ""),
                "email": client.get("email", ""),
                "birth_date": client.get("birth_date", ""),
                "notes": client.get("notes", ""),
            },
        },
    )
    return True, "Scheda cliente aggiornata."


def count_confirmed(data: dict, day, time: str, instructor: str = "", exclude_id: str = "") -> int:
    target = date_key(day)
    return sum(
        1
        for b in data["bookings"]
        if b.get("date") == target
        and b.get("time") == time
        and b.get("status") == "Confermata"
        and b.get("id") != exclude_id
        and (not instructor or b.get("instructor") == instructor)
    )


def auto_status(data: dict, day, time: str, instructor: str) -> str:
    return "Confermata" if count_confirmed(data, day, time, instructor) < CAPACITY else "Lista attesa"


def create_booking(data: dict, client_id: str, day, time: str, amount: float, paid: bool, instructor: str, note: str, gift_flag: bool):
    client = get_client(data, client_id)
    if not client:
        raise ValueError("Cliente non trovato.")
    amount = 0.0 if gift_flag else money(amount)
    paid = True if gift_flag else bool(paid)
    clean_note = note.strip()
    if gift_flag and "omaggio" not in clean_note.lower():
        clean_note = (clean_note + " | " if clean_note else "") + "Seduta omaggio / prova"

    booking = {
        "id": new_id("b_"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "client_id": client_id,
        "date": date_key(day),
        "day": DAY_FULL[parse_date(day).weekday()],
        "time": time,
        "name": full_name(client),
        "phone": client.get("phone", ""),
        "email": client.get("email", ""),
        "note": clean_note,
        "status": auto_status(data, day, time, instructor),
        "amount": amount,
        "paid": paid,
        "gift": bool(gift_flag),
        "paid_to_gym_at": datetime.now().isoformat(timespec="seconds") if paid and not gift_flag else "",
        "paid_to_gym_by": current_user() if paid and not gift_flag else "",
        "settlement_id": "",
        "instructor": instructor,
        "created_by": current_user(),
    }
    data["bookings"].append(booking)
    audit_event(
        data,
        "create_booking",
        "booking",
        booking["id"],
        {
            "client_id": client_id,
            "date": booking["date"],
            "time": time,
            "instructor": instructor,
            "amount": amount,
            "paid": paid,
            "gift": bool(gift_flag),
            "status": booking["status"],
        },
    )
    return booking


def open_rows(data: dict, instructor: str = ""):
    return [
        b
        for b in data["bookings"]
        if b.get("status") != "Annullata"
        and not b.get("settlement_id")
        and (not instructor or b.get("instructor") == instructor)
    ]


def row_label(booking: dict) -> str:
    suffix = " · OMAGGIO" if is_gift(booking) else f" · € {money(booking.get('amount')):.2f}"
    return f"{date_it(booking.get('date'))} · {booking.get('time', '')} · {booking.get('instructor', '')} · {booking.get('name', '')}{suffix}"


def mark_paid(data: dict, booking_id: str):
    booking = next((b for b in data["bookings"] if b.get("id") == booking_id), None)
    if not booking:
        return False, "Prenotazione non trovata."
    if is_gift(booking):
        return False, "Seduta omaggio: non c'è incasso."
    was_paid = yes(booking.get("paid"))
    booking["paid"] = True
    booking["paid_to_gym_at"] = datetime.now().isoformat(timespec="seconds")
    booking["paid_to_gym_by"] = current_user()
    audit_event(data, "mark_paid", "booking", booking_id, {"was_paid": was_paid, "amount": money(booking.get("amount"))})
    return True, "Incasso registrato."


def mark_gift(data: dict, booking_id: str, note: str = ""):
    booking = next((b for b in data["bookings"] if b.get("id") == booking_id), None)
    if not booking:
        return False, "Prenotazione non trovata."
    if booking.get("settlement_id"):
        return False, "Quota già chiusa: non modificabile."
    old_amount = money(booking.get("amount"))
    old_paid = yes(booking.get("paid"))
    booking.update({"gift": True, "amount": 0.0, "paid": True, "paid_to_gym_at": "", "paid_to_gym_by": current_user()})
    if "omaggio" not in str(booking.get("note", "")).lower():
        log = "Seduta omaggio / prova"
        if note.strip():
            log += f" - {note.strip()}"
        booking["note"] = (booking.get("note", "") + " | " if booking.get("note") else "") + log
    audit_event(data, "mark_gift", "booking", booking_id, {"old_amount": old_amount, "old_paid": old_paid, "note": note.strip()})
    return True, "Segnata come omaggio."


def unmark_gift(data: dict, booking_id: str, amount: float, paid: bool, note: str = ""):
    booking = next((b for b in data["bookings"] if b.get("id") == booking_id), None)
    if not booking:
        return False, "Prenotazione non trovata."
    if booking.get("settlement_id"):
        return False, "Quota già chiusa: non modificabile."
    old_note = booking.get("note", "")
    booking.update(
        {
            "gift": False,
            "amount": money(amount),
            "paid": bool(paid),
            "paid_to_gym_at": datetime.now().isoformat(timespec="seconds") if paid else "",
            "paid_to_gym_by": current_user() if paid else "",
        }
    )
    if note.strip():
        booking["note"] = (booking.get("note", "") + " | " if booking.get("note") else "") + note.strip()
    audit_event(
        data,
        "unmark_gift",
        "booking",
        booking_id,
        {"amount": money(amount), "paid": bool(paid), "old_note": old_note, "note": note.strip()},
    )
    return True, "Omaggio tolto."


def update_amount(data: dict, booking_id: str, amount: float, note: str = ""):
    booking = next((b for b in data["bookings"] if b.get("id") == booking_id), None)
    if not booking:
        return False, "Prenotazione non trovata."
    if booking.get("settlement_id"):
        return False, "Quota già chiusa: non modificabile."
    if is_gift(booking):
        return False, "Togli prima la spunta omaggio."
    old = money(booking.get("amount"))
    new = money(amount)
    booking["amount"] = new
    booking["amount_updated_at"] = datetime.now().isoformat(timespec="seconds")
    booking["amount_updated_by"] = current_user()
    if note.strip() or old != new:
        log = f"Importo modificato da € {old:.2f} a € {new:.2f}"
        if note.strip():
            log += f" - {note.strip()}"
        booking["note"] = (booking.get("note", "") + " | " if booking.get("note") else "") + log
    audit_event(data, "update_amount", "booking", booking_id, {"old_amount": old, "new_amount": new, "note": note.strip()})
    return True, "Importo aggiornato."


def mark_share(data: dict, booking_id: str):
    booking = next((b for b in data["bookings"] if b.get("id") == booking_id), None)
    if not booking:
        return False, "Prenotazione non trovata."
    if is_gift(booking):
        return False, "Omaggio: non genera quota."
    if not yes(booking.get("paid")):
        return False, "Prima registra l'incasso palestra."
    if booking.get("settlement_id"):
        return False, "Quota già chiusa."

    amount = money(booking.get("amount"))
    settlement_id = new_id("sett_")
    booking["settlement_id"] = settlement_id
    booking["share_paid_at"] = datetime.now().isoformat(timespec="seconds")
    booking["share_paid_by"] = current_user()
    data.setdefault("settlements", []).append(
        {
            "id": settlement_id,
            "created_at": booking["share_paid_at"],
            "instructor": booking.get("instructor", ""),
            "gross_amount": amount,
            "instructor_amount": round(amount * instructor_share(), 2),
            "gym_amount": round(amount * gym_share(), 2),
            "lessons": 1,
            "closed_by": current_user(),
            "booking_id": booking_id,
        }
    )
    audit_event(
        data,
        "mark_share",
        "booking",
        booking_id,
        {
            "settlement_id": settlement_id,
            "gross_amount": amount,
            "instructor_amount": round(amount * instructor_share(), 2),
            "gym_amount": round(amount * gym_share(), 2),
        },
    )
    return True, "Quota 40% chiusa."


def cancel_booking(data: dict, booking_id: str, note: str = ""):
    booking = next((b for b in data["bookings"] if b.get("id") == booking_id), None)
    if not booking:
        return False, "Prenotazione non trovata."
    if booking.get("settlement_id"):
        return False, "Quota già chiusa: non annullare da qui."
    booking["status"] = "Annullata"
    booking["cancelled_at"] = datetime.now().isoformat(timespec="seconds")
    booking["cancelled_by"] = current_user()
    if note.strip():
        booking["note"] = (booking.get("note", "") + " | " if booking.get("note") else "") + f"Annullata: {note.strip()}"
    audit_event(data, "cancel_booking", "booking", booking_id, {"note": note.strip()})
    return True, "Prenotazione annullata."


def booking_dataframe(rows: list) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Data": date_it(b.get("date")),
                "Ora": b.get("time", ""),
                "Istruttrice": b.get("instructor", ""),
                "Cliente": b.get("name", ""),
                "Telefono": b.get("phone", ""),
                "Stato": b.get("status", ""),
                "Tipo": "Omaggio" if is_gift(b) else "Pagamento",
                "Importo": money(b.get("amount")),
                "Incassato": "Omaggio" if is_gift(b) else ("Sì" if yes(b.get("paid")) else "No"),
                "Quota 40%": 0.0 if is_gift(b) else round(money(b.get("amount")) * instructor_share(), 2),
                "Quota chiusa": "Sì" if b.get("settlement_id") else "No",
                "Note": b.get("note", ""),
            }
            for b in rows
        ]
    )


def planning_rows(data: dict, days: int = PLANNING_DAYS, instructor: str = ""):
    today = date.today()
    end = today + timedelta(days=days - 1)
    out = []
    for booking in data["bookings"]:
        if booking.get("status") == "Annullata":
            continue
        if instructor and booking.get("instructor") != instructor:
            continue
        try:
            booking_day = parse_date(booking.get("date"))
        except Exception:
            continue
        if today <= booking_day <= end:
            out.append(booking)
    return sorted(out, key=lambda x: (x.get("date", ""), x.get("time", ""), x.get("instructor", ""), x.get("name", "")))


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Dati")
    return output.getvalue()


def pdf_bytes(title: str, df: pd.DataFrame) -> bytes:
    if SimpleDocTemplate is None:
        return simple_pdf_bytes(title, df)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=1 * cm, leftMargin=1 * cm, topMargin=1 * cm, bottomMargin=1 * cm)
    styles = getSampleStyleSheet()
    story = []

    if Path(LOGO_PATH).exists():
        try:
            story.append(Image(LOGO_PATH, width=2.0 * cm, height=2.0 * cm))
        except Exception:
            pass

    story.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
    story.append(Paragraph(f"Generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]))
    story.append(Spacer(1, 0.3 * cm))

    show_df = df.copy()
    for col in show_df.columns:
        show_df[col] = show_df[col].astype(str)
    show_df = show_df.iloc[:120]
    data = [list(show_df.columns)] + show_df.values.tolist()

    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243142")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return buffer.getvalue()


def simple_pdf_bytes(title: str, df: pd.DataFrame) -> bytes:
    def clean(value):
        return str(value or "").replace("\\", "/").replace("(", "[").replace(")", "]")

    lines = [title, " | ".join(map(str, df.columns))]
    for _, row in df.head(70).iterrows():
        lines.append(" | ".join(clean(x) for x in row.tolist())[:130])

    y = 805
    chunks = []
    for i, line in enumerate(lines):
        font_size = 14 if i == 0 else 8
        chunks.append(f"BT /F1 {font_size} Tf 35 {y} Td ({clean(line)[:125]}) Tj ET")
        y -= 18 if i == 0 else 11
        if y < 30:
            break

    stream = "\n".join(chunks)
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
        "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        f"5 0 obj << /Length {len(stream.encode('latin-1', 'replace'))} >> stream\n{stream}\nendstream endobj",
    ]
    pdf = "%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf.encode("latin-1", "replace")))
        pdf += obj + "\n"
    xref = len(pdf.encode("latin-1", "replace"))
    pdf += "xref\n0 6\n0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n"
    pdf += f"trailer << /Root 1 0 R /Size 6 >>\nstartxref\n{xref}\n%%EOF"
    return pdf.encode("latin-1", "replace")


def header():
    st.markdown(
        """
        <style>
        .main .block-container {max-width: 1350px; padding-top: 1rem;}
        .bc-header {display:flex; align-items:center; gap:22px; margin-bottom:18px;}
        .bc-title {font-size:40px; font-weight:800; color:#243142; line-height:1.05;}
        .bc-logo {width:92px; max-height:92px; object-fit:contain;}
        .day-card {border:1px solid #D8DEE8; border-radius:12px; padding:10px 12px; background:#fff; min-height:86px;}
        .day-empty {background:#FAFAFA; color:#9AA0A6;}
        .day-title {font-weight:800; margin-bottom:6px;}
        .slot {font-size:0.86rem; line-height:1.22; padding:4px 0; border-bottom:1px solid #EEF0F2;}
        .slot:last-child {border-bottom:0;}
        .muted {color:#6F7782;}
        @media(max-width: 700px) {.bc-title{font-size:27px}.bc-logo{width:64px}.day-card{min-height:70px}}
        </style>
        """,
        unsafe_allow_html=True,
    )
    logo = ""
    if Path(LOGO_PATH).exists():
        encoded = base64.b64encode(Path(LOGO_PATH).read_bytes()).decode("ascii")
        logo = f"<img class='bc-logo' src='data:image/png;base64,{encoded}'>"
    st.markdown(f"<div class='bc-header'>{logo}<div class='bc-title'>{APP_TITLE}</div></div>", unsafe_allow_html=True)


def login() -> bool:
    if st.session_state.get("authenticated"):
        return True

    users = users_config()
    _, col, _ = st.columns([1.3, 1.1, 1.3])
    with col:
        st.markdown("### Accesso staff")
        username = st.selectbox("Utente", list(users.keys()), key="login_user")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Accedi", type="primary", use_container_width=True):
            cfg = users.get(str(username).lower().strip(), {})
            if password and password == str(cfg.get("password", "")):
                st.session_state["authenticated"] = True
                st.session_state["current_user"] = str(username).lower().strip()
                st.session_state["current_role"] = str(cfg.get("role", "instructor")).lower().strip()
                navigate("Planning")
            else:
                st.error("Utente o password non corretti.")
    return False


def render_downloads(label: str, df: pd.DataFrame, base_name: str):
    if df.empty:
        return
    col1, col2 = st.columns(2)
    col1.download_button(f"Scarica PDF {label}", data=pdf_bytes(label, df), file_name=f"{base_name}.pdf", mime="application/pdf", use_container_width=True)
    col2.download_button(f"Scarica Excel {label}", data=to_excel_bytes(df), file_name=f"{base_name}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)


def render_booking(data, sha):
    st.subheader("Prenota")
    mode = st.radio("Cliente", ["Seleziona da archivio", "Nuovo cliente"], horizontal=True)
    client_id = None

    if mode == "Seleziona da archivio":
        options = client_options(data)
        if not options:
            st.warning("Nessun cliente in archivio.")
        else:
            client_id = option_to_client_id(st.selectbox("Cliente", options))
            client = get_client(data, client_id)
            st.caption(f"Telefono: {client.get('phone', '')} · Email: {client.get('email', '')}")
    else:
        with st.container(border=True):
            c1, c2 = st.columns(2)
            last = c1.text_input("Cognome", key="new_last")
            first = c2.text_input("Nome", key="new_first")
            c3, c4 = st.columns(2)
            phone = c3.text_input("Telefono", key="new_phone")
            email = c4.text_input("Email", key="new_email")
            birth = st.text_input("Data di nascita", key="new_birth")
            notes = st.text_area("Note cliente", key="new_notes")
            if st.button("Salva nuovo cliente", type="primary"):
                ok, msg, client_id = add_client(data, first, last, phone, email, notes, birth)
                if ok:
                    save_data(data, sha, "Add client")
                    st.session_state["booking_client_id"] = client_id
                    navigate("Prenota")
                else:
                    st.error(msg)
        client_id = st.session_state.get("booking_client_id")

    if client_id:
        st.markdown("### Dati prenotazione")
        c1, c2 = st.columns(2)
        selected_date = parse_date(c1.date_input("Data", value=date.today(), min_value=date.today(), format="DD/MM/YYYY"))
        times = SCHEDULE.get(selected_date.weekday(), [])
        if not times:
            st.warning("Nessun orario previsto per questa data.")
            return
        selected_time = c2.selectbox("Orario", times)
        default_instructor = current_instructor()
        default_index = INSTRUCTORS.index(default_instructor) if default_instructor in INSTRUCTORS else 0
        c3, c4, c5 = st.columns(3)
        gift_flag = c3.checkbox("Seduta omaggio / prova gratuita")
        amount = c4.number_input("Importo (€)", min_value=0.0, value=0.0, step=1.0, format="%.2f", disabled=gift_flag)
        paid = c5.checkbox("Già incassato dalla palestra", disabled=gift_flag)
        instructor = st.selectbox("Istruttrice", INSTRUCTORS, index=default_index)
        note = st.text_area("Note prenotazione")
        st.info(f"{instructor} · {selected_time}: {count_confirmed(data, selected_date, selected_time, instructor)}/{CAPACITY} confermate · stato: {'Seduta omaggio' if gift_flag else auto_status(data, selected_date, selected_time, instructor)}")
        if st.button("Salva prenotazione", type="primary"):
            create_booking(data, client_id, selected_date, selected_time, amount, paid, instructor, note, gift_flag)
            save_data(data, sha, "Add booking")
            st.success("Prenotazione salvata.")
            navigate("Planning")


def render_cash(data, sha):
    instructor = "" if is_admin() else current_instructor()
    rows = open_rows(data, instructor)
    pay_rows = [b for b in rows if not is_gift(b)]
    gift_rows = [b for b in rows if is_gift(b)]
    unpaid = [b for b in pay_rows if not yes(b.get("paid"))]
    paid = [b for b in pay_rows if yes(b.get("paid"))]

    collected = sum(money(b.get("amount")) for b in paid)
    total_open = sum(money(b.get("amount")) for b in pay_rows)
    to_collect = sum(money(b.get("amount")) for b in unpaid)
    quota_open = collected * instructor_share()
    quota_closed = sum(money(s.get("instructor_amount")) for s in data.get("settlements", []) if not instructor or s.get("instructor") == instructor)

    st.subheader("Incassi")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Totale aperto", f"€ {total_open:.2f}")
    m2.metric("Da incassare", f"€ {to_collect:.2f}")
    m3.metric("Incassato palestra", f"€ {collected:.2f}")
    m4.metric("40% da dare" if is_admin() else "Tuo 40% da ricevere", f"€ {quota_open:.2f}")
    m5.metric("Omaggio", len(gift_rows))
    if is_admin():
        st.info(f"Quote istruttrici: da dare € {quota_open:.2f} · già pagate € {quota_closed:.2f}")
    else:
        st.info(f"Quota {current_instructor()}: da ricevere € {quota_open:.2f} · già ricevuto € {quota_closed:.2f}")

    st.markdown("### Azione unica")
    all_rows = sorted(rows, key=lambda b: (b.get("date", ""), b.get("time", ""), b.get("name", "")))
    with st.container(border=True):
        if not all_rows:
            st.info("Nessuna prenotazione modificabile.")
        else:
            idx = st.selectbox("Prenotazione", range(len(all_rows)), format_func=lambda i: row_label(all_rows[i]))
            selected = all_rows[idx]
            booking_id = selected.get("id")
            was_gift = is_gift(selected)
            c1, c2, c3 = st.columns(3)
            gift_now = c1.checkbox("Seduta omaggio / prova", value=was_gift, key=f"gift_{booking_id}")
            new_amount = c2.number_input("Importo totale (€)", min_value=0.0, value=0.0 if gift_now else float(money(selected.get("amount"))), step=1.0, format="%.2f", disabled=gift_now, key=f"amount_{booking_id}")
            paid_now = c3.checkbox("Incassato palestra", value=True if gift_now else yes(selected.get("paid")), disabled=gift_now, key=f"paid_{booking_id}")
            note = st.text_input("Nota opzionale", key=f"note_{booking_id}")
            if st.button("Salva", type="primary", key=f"save_cash_{booking_id}"):
                if gift_now:
                    ok, msg = mark_gift(data, booking_id, note)
                elif was_gift and not gift_now:
                    ok, msg = unmark_gift(data, booking_id, new_amount, paid_now, note)
                else:
                    ok, msg = update_amount(data, booking_id, new_amount, note)
                    if ok and paid_now and not yes(selected.get("paid")):
                        ok, msg = mark_paid(data, booking_id)
                if ok:
                    save_data(data, sha, "Save payment")
                    navigate("Incassi")
                else:
                    st.error(msg)

    st.markdown("### Quota 40%")
    payable = [b for b in paid if not b.get("settlement_id") and not is_gift(b)]
    with st.container(border=True):
        if not payable:
            st.info("Nessuna quota da chiudere.")
        else:
            q_idx = st.selectbox("Prenotazione quota", range(len(payable)), format_func=lambda i: row_label(payable[i]) + f" · quota € {money(payable[i].get('amount')) * instructor_share():.2f}")
            label = "Segna quota 40% pagata ad Alice/Grazia" if is_admin() else "Segna quota 40% ricevuta"
            if st.button(label, type="primary"):
                ok, msg = mark_share(data, payable[q_idx].get("id"))
                if ok:
                    save_data(data, sha, "Close instructor share")
                    navigate("Incassi")
                else:
                    st.error(msg)

    st.markdown("### Elenchi")
    with st.expander("Da incassare", expanded=True):
        st.dataframe(booking_dataframe(unpaid), use_container_width=True, hide_index=True) if unpaid else st.success("Nessun importo da incassare.")
    with st.expander("Incassati dalla palestra", expanded=True):
        st.dataframe(booking_dataframe(paid), use_container_width=True, hide_index=True) if paid else st.info("Nessun incasso registrato.")
    with st.expander("Sedute omaggio", expanded=True):
        st.dataframe(booking_dataframe(gift_rows), use_container_width=True, hide_index=True) if gift_rows else st.info("Nessuna seduta omaggio.")
    history = []
    for s in data.get("settlements", []):
        if instructor and s.get("instructor") != instructor:
            continue
        history.append(
            {
                "Data": s.get("created_at", ""),
                "Istruttrice": s.get("instructor", ""),
                "Lordo": money(s.get("gross_amount")),
                "Quota 40%": money(s.get("instructor_amount")),
                "Body Center 60%": money(s.get("gym_amount")),
                "Chiusa da": s.get("closed_by", ""),
            }
        )
    with st.expander("Storico quote già chiuse", expanded=True):
        st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True) if history else st.info("Nessuna quota chiusa.")


def cancel_box(data, sha):
    future = []
    for b in data["bookings"]:
        try:
            if b.get("status") != "Annullata" and not b.get("settlement_id") and parse_date(b.get("date")) >= date.today():
                future.append(b)
        except Exception:
            pass
    future = sorted(future, key=lambda b: (b.get("date", ""), b.get("time", ""), b.get("instructor", ""), b.get("name", "")))

    with st.expander("Annulla prenotazione", expanded=False):
        if not future:
            st.info("Nessuna prenotazione futura annullabile.")
            return
        idx = st.selectbox("Prenotazione", range(len(future)), format_func=lambda i: row_label(future[i]))
        note = st.text_input("Motivo / nota opzionale")
        confirm = st.checkbox("Confermo l'annullamento")
        if st.button("Annulla prenotazione selezionata"):
            if not confirm:
                st.warning("Spunta la conferma prima di annullare.")
                return
            ok, msg = cancel_booking(data, future[idx].get("id"), note)
            if ok:
                save_data(data, sha, "Cancel booking")
                navigate("Planning")
            else:
                st.error(msg)


def render_planning_grid(rows: list, title: str, days: int = PLANNING_DAYS, show_instructor: bool = True):
    st.markdown(f"### {title}")
    today = date.today()
    all_days = [(today + timedelta(days=i)).isoformat() for i in range(days)]
    by_day = {d: [] for d in all_days}
    for row in rows:
        by_day.setdefault(row.get("date", ""), []).append(row)

    c1, c2, c3 = st.columns(3)
    c1.metric("Oggi", len([r for r in rows if r.get("date") == today.isoformat()]))
    c2.metric(f"Prossimi {days} giorni", len(rows))
    c3.metric("Omaggio", len([r for r in rows if is_gift(r)]))

    cards = []
    for day_key in all_days:
        grouped = {}
        for row in by_day.get(day_key, []):
            grouped.setdefault((row.get("time", ""), row.get("instructor", "")), []).append(row)

        lines = []
        for (time, instructor), group in sorted(grouped.items(), key=lambda item: item[0]):
            confirmed_rows = [r for r in group if r.get("status") == "Confermata"]
            waiting_rows = [r for r in group if r.get("status") == "Lista attesa"]
            names = ", ".join([r.get("name", "") + (" (omaggio)" if is_gift(r) else "") for r in confirmed_rows]) or "—"
            instructor_html = f" <span class='muted'>{instructor}</span>" if show_instructor and instructor else ""
            waiting = f" · att {len(waiting_rows)}" if waiting_rows else ""
            lines.append(
                f"<div class='slot'><b>{time}</b>{instructor_html} "
                f"<span class='muted'>{len(confirmed_rows)}/{CAPACITY} · lib {max(CAPACITY - len(confirmed_rows), 0)}{waiting}</span><br>"
                f"<small>{names}</small></div>"
            )
        body = "".join(lines) if lines else "<div class='muted'>—</div>"
        cls = "day-card day-empty" if not lines else "day-card"
        cards.append(f"<div class='{cls}'><div class='day-title'>{date_label(day_key)}</div>{body}</div>")

    st.markdown("<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px'>" + "".join(cards) + "</div>", unsafe_allow_html=True)

    df = booking_dataframe(rows)
    with st.expander("Elenco rapido", expanded=False):
        if df.empty:
            st.info("Nessuna prenotazione nel periodo.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)


def render_planning(data, sha):
    st.subheader("Planning 3 mesi")
    pdf_scope = "" if is_admin() else current_instructor()
    pdf_rows = planning_rows(data, PLANNING_DAYS, pdf_scope)
    df = booking_dataframe(pdf_rows)
    render_downloads("planning", df, "planning_3_mesi")

    if st.button("Apri Incassi", type="primary"):
        navigate("Incassi")
    cancel_box(data, sha)

    if is_admin():
        view = st.selectbox("Vista", ["Tutte", *INSTRUCTORS])
        instructor = "" if view == "Tutte" else view
        render_planning_grid(planning_rows(data, PLANNING_DAYS, instructor), f"Planning {view}", PLANNING_DAYS, True)
    else:
        instructor = current_instructor()
        tab_all, tab_mine = st.tabs(["Planning completo", "I miei impegni"])
        with tab_all:
            render_planning_grid(planning_rows(data, PLANNING_DAYS, ""), "Planning completo", PLANNING_DAYS, True)
        with tab_mine:
            render_planning_grid(planning_rows(data, PLANNING_DAYS, instructor), f"Prossimi impegni {instructor}", PLANNING_DAYS, False)


def render_clients(data, sha):
    st.subheader("Clienti")

    with st.expander("Aggiungi cliente", expanded=False):
        c1, c2 = st.columns(2)
        last = c1.text_input("Cognome", key="add_last")
        first = c2.text_input("Nome", key="add_first")
        c3, c4 = st.columns(2)
        phone = c3.text_input("Telefono", key="add_phone")
        email = c4.text_input("Email", key="add_email")
        birth = st.text_input("Data di nascita", key="add_birth")
        notes = st.text_area("Note", key="add_notes")
        if st.button("Salva nuovo cliente", type="primary"):
            ok, msg, client_id = add_client(data, first, last, phone, email, notes, birth)
            if ok:
                st.session_state["edit_client_id"] = client_id
                save_data(data, sha, "Add client")
                navigate("Clienti")
            else:
                st.error(msg)

    clients = sorted(data["clients"], key=lambda c: (str(c.get("last_name", "")).lower(), str(c.get("first_name", "")).lower()))
    clients_df = pd.DataFrame(
        [
            {
                "Cognome": c.get("last_name", ""),
                "Nome": c.get("first_name", ""),
                "Telefono": c.get("phone", ""),
                "Email": c.get("email", ""),
                "Note": c.get("notes", ""),
            }
            for c in clients
        ]
    )
    st.dataframe(clients_df, use_container_width=True, hide_index=True) if not clients_df.empty else st.info("Nessun cliente.")

    st.markdown("### Modifica scheda cliente")
    options = client_options(data)
    if not options:
        return
    selected = st.selectbox("Scegli cliente", options, key="client_pick_to_open")
    selected_id = option_to_client_id(selected)
    if st.button("Apri scheda selezionata", type="primary"):
        st.session_state["edit_client_id"] = selected_id
        st.rerun()

    client_id = st.session_state.get("edit_client_id", "")
    client = get_client(data, client_id)
    if not client:
        st.info("Scegli un cliente e clicca 'Apri scheda selezionata'.")
        return

    st.success(f"Scheda aperta: {full_name(client)}")
    with st.form(f"edit_client_{client_id}", clear_on_submit=False):
        c1, c2 = st.columns(2)
        last = c1.text_input("Cognome", value=client.get("last_name", ""), key=f"last_{client_id}")
        first = c2.text_input("Nome", value=client.get("first_name", ""), key=f"first_{client_id}")
        c3, c4 = st.columns(2)
        phone = c3.text_input("Telefono", value=client.get("phone", ""), key=f"phone_{client_id}")
        email = c4.text_input("Email", value=client.get("email", ""), key=f"email_{client_id}")
        birth = st.text_input("Data nascita", value=client.get("birth_date", ""), key=f"birth_{client_id}")
        notes = st.text_area("Note", value=client.get("notes", ""), key=f"notes_{client_id}")
        submitted = st.form_submit_button("Salva questa scheda cliente", type="primary")

    if submitted:
        ok, msg = update_client(data, client_id, first, last, phone, email, birth, notes)
        if ok:
            st.session_state["edit_client_id"] = client_id
            save_data(data, sha, "Update client")
            navigate("Clienti")
        else:
            st.error(msg)


def render_search(data):
    st.subheader("Cerca")
    query = st.text_input("Cerca cliente, telefono, email, istruttrice, nota, data, ora").strip().lower()
    rows = []
    for b in data["bookings"]:
        haystack = " ".join(str(b.get(k, "")) for k in ["name", "phone", "email", "instructor", "note", "date", "time", "status"]).lower()
        if not query or query in haystack:
            rows.append(b)
    df = booking_dataframe(rows)
    render_downloads("ricerca", df, "ricerca_prenotazioni")
    st.dataframe(df, use_container_width=True, hide_index=True) if not df.empty else st.info("Nessun risultato.")


def render_archive(data, sha):
    st.subheader("Archivio prenotazioni")
    rows = sorted(data["bookings"], key=lambda b: (b.get("date", ""), b.get("time", ""), b.get("instructor", ""), b.get("name", "")), reverse=True)
    df = booking_dataframe(rows)
    render_downloads("archivio", df, "archivio_prenotazioni")
    st.dataframe(df, use_container_width=True, hide_index=True) if not df.empty else st.info("Archivio vuoto.")


def run():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    header()
    if not login():
        return

    data, sha = load_data()
    data = ensure_data(data)

    allowed = allowed_sections()
    next_section = st.session_state.pop("_next_section", None)
    if next_section in allowed:
        st.session_state["section"] = next_section
    if st.session_state.get("section") not in allowed:
        st.session_state["section"] = "Planning"

    section = st.radio("Sezione", allowed, horizontal=True, key="section", label_visibility="collapsed")
    c1, c2 = st.columns([4, 1])
    c1.caption(f"Accesso: {current_user().capitalize()} · {'Admin' if is_admin() else 'Istruttrice'}")
    if c2.button("Logout", use_container_width=True):
        for key in ["authenticated", "current_user", "current_role", "section", "_next_section", "edit_client_id", "booking_client_id"]:
            st.session_state.pop(key, None)
        st.rerun()

    st.divider()
    dispatch = {
        "Planning": render_planning,
        "Prenota": render_booking,
        "Incassi": render_cash,
        "Clienti": render_clients,
        "Cerca": lambda d, s: render_search(d),
        "Archivio": render_archive,
    }
    dispatch[section](data, sha)


if __name__ == "__main__":
    run()
