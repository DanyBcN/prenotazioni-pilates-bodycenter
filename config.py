import os
import re
from datetime import date, datetime

import pandas as pd
import streamlit as st


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
