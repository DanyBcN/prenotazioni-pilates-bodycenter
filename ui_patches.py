import base64
from pathlib import Path

import streamlit as st

_PATCHED = False


def _logo_data_uri():
    path = Path("assets/logo.png")
    if not path.exists():
        return ""
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


def _merge_css(existing=None):
    css = dict(existing or {})
    css.update({
        ".ag-root-wrapper": {"border": "1px solid #d8e2d7", "border-radius": "14px", "overflow": "hidden"},
        ".ag-header": {"background-color": "#edf5ef"},
        ".ag-header-cell-label": {"justify-content": "center", "text-align": "center"},
        ".ag-header-cell-text": {"font-weight": "700", "font-size": "13px", "white-space": "normal", "line-height": "1.15"},
        ".ag-cell": {"padding-left": "12px", "padding-right": "12px", "font-size": "13px", "line-height": "1.25"},
        ".ag-row-hover": {"background-color": "#f3f8f3"},
    })
    return css


def _set_col(grid_options, field, **settings):
    for col in grid_options.get("columnDefs", []):
        if col.get("field") == field:
            col.update(settings)
            col["suppressSizeToFit"] = True
            return


def _apply_archive_widths(grid_options):
    if not isinstance(grid_options, dict):
        return grid_options
    grid_options.setdefault("defaultColDef", {})
    grid_options["defaultColDef"].update({
        "resizable": True,
        "sortable": True,
        "filter": True,
        "wrapHeaderText": False,
        "autoHeaderHeight": False,
    })
    grid_options["rowHeight"] = 46
    grid_options["headerHeight"] = 56
    grid_options["suppressHorizontalScroll"] = False

    _set_col(grid_options, "Elimina", width=90, minWidth=85, maxWidth=100, pinned="left")
    _set_col(grid_options, "Cliente", width=260, minWidth=230, pinned="left")
    _set_col(grid_options, "Data", width=120, minWidth=110)
    _set_col(grid_options, "Giorno", width=120, minWidth=110)
    _set_col(grid_options, "Ora", width=85, minWidth=80)
    _set_col(grid_options, "Telefono", width=150, minWidth=135)
    _set_col(grid_options, "Email", width=320, minWidth=280)
    _set_col(grid_options, "Istruttrice", width=125, minWidth=115)
    _set_col(grid_options, "Stato", width=140, minWidth=130)
    _set_col(grid_options, "Importo", width=110, minWidth=100)
    _set_col(grid_options, "Pagato", width=105, minWidth=95)
    _set_col(grid_options, "Note cliente", width=340, minWidth=300, wrapText=True, autoHeight=True)
    _set_col(grid_options, "Note prenotazione", width=340, minWidth=300, wrapText=True, autoHeight=True)
    _set_col(grid_options, "Inserita il", width=190, minWidth=170)
    return grid_options


def _apply_client_widths(grid_options):
    if not isinstance(grid_options, dict):
        return grid_options
    grid_options.setdefault("defaultColDef", {})
    grid_options["defaultColDef"].update({"resizable": True, "sortable": True, "filter": True, "wrapHeaderText": False, "autoHeaderHeight": False})
    grid_options["rowHeight"] = 44
    grid_options["headerHeight"] = 52
    _set_col(grid_options, "Cognome", width=280, minWidth=240)
    _set_col(grid_options, "Nome", width=280, minWidth=240)
    _set_col(grid_options, "Ultima lezione", width=170, minWidth=155)
    return grid_options


def apply_ui_patches():
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True

    original_columns = st.columns
    original_image = st.image
    original_markdown = st.markdown
    original_caption = st.caption
    original_radio = st.radio

    state = {"skip_logo": False, "skip_caption": False}

    class NoopColumn:
        def __enter__(self):
            return st
        def __exit__(self, exc_type, exc, tb):
            return False

    def inject_css():
        original_markdown(
            """
            <style>
            .block-container { padding-top: 1rem !important; max-width: 1240px !important; }
            .bodycenter-hero {
                display:flex; align-items:center; gap:28px; width:100%; box-sizing:border-box;
                background:linear-gradient(135deg,#f8fbf8 0%,#eef6f1 100%);
                border:1px solid #dfe8df; border-radius:26px; padding:22px 28px; margin:4px 0 18px 0;
                box-shadow:0 10px 30px rgba(36,49,66,.07);
            }
            .bodycenter-hero-logo { width:128px; height:128px; object-fit:contain; }
            .bodycenter-hero-title { margin:0; color:#243142; font-size:clamp(2.25rem,4vw,3.15rem); font-weight:850; line-height:1.02; letter-spacing:-.035em; }
            .bodycenter-hero-subtitle { margin:8px 0 0 0; color:#6f7780; font-size:1.06rem; }
            div[data-testid="stRadio"] > div { gap:.65rem !important; flex-wrap:wrap !important; }
            div[data-testid="stRadio"] label { min-height:42px !important; padding:.55rem 1rem !important; border-radius:999px !important; border:1px solid #dce6dc !important; background:#fff !important; }
            div[data-testid="stRadio"] input[type="radio"] { display:none !important; }
            div[data-testid="stRadio"] label:has(input:checked) { background:#496744 !important; border-color:#496744 !important; }
            div[data-testid="stRadio"] label:has(input:checked) p { color:white !important; }
            </style>
            """,
            unsafe_allow_html=True,
        )

    def columns_patched(spec, *args, **kwargs):
        if spec == [1, 6] or spec == (1, 6):
            state["skip_logo"] = True
            return [NoopColumn(), NoopColumn()]
        return original_columns(spec, *args, **kwargs)

    def image_patched(*args, **kwargs):
        if state["skip_logo"] and kwargs.get("width") == 130:
            return None
        return original_image(*args, **kwargs)

    def markdown_patched(body, *args, **kwargs):
        if isinstance(body, str) and "Prenotazioni Pilates Reformer" in body and "<h1" in body:
            inject_css()
            logo = _logo_data_uri()
            logo_html = f'<img class="bodycenter-hero-logo" src="{logo}" alt="Body Center logo" />' if logo else ""
            state["skip_logo"] = False
            state["skip_caption"] = True
            return original_markdown(
                f"""
                <div class="bodycenter-hero">
                    {logo_html}
                    <div>
                        <h1 class="bodycenter-hero-title">Prenotazioni Pilates Reformer</h1>
                        <p class="bodycenter-hero-subtitle">Gestionale interno Body Center · clienti, prenotazioni, pagamenti</p>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        return original_markdown(body, *args, **kwargs)

    def caption_patched(body, *args, **kwargs):
        if state["skip_caption"] and isinstance(body, str) and "Gestionale interno Body Center" in body:
            state["skip_caption"] = False
            return None
        return original_caption(body, *args, **kwargs)

    def radio_patched(*args, **kwargs):
        inject_css()
        return original_radio(*args, **kwargs)

    st.columns = columns_patched
    st.image = image_patched
    st.markdown = markdown_patched
    st.caption = caption_patched
    st.radio = radio_patched

    try:
        import st_aggrid as _st_aggrid
        original_aggrid = _st_aggrid.AgGrid

        def aggrid_patched(data, *args, **kwargs):
            key = str(kwargs.get("key", ""))
            if key.startswith("archive_grid"):
                kwargs["gridOptions"] = _apply_archive_widths(kwargs.get("gridOptions", {}))
                kwargs["custom_css"] = _merge_css(kwargs.get("custom_css"))
                kwargs["fit_columns_on_grid_load"] = False
                kwargs["height"] = max(int(kwargs.get("height", 0) or 0), 680)
            elif key.startswith("client_grid"):
                kwargs["gridOptions"] = _apply_client_widths(kwargs.get("gridOptions", {}))
                kwargs["custom_css"] = _merge_css(kwargs.get("custom_css"))
                kwargs["fit_columns_on_grid_load"] = False
                kwargs["height"] = max(int(kwargs.get("height", 0) or 0), 480)
            return original_aggrid(data, *args, **kwargs)

        _st_aggrid.AgGrid = aggrid_patched
    except Exception:
        pass
