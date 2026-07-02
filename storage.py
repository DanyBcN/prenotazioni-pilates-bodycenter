import base64
import json
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from auth import current_user
from config import (
    AUDIT_LOG_LIMIT, BACKUP_DIR, CAPACITY, DATA_PATH, DAY_FULL, PLANNING_DAYS,
    client_key, date_it, date_key, full_name, github_enabled, github_headers, github_url,
    gym_share, instructor_share, is_gift, money, new_id, parse_date, secret, split_name, yes,
)

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
