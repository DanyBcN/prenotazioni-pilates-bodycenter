try:
    import streamlit as st
    import st_aggrid as _st_aggrid

    _OriginalAgGrid = _st_aggrid.AgGrid

    def _has_selected_rows(selected):
        if selected is None:
            return False
        try:
            if hasattr(selected, "empty"):
                return not selected.empty
        except Exception:
            pass
        try:
            return len(selected) > 0
        except Exception:
            return False

    def _style(align="center", editable=False, bold=False, color=None):
        justify = {"left": "flex-start", "right": "flex-end", "center": "center"}.get(align, "center")
        out = {
            "display": "flex",
            "alignItems": "center",
            "justifyContent": justify,
            "textAlign": align,
            "fontSize": "13px",
            "paddingLeft": "10px",
            "paddingRight": "10px",
            "lineHeight": "1.25",
        }
        if editable:
            out["backgroundColor"] = "#fffdf0"
        if bold:
            out["fontWeight"] = "700"
        if color:
            out["color"] = color
        return out

    def _apply_defs(grid_options, key):
        if not isinstance(grid_options, dict):
            return grid_options
        grid_options.setdefault("defaultColDef", {})
        grid_options["defaultColDef"].update({
            "sortable": True,
            "filter": True,
            "resizable": True,
            "wrapHeaderText": True,
            "autoHeaderHeight": True,
            "cellStyle": _style("center"),
        })
        grid_options["rowHeight"] = 38 if key.startswith("archive_grid") else 40
        grid_options["headerHeight"] = 44
        grid_options["suppressHorizontalScroll"] = False

        archive = {
            "Elimina": {"width": 82, "pinned": "left", "cellStyle": _style("center")},
            "Data": {"width": 104, "cellStyle": _style("center")},
            "Giorno": {"width": 110, "cellStyle": _style("center")},
            "Ora": {"width": 78, "cellStyle": _style("center")},
            "Cliente": {"width": 220, "pinned": "left", "cellStyle": _style("left", bold=True, color="#1f5c8f")},
            "Telefono": {"width": 135, "cellStyle": _style("left")},
            "Email": {"width": 250, "cellStyle": _style("left", editable=True)},
            "Istruttrice": {"width": 112, "cellStyle": _style("center")},
            "Stato": {"width": 118, "cellStyle": _style("center")},
            "Importo": {"width": 112, "cellStyle": _style("right", editable=True)},
            "Pagato": {"width": 92, "cellStyle": _style("center", editable=True)},
            "Note cliente": {"width": 330, "wrapText": True, "autoHeight": True, "cellStyle": _style("left", editable=True)},
            "Note prenotazione": {"width": 330, "wrapText": True, "autoHeight": True, "cellStyle": _style("left", editable=True)},
            "Inserita il": {"width": 168, "cellStyle": _style("center")},
        }
        clients = {
            "Cognome": {"width": 260, "cellStyle": _style("left", bold=True, color="#243142")},
            "Nome": {"width": 245, "cellStyle": _style("left")},
            "Ultima lezione": {"width": 170, "cellStyle": _style("center")},
        }
        mapping = archive if key.startswith("archive_grid") else clients if key.startswith("client_grid") else {}
        for c in grid_options.get("columnDefs", []):
            f = c.get("field")
            if f in mapping:
                c.update(mapping[f])
        return grid_options

    def _css(existing=None):
        css = dict(existing or {})
        css.update({
            ".ag-root-wrapper": {"border-radius": "14px", "border": "1px solid #dfe6de", "overflow": "hidden", "box-shadow": "0 4px 14px rgba(36,49,66,0.05)"},
            ".ag-header": {"background-color": "#edf5ef", "border-bottom": "1px solid #d7e3d7"},
            ".ag-header-cell-label": {"justify-content": "center", "text-align": "center", "font-weight": "700", "font-size": "13px", "color": "#243142"},
            ".ag-cell": {"display": "flex", "align-items": "center", "font-size": "13px", "border-right": "1px solid #eef1ee"},
            ".ag-row": {"cursor": "pointer !important"},
            ".ag-row-hover": {"background-color": "#eef6f2 !important", "cursor": "pointer !important"},
            ".ag-row-selected": {"background-color": "#dceee4 !important"},
            ".ag-cell[col-id='Importo']": {"justify-content": "flex-end !important", "text-align": "right !important"},
            ".ag-cell[col-id='Cliente']": {"justify-content": "flex-start !important", "text-align": "left !important", "font-weight": "700", "color": "#1f5c8f"},
            ".ag-cell[col-id='Cognome']": {"justify-content": "flex-start !important", "text-align": "left !important", "font-weight": "700"},
            ".ag-cell[col-id='Nome']": {"justify-content": "flex-start !important", "text-align": "left !important"},
            ".ag-cell[col-id='Telefono']": {"justify-content": "flex-start !important", "text-align": "left !important"},
            ".ag-cell[col-id='Email']": {"justify-content": "flex-start !important", "text-align": "left !important", "background-color": "#fffdf0"},
            ".ag-cell[col-id='Note cliente']": {"justify-content": "flex-start !important", "text-align": "left !important", "background-color": "#fffdf0"},
            ".ag-cell[col-id='Note prenotazione']": {"justify-content": "flex-start !important", "text-align": "left !important", "background-color": "#fffdf0"},
            ".ag-cell[col-id='Pagato']": {"justify-content": "center !important", "text-align": "center !important", "background-color": "#fffdf0"},
            ".ag-cell[col-id='Elimina']": {"justify-content": "center !important", "text-align": "center !important"},
        })
        return css

    def AgGrid_selection_guard(*args, **kwargs):
        key = str(kwargs.get("key", ""))
        if key.startswith("archive_grid") or key.startswith("client_grid"):
            kwargs["gridOptions"] = _apply_defs(kwargs.get("gridOptions", {}), key)
            kwargs["custom_css"] = _css(kwargs.get("custom_css"))
            kwargs["fit_columns_on_grid_load"] = False
            if key.startswith("archive_grid"):
                kwargs["height"] = 680
            else:
                kwargs["height"] = max(int(kwargs.get("height", 0) or 0), 460)
        response = _OriginalAgGrid(*args, **kwargs)
        if key.startswith("archive_grid") or key.startswith("client_grid"):
            selected = response.get("selected_rows", []) if isinstance(response, dict) else []
            if not _has_selected_rows(selected):
                st.session_state.pop("open_client_id", None)
        return response

    _st_aggrid.AgGrid = AgGrid_selection_guard
except Exception:
    pass
