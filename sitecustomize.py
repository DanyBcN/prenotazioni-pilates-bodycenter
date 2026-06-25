try:
    import pandas as pd
    import streamlit as st
    import st_aggrid as _st_aggrid

    _OriginalAgGrid = _st_aggrid.AgGrid
    _OriginalCaption = st.caption

    DAY_ABBR = {
        "Lunedì": "Lun",
        "Martedì": "Mar",
        "Mercoledì": "Mer",
        "Giovedì": "Gio",
        "Venerdì": "Ven",
        "Sabato": "Sab",
        "Domenica": "Dom",
    }
    MONTHS = {
        1: "gennaio",
        2: "febbraio",
        3: "marzo",
        4: "aprile",
        5: "maggio",
        6: "giugno",
        7: "luglio",
        8: "agosto",
        9: "settembre",
        10: "ottobre",
        11: "novembre",
        12: "dicembre",
    }

    def _compact_date(data_value, day_value=""):
        try:
            dt = pd.to_datetime(str(data_value), dayfirst=True, errors="coerce")
            if pd.isna(dt):
                return str(data_value or "")
            day = DAY_ABBR.get(str(day_value or ""), dt.strftime("%a"))
            return f"{day} {dt.day} {MONTHS.get(dt.month, dt.strftime('%m'))} {str(dt.year)[-2:]}"
        except Exception:
            return str(data_value or "")

    def _set_col(grid_options, field, **settings):
        if not isinstance(grid_options, dict):
            return
        for col in grid_options.get("columnDefs", []):
            if col.get("field") == field:
                col.update(settings)
                col["suppressSizeToFit"] = True
                return

    def _patch_archive_options(grid_options):
        if not isinstance(grid_options, dict):
            return grid_options
        grid_options.setdefault("defaultColDef", {})
        grid_options["defaultColDef"].update({
            "resizable": True,
            "sortable": True,
            "filter": True,
        })
        grid_options["rowHeight"] = max(int(grid_options.get("rowHeight", 0) or 0), 42)
        grid_options["headerHeight"] = max(int(grid_options.get("headerHeight", 0) or 0), 46)

        _set_col(grid_options, "Giorno", hide=True)
        _set_col(grid_options, "Note prenotazione", hide=True)
        _set_col(grid_options, "Data", headerName="Data", width=160, minWidth=145)
        _set_col(grid_options, "Cliente", width=250, minWidth=220)
        _set_col(grid_options, "Telefono", width=145, minWidth=130)
        _set_col(grid_options, "Email", width=290, minWidth=250)
        _set_col(grid_options, "Note cliente", width=360, minWidth=300, wrapText=True, autoHeight=True)
        _set_col(grid_options, "Inserita il", width=170, minWidth=150)
        return grid_options

    def AgGrid_patched(data, *args, **kwargs):
        key = str(kwargs.get("key", ""))
        if key.startswith("archive_grid"):
            try:
                if isinstance(data, pd.DataFrame):
                    data = data.copy()
                    if "Data" in data.columns:
                        if "Giorno" in data.columns:
                            data["Data"] = [_compact_date(d, g) for d, g in zip(data["Data"], data["Giorno"])]
                        else:
                            data["Data"] = [_compact_date(d) for d in data["Data"]]
                kwargs["gridOptions"] = _patch_archive_options(kwargs.get("gridOptions", {}))
                kwargs["fit_columns_on_grid_load"] = False
            except Exception:
                pass
        return _OriginalAgGrid(data, *args, **kwargs)

    def caption_patched(body, *args, **kwargs):
        if isinstance(body, str) and "Colonne editabili" in body and "Note prenotazione" in body:
            body = "Colonne editabili evidenziate: Email, Importo, Pagato e Note cliente. Clicca una riga per aprire la scheda cliente sotto."
        return _OriginalCaption(body, *args, **kwargs)

    _st_aggrid.AgGrid = AgGrid_patched
    st.caption = caption_patched
except Exception:
    pass
