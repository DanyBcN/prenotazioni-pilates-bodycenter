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

    def AgGrid_archive_selection_guard(*args, **kwargs):
        response = _OriginalAgGrid(*args, **kwargs)
        key = str(kwargs.get("key", ""))
        if key.startswith("archive_grid"):
            selected = response.get("selected_rows", []) if isinstance(response, dict) else []
            if not _has_selected_rows(selected):
                st.session_state.pop("open_client_id", None)
        return response

    _st_aggrid.AgGrid = AgGrid_archive_selection_guard
except Exception:
    pass
