import builtins

builtins.APP_TITLE = "Prenotazioni Pilates Reformer"


def status_icon(status):
    return {"Confermata": "✅", "Lista attesa": "⏳", "Annullata": "❌"}.get(status, "")


builtins.status_icon = status_icon


POINTER_TABLE_CSS = """
<style>
div[data-testid="stDataFrame"] canvas,
div[data-testid="stDataFrame"] [role="grid"],
div[data-testid="stDataFrame"] [role="row"],
div[data-testid="stDataFrame"] [role="gridcell"] {
    cursor: pointer !important;
}
div[data-testid="stDataFrame"]:hover {
    cursor: pointer !important;
}
</style>
"""

try:
    import streamlit as st

    _original_dataframe = st.dataframe

    def dataframe_with_pointer_cursor(*args, **kwargs):
        st.markdown(POINTER_TABLE_CSS, unsafe_allow_html=True)
        return _original_dataframe(*args, **kwargs)

    st.dataframe = dataframe_with_pointer_cursor
except Exception:
    pass
