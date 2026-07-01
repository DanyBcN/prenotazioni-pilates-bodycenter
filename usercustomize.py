import datetime as _datetime
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
