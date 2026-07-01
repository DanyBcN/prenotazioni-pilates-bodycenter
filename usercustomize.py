from pathlib import Path
import requests as _requests
import streamlit as _st

# Applica modifiche runtime prima che Streamlit esegua app.py.
# Serve perché Streamlit Cloud può continuare a usare cache/runtime vecchi se la logica non è forzata qui.
_app_path = Path(__file__).resolve().with_name("app.py")
if _app_path.exists():
    _text = _app_path.read_text(encoding="utf-8")
    _new = _text
    _new = _new.replace('st.subheader("Planning 14 giorni")', 'st.subheader("Planning 3 mesi")')
    _new = _new.replace('st.subheader("Planning 15 giorni")', 'st.subheader("Planning 3 mesi")')
    _new = _new.replace('days = 14\n    if bc_is_admin():', 'days = 92\n    if bc_is_admin():')
    _new = _new.replace('days = 15\n    if bc_is_admin():', 'days = 92\n    if bc_is_admin():')
    _new = _new.replace('giorni = 14\n    if is_admin():', 'giorni = 92\n    if is_admin():')
    _new = _new.replace('giorni=14\n    if is_admin():', 'giorni=92\n    if is_admin():')
    _new = _new.replace('days = 14\n    view =', 'days = 92\n    view =')
    _new = _new.replace('days = 15\n    view =', 'days = 92\n    view =')
    if _new != _text:
        _app_path.write_text(_new, encoding="utf-8")

# Dopo un salvataggio su GitHub, rilegge subito i dati appena salvati senza aspettare refresh/cache.
_original_get = _requests.get
_original_put = _requests.put

class _BodyCenterCachedResponse:
    status_code = 200
    text = ""
    headers = {}

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


def _is_bookings_url(url):
    return isinstance(url, str) and "/contents/data/bookings.json" in url


def _bodycenter_put(url, *args, **kwargs):
    response = _original_put(url, *args, **kwargs)
    if _is_bookings_url(url) and getattr(response, "status_code", None) in (200, 201):
        try:
            payload = kwargs.get("json") or {}
            content = payload.get("content", "")
            if content:
                _st.session_state["_last_saved_bookings_content"] = content
                _st.session_state["_last_saved_bookings_sha"] = response.json().get("content", {}).get("sha", "")
        except Exception:
            pass
    return response


def _bodycenter_get(url, *args, **kwargs):
    if _is_bookings_url(url) and _st.session_state.get("_last_saved_bookings_content"):
        return _BodyCenterCachedResponse({
            "content": _st.session_state.get("_last_saved_bookings_content", ""),
            "sha": _st.session_state.get("_last_saved_bookings_sha", ""),
        })
    return _original_get(url, *args, **kwargs)

_requests.put = _bodycenter_put
_requests.get = _bodycenter_get
