from pathlib import Path


def _patch_app_source():
    path = Path(__file__).with_name("app.py")
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8")
    original = text

    old_add_client = """def add_client(data, first, last, phone=\"\", email=\"\", notes=\"\", birth_date=\"\", anamnesis=\"\", goals=\"\"):\n    first, last = first.strip(), last.strip()\n    if not first or not last:\n        return False, \"Inserisci nome e cognome.\", None\n"""
    new_add_client = """def add_client(data, first, last, phone=\"\", email=\"\", notes=\"\", birth_date=\"\", anamnesis=\"\", goals=\"\"):\n    first, last, phone = first.strip(), last.strip(), phone.strip()\n    if not first or not last or not phone:\n        return False, \"Inserisci cognome, nome e telefono.\", None\n"""
    text = text.replace(old_add_client, new_add_client)

    old_import = "from st_aggrid import AgGrid, DataReturnMode, GridOptionsBuilder, GridUpdateMode"
    new_import = "from st_aggrid import AgGrid, DataReturnMode, GridOptionsBuilder, GridUpdateMode, JsCode"
    text = text.replace(old_import, new_import)

    old_clients_card = """    if selected:\n        st.session_state[\"open_client_id\"] = selected.get(\"ID\")\n    cid_open = st.session_state.get(\"open_client_id\")\n    if cid_open:\n        st.divider()\n        render_client_card(data, sha, cid_open, prefix=\"clienti\")\n"""
    new_clients_card = """    if selected and selected.get(\"ID\"):\n        st.divider()\n        render_client_card(data, sha, selected.get(\"ID\"), prefix=\"clienti\")\n"""
    text = text.replace(old_clients_card, new_clients_card)

    old_archive_card = """    if selected and selected.get(\"Client ID\"):\n        st.session_state[\"open_client_id\"] = selected.get(\"Client ID\")\n    cid_open = st.session_state.get(\"open_client_id\")\n    if cid_open:\n        st.divider()\n        render_client_card(data, sha, cid_open, prefix=\"archivio\")\n"""
    new_archive_card = """    if selected and selected.get(\"Client ID\"):\n        st.divider()\n        render_client_card(data, sha, selected.get(\"Client ID\"), prefix=\"archivio\")\n"""
    text = text.replace(old_archive_card, new_archive_card)

    old_header = """def render_header():\n    c1, c2 = st.columns([1, 6])\n    with c1:\n        if Path(LOGO_PATH).exists():\n            st.image(LOGO_PATH, width=130)\n    with c2:\n        st.markdown(f\"<h1 style='margin-bottom:0;color:{DARK};'>Prenotazioni Pilates Reformer</h1>\", unsafe_allow_html=True)\n        st.caption(\"Gestionale interno Body Center · clienti, prenotazioni, pagamenti\")\n"""
    new_header = """def render_header():\n    logo_html = \"\"\n    if Path(LOGO_PATH).exists():\n        logo_b64 = base64.b64encode(Path(LOGO_PATH).read_bytes()).decode(\"ascii\")\n        logo_html = f\"<img src='data:image/png;base64,{logo_b64}' style='width:128px;height:128px;object-fit:contain;filter:drop-shadow(0 6px 10px rgba(36,49,66,.10));'>\"\n    st.markdown(\n        f\"\"\"\n        <div style='display:flex;align-items:center;gap:28px;width:100%;box-sizing:border-box;background:linear-gradient(135deg,#f8fbf8 0%,#eef6f1 100%);border:1px solid #dfe8df;border-radius:26px;padding:22px 28px;margin:4px 0 18px 0;box-shadow:0 10px 30px rgba(36,49,66,.07);'>\n            <div style='flex:0 0 auto;'>{logo_html}</div>\n            <div>\n                <h1 style='margin:0;color:#243142;font-size:clamp(2.25rem,4vw,3.15rem);font-weight:850;line-height:1.02;letter-spacing:-.035em;'>Prenotazioni Pilates Reformer</h1>\n                <p style='margin:8px 0 0 0;color:#6f7780;font-size:1.06rem;'>Gestionale interno Body Center · clienti, prenotazioni, pagamenti</p>\n            </div>\n        </div>\n        \"\"\",\n        unsafe_allow_html=True,\n    )\n"""
    text = text.replace(old_header, new_header)

    css_marker = """    .stApp {{ background: #fbfcfb; }}\n"""
    css_insert = """    .stApp {{ background: #fbfcfb; }}\n    .block-container {{ padding-top:1rem !important; max-width:1240px !important; }}\n    div[data-testid=\"stRadio\"] > div {{ gap:.65rem !important; flex-wrap:wrap !important; }}\n    div[data-testid=\"stRadio\"] label {{ min-height:42px !important; padding:.55rem 1rem !important; border-radius:999px !important; border:1px solid #dce6dc !important; background:#fff !important; box-shadow:0 3px 10px rgba(36,49,66,.045) !important; }}\n    div[data-testid=\"stRadio\"] input[type=\"radio\"] {{ display:none !important; }}\n    div[data-testid=\"stRadio\"] label:has(input:checked) {{ background:#496744 !important; border-color:#496744 !important; }}\n    div[data-testid=\"stRadio\"] label:has(input:checked) p {{ color:#fff !important; }}\n    @media (max-width:760px) {{\n        .block-container {{ padding-left:.45rem !important; padding-right:.45rem !important; max-width:100% !important; }}\n        .ag-cell {{ font-size:12px !important; padding-left:4px !important; padding-right:4px !important; }}\n        .ag-header-cell-text {{ font-size:11px !important; }}\n    }}\n"""
    if css_insert not in text:
        text = text.replace(css_marker, css_insert)

    # Hide/remove the audit column from the archive table. Keep the raw data untouched.
    text = text.replace(', "Inserita il", "ID", "Client ID"', ', "ID", "Client ID"')
    text = text.replace(', "Inserita il", "ID", "Client ID"]', ', "ID", "Client ID"]')
    text = text.replace(', "Inserita il": b.get("created_at")', '')
    text = text.replace('    gb.configure_column("Inserita il", editable=False, width=170, cellStyle=cell_style("center"))\n', '')
    text = text.replace('    gb.configure_column("Inserita il", editable=False, width=168, cellStyle=cell_style("center"))\n', '')

    # Sort archive rows alphabetically by client surname/name, then date and time.
    text = text.replace('return df.sort_values(["_sort", "Ora", "Cliente"]).drop(columns=["_sort"]).reset_index(drop=True)', 'return df.sort_values(["Cliente", "_sort", "Ora"]).drop(columns=["_sort"]).reset_index(drop=True)')

    # When clicking the visible Data column, sort by the hidden ISO date, not by the pretty text.
    old_data_col = '    gb.configure_column("Data", editable=False, width=160, cellStyle=cell_style("center"))\n'
    new_data_col = '''    gb.configure_column(
        "Data",
        editable=False,
        width=160,
        comparator=JsCode("""
        function(valueA, valueB, nodeA, nodeB, isDescending) {
            const a = nodeA && nodeA.data ? nodeA.data["Data ISO"] : "";
            const b = nodeB && nodeB.data ? nodeB.data["Data ISO"] : "";
            if (a === b) return 0;
            if (!a) return 1;
            if (!b) return -1;
            return a > b ? 1 : -1;
        }
        """),
        cellStyle=cell_style("center"),
    )
'''
    text = text.replace(old_data_col, new_data_col)

    mobile_functions = '''

def archive_mobile_cards(df, data, sha):
    st.caption("Vista compatta per telefono. Per modificare importi, pagamenti ed email usa la vista tabella.")
    if df.empty:
        st.info("Nessuna prenotazione nel periodo selezionato.")
        return
    for _, r in df.iterrows():
        with st.container(border=True):
            st.markdown(f"**{r.get('Cliente', '')}**")
            st.caption(f"{r.get('Data', '')} · {r.get('Ora', '')} · {r.get('Stato', '')}")
            st.write(f"📞 {r.get('Telefono', '')}")
            if str(r.get('Email', '') or '').strip():
                st.write(f"✉️ {r.get('Email', '')}")
            st.write(f"💶 € {money(r.get('Importo', 0)):.2f} · {'Pagato' if to_bool(r.get('Pagato', False)) else 'Non pagato'}")
            note = str(r.get('Note cliente', '') or '').strip()
            if note:
                st.write(f"📝 {note}")
            if r.get('Client ID') and st.button("Apri scheda cliente", key=f"mobile_archive_{r.get('ID')}"):
                render_client_card(data, sha, r.get('Client ID'), prefix=f"mobile_archive_{r.get('ID')}")


def clients_mobile_cards(view, data, sha):
    st.caption("Vista compatta per telefono.")
    if view.empty:
        st.info("Nessun cliente trovato.")
        return
    for _, r in view.iterrows():
        with st.container(border=True):
            st.markdown(f"**{r.get('Cognome', '')} {r.get('Nome', '')}**")
            if str(r.get('Ultima lezione', '') or '').strip():
                st.caption(f"Ultima lezione: {r.get('Ultima lezione', '')}")
            if st.button("Apri scheda", key=f"mobile_client_{r.get('ID')}"):
                render_client_card(data, sha, r.get('ID'), prefix=f"mobile_client_{r.get('ID')}")
'''
    marker = '\n\ndef render_client_card(data, sha, cid, prefix="client"):\n'
    if 'def archive_mobile_cards(' not in text:
        text = text.replace(marker, mobile_functions + marker)

    clients_toggle = '''    if st.toggle("📱 Vista compatta telefono", key="clients_mobile_view"):
        clients_mobile_cards(view, data, sha)
        return
'''
    archive_toggle = '''    if st.toggle("📱 Vista compatta telefono", key="archive_mobile_view"):
        archive_mobile_cards(df, data, sha)
        return
'''
    text = text.replace(clients_toggle, '')
    text = text.replace(archive_toggle, '')

    old_clients_view = '''    st.caption("Tabella clienti: clicca una riga per aprire la scheda qui sotto.")
    selected = client_grid(view, "client_grid")
'''
    new_clients_view = clients_toggle + old_clients_view
    text = text.replace(old_clients_view, new_clients_view)

    old_archive_view = '''    st.caption("Colonne editabili evidenziate: Email, Importo, Pagato e Note cliente. Clicca una riga per aprire la scheda cliente sotto.")
    grid_key = f"archive_grid_{st.session_state.get('archive_nonce', 0)}"
'''
    new_archive_view = '''    st.caption("Colonne editabili evidenziate: Email, Importo, Pagato e Note cliente. Clicca una riga per aprire la scheda cliente sotto.")
''' + archive_toggle + '''    grid_key = f"archive_grid_{st.session_state.get('archive_nonce', 0)}"
'''
    text = text.replace(old_archive_view, new_archive_view)

    if text != original:
        path.write_text(text, encoding="utf-8")


try:
    _patch_app_source()
except Exception:
    pass
