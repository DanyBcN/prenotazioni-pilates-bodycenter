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

    def _cell_style(align="center", editable=False, bold=False, color=None):
        justify = {"left": "flex-start", "right": "flex-end", "center": "center"}.get(align, "center")
        style = {
            "display": "flex",
            "alignItems": "center",
            "justifyContent": justify,
            "textAlign": align,
            "paddingLeft": "10px",
            "paddingRight": "10px",
            "fontSize": "13px",
            "lineHeight": "1.25",
        }
        if editable:
            style["backgroundColor"] = "#fffdf0"
        if bold:
            style["fontWeight"] = "700"
        if color:
            style["color"] = color
        return style

    def _style_column_defs(grid_options, key):
        if not isinstance(grid_options, dict):
            return grid_options

        grid_options.setdefault("defaultColDef", {})
        grid_options["defaultColDef"].update({
            "sortable": True,
            "filter": True,
            "resizable": True,
            "wrapHeaderText": True,
            "autoHeaderHeight": True,
            "cellStyle": _cell_style("center"),
        })
        grid_options["rowHeight"] = 38
        grid_options["headerHeight"] = 42
        grid_options["suppressHorizontalScroll"] = False

        archive_defs = {
            "Elimina": {"width": 86, "pinned": "left", "cellStyle": _cell_style("center")},
            "Data": {"width": 105, "cellStyle": _cell_style("center")},
            "Giorno": {"width": 115, "cellStyle": _cell_style("center")},
            "Ora": {"width": 82, "cellStyle": _cell_style("center")},
            "Cliente": {"width": 215, "pinned": "left", "cellStyle": _cell_style("left", bold=True, color="#1f5c8f")},
            "Telefono": {"width": 140, "cellStyle": _cell_style("left")},
            "Email": {"width": 245, "cellStyle": _cell_style("left", editable=True)},
            "Istruttrice": {"width": 118, "cellStyle": _cell_style("center")},
            "Stato": {"width": 125, "cellStyle": _cell_style("center")},
            "Importo": {"width": 112, "cellStyle": _cell_style("right", editable=True)},
            "Pagato": {"width": 96, "cellStyle": _cell_style("center", editable=True)},
            "Note cliente": {"width": 300, "wrapText": True, "autoHeight": True, "cellStyle": _cell_style("left", editable=True)},
            "Note prenotazione": {"width": 300, "wrapText": True, "autoHeight": True, "cellStyle": _cell_style("left", editable=True)},
            "Inserita il": {"width": 170, "cellStyle": _cell_style("center")},
        }
        client_defs = {
            "Cognome": {"width": 230, "cellStyle": _cell_style("left", bold=True, color="#243142")},
            "Nome": {"width": 220, "cellStyle": _cell_style("left")},
            "Ultima lezione": {"width": 160, "cellStyle": _cell_style("center")},
        }
        definitions = archive_defs if key.startswith("archive_grid") else client_defs if key.startswith("client_grid") else {}

        for col_def in grid_options.get("columnDefs", []):
            field = col_def.get("field")
            if field in definitions:
                col_def.update(definitions[field])
        return grid_options

    def _merge_css(existing_css):
        css = dict(existing_css or {})
        css.update({
            ".ag-root-wrapper": {"border-radius": "12px", "border": "1px solid #dfe6de", "overflow": "hidden"},
            ".ag-header": {"background-color": "#edf5ef", "border-bottom": "1px solid #d7e3d7"},
            ".ag-header-cell-label": {"justify-content": "center", "text-align": "center", "font-weight": "700", "font-size": "13px", "color": "#243142"},
            ".ag-cell": {"display": "flex", "align-items": "center", "font-size": "13px", "border-right": "1px solid #eef1ee"},
            ".ag-row": {"cursor": "pointer !important"},
            ".ag-row-hover": {"background-color": "#eef6f2 !important", "cursor": "pointer !important"},
            ".ag-row-selected": {"background-color": "#dceee4 !important"},
        })
        return css

    def AgGrid_selection_guard(*args, **kwargs):
        key = str(kwargs.get("key", ""))
        if key.startswith("archive_grid") or key.startswith("client_grid"):
            kwargs["gridOptions"] = _style_column_defs(kwargs.get("gridOptions", {}), key)
            kwargs["custom_css"] = _merge_css(kwargs.get("custom_css"))
            if key.startswith("archive_grid"):
                kwargs["height"] = max(int(kwargs.get("height", 0) or 0), 620)
            elif key.startswith("client_grid"):
                kwargs["height"] = max(int(kwargs.get("height", 0) or 0), 420)
        response = _OriginalAgGrid(*args, **kwargs)
        if key.startswith("archive_grid") or key.startswith("client_grid"):
            selected = response.get("selected_rows", []) if isinstance(response, dict) else []
            if not _has_selected_rows(selected):
                st.session_state.pop("open_client_id", None)
        return response

    _st_aggrid.AgGrid = AgGrid_selection_guard
except Exception:
    pass
