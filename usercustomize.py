import base64 as _base64
import json as _json
import datetime as _datetime
import requests as _requests
import streamlit as _st

_original_timedelta = _datetime.timedelta

def _bodycenter_timedelta(*args, **kwargs):
    if kwargs.get("days") == 13:
        kwargs = dict(kwargs)
        kwargs["days"] = 91
    return _original_timedelta(*args, **kwargs)

_datetime.timedelta = _bodycenter_timedelta

_original_subheader = _st.subheader

def _bodycenter_subheader(text, *args, **kwargs):
    if text == "Planning 14 giorni":
        text = "Planning 3 mesi"
    return _original_subheader(text, *args, **kwargs)

_st.subheader = _bodycenter_subheader

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
