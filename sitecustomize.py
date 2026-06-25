import builtins
import html
from types import SimpleNamespace

builtins.APP_TITLE = "Prenotazioni Pilates Reformer"


def status_icon(status):
    return {"Confermata": "✅", "Lista attesa": "⏳", "Annullata": "❌"}.get(status, "")


builtins.status_icon = status_icon


# --- PDF: force long text/note cells to wrap inside table cells ---
try:
    import reportlab.platypus as _platypus
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph

    _OriginalTable = _platypus.Table
    _pdf_body_style = ParagraphStyle(
        "BodyCenterWrapped",
        fontName="Helvetica",
        fontSize=6,
        leading=7.5,
        alignment=TA_CENTER,
        textColor=colors.black,
        wordWrap="CJK",
    )
    _pdf_header_style = ParagraphStyle(
        "HeaderCenterWrapped",
        fontName="Helvetica-Bold",
        fontSize=6,
        leading=7.5,
        alignment=TA_CENTER,
        textColor=colors.white,
        wordWrap="CJK",
    )

    def _wrap_pdf_cell(value, is_header=False):
        if value is None:
            value = ""
        if isinstance(value, str):
            text = html.escape(value).replace("\n", "<br/>")
            return Paragraph(text, _pdf_header_style if is_header else _pdf_body_style)
        return value

    def WrappingTable(data, *args, **kwargs):
        if isinstance(data, (list, tuple)):
            wrapped = []
            for row_idx, row in enumerate(data):
                if isinstance(row, (list, tuple)):
                    wrapped.append([_wrap_pdf_cell(cell, row_idx == 0) for cell in row])
                else:
                    wrapped.append(row)
            data = wrapped
        return _OriginalTable(data, *args, **kwargs)

    _platypus.Table = WrappingTable
except Exception:
    pass


# --- Streamlit: move password/login controls from sidebar to main page ---
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
.login-card {
    max-width: 460px;
    padding: 22px 24px;
    border: 1px solid #e2e8e0;
    border-radius: 16px;
    background: #ffffff;
    box-shadow: 0 8px 24px rgba(36, 49, 66, 0.06);
    margin-top: 20px;
}
</style>
"""

AGGRID_CSS = {
    ".ag-row": {"cursor": "pointer !important"},
    ".ag-row-hover": {"background-color": "#eef6f2 !important", "cursor": "pointer !important"},
    ".ag-cell": {"cursor": "pointer !important"},
    ".ag-header-cell-label": {"font-weight": "700"},
}

try:
    import pandas as pd
    import streamlit as st

    _original_dataframe = st.dataframe

    class _MainLoginProxy:
        def header(self, *args, **kwargs):
            st.markdown("<div class='login-card'>", unsafe_allow_html=True)
            return st.markdown("### Accesso staff")

        def text_input(self, *args, **kwargs):
            return st.text_input(*args, **kwargs)

        def success(self, *args, **kwargs):
            # Do not show a persistent login message that occupies layout space.
            return None

        def error(self, *args, **kwargs):
            return st.error(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(st, name)

    st.sidebar = _MainLoginProxy()

    def _empty_selection_event():
        return SimpleNamespace(selection=SimpleNamespace(rows=[]))

    def _aggrid_client_table(data, kwargs):
        try:
            from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
        except Exception:
            st.markdown(POINTER_TABLE_CSS, unsafe_allow_html=True)
            return _original_dataframe(data, **kwargs)

        df = data.copy() if hasattr(data, "copy") else pd.DataFrame(data)
        if df.empty:
            return _empty_selection_event()

        df = df.reset_index(drop=True)
        df["__row_index"] = df.index

        gb = GridOptionsBuilder.from_dataframe(df)
        gb.configure_selection(selection_mode="single", use_checkbox=False)
        gb.configure_grid_options(
            domLayout="normal",
            rowHeight=42,
            suppressCellFocus=False,
            rowSelection="single",
            enableCellTextSelection=False,
        )
        gb.configure_column("__row_index", hide=True)
        for col in df.columns:
            if col != "__row_index":
                gb.configure_column(col, sortable=True, filter=True, resizable=True)

        response = AgGrid(
            df,
            gridOptions=gb.build(),
            height=min(420, 70 + 43 * max(len(df), 3)),
            fit_columns_on_grid_load=True,
            allow_unsafe_jscode=True,
            custom_css=AGGRID_CSS,
            update_mode=GridUpdateMode.SELECTION_CHANGED,
            key=kwargs.get("key", "client_aggrid"),
        )
        selected = response.get("selected_rows", []) or []
        if selected:
            try:
                idx = int(selected[0].get("__row_index", 0))
                return SimpleNamespace(selection=SimpleNamespace(rows=[idx]))
            except Exception:
                return _empty_selection_event()
        return _empty_selection_event()

    def dataframe_with_clickable_rows(*args, **kwargs):
        key = kwargs.get("key", "")
        clickable_keys = {"client_table_in_main", "client_row_selection", "client_click_table_page"}
        if key in clickable_keys and args:
            clean_kwargs = dict(kwargs)
            clean_kwargs.pop("on_select", None)
            clean_kwargs.pop("selection_mode", None)
            clean_kwargs.pop("hide_index", None)
            clean_kwargs.pop("use_container_width", None)
            return _aggrid_client_table(args[0], clean_kwargs)
        st.markdown(POINTER_TABLE_CSS, unsafe_allow_html=True)
        return _original_dataframe(*args, **kwargs)

    st.dataframe = dataframe_with_clickable_rows
except Exception:
    pass
