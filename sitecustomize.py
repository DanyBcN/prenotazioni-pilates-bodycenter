from pathlib import Path


def _patch_app_source():
    path = Path(__file__).with_name("app.py")
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8")
    original = text

    text = text.replace(
        '''def add_client(data, first, last, phone="", email="", notes="", birth_date="", anamnesis="", goals=""):
    first, last = first.strip(), last.strip()
    if not first or not last:
        return False, "Inserisci nome e cognome.", None
''',
        '''def add_client(data, first, last, phone="", email="", notes="", birth_date="", anamnesis="", goals=""):
    first, last, phone = first.strip(), last.strip(), phone.strip()
    if not first or not last or not phone:
        return False, "Inserisci cognome, nome e telefono.", None
'''
    )

    text = text.replace(
        "from st_aggrid import AgGrid, DataReturnMode, GridOptionsBuilder, GridUpdateMode",
        "from st_aggrid import AgGrid, DataReturnMode, GridOptionsBuilder, GridUpdateMode, JsCode",
    )

    text = text.replace(
        '''    if selected:
        st.session_state["open_client_id"] = selected.get("ID")
    cid_open = st.session_state.get("open_client_id")
    if cid_open:
        st.divider()
        render_client_card(data, sha, cid_open, prefix="clienti")
''',
        '''    if selected and selected.get("ID"):
        st.divider()
        render_client_card(data, sha, selected.get("ID"), prefix="clienti")
'''
    )

    text = text.replace(
        '''    if selected and selected.get("Client ID"):
        st.session_state["open_client_id"] = selected.get("Client ID")
    cid_open = st.session_state.get("open_client_id")
    if cid_open:
        st.divider()
        render_client_card(data, sha, cid_open, prefix="archivio")
''',
        '''    if selected and selected.get("Client ID"):
        st.divider()
        render_client_card(data, sha, selected.get("Client ID"), prefix="archivio")
'''
    )

    text = text.replace(
        '''def render_header():
    c1, c2 = st.columns([1, 6])
    with c1:
        if Path(LOGO_PATH).exists():
            st.image(LOGO_PATH, width=130)
    with c2:
        st.markdown(f"<h1 style='margin-bottom:0;color:{DARK};'>Prenotazioni Pilates Reformer</h1>", unsafe_allow_html=True)
        st.caption("Gestionale interno Body Center · clienti, prenotazioni, pagamenti")
''',
        '''def render_header():
    logo_html = ""
    if Path(LOGO_PATH).exists():
        logo_b64 = base64.b64encode(Path(LOGO_PATH).read_bytes()).decode("ascii")
        logo_html = f"<img src='data:image/png;base64,{logo_b64}' style='width:128px;height:128px;object-fit:contain;filter:drop-shadow(0 6px 10px rgba(36,49,66,.10));'>"
    st.markdown(
        f"""
        <div style='display:flex;align-items:center;gap:28px;width:100%;box-sizing:border-box;background:linear-gradient(135deg,#f8fbf8 0%,#eef6f1 100%);border:1px solid #dfe8df;border-radius:26px;padding:22px 28px;margin:4px 0 18px 0;box-shadow:0 10px 30px rgba(36,49,66,.07);'>
            <div style='flex:0 0 auto;'>{logo_html}</div>
            <div>
                <h1 style='margin:0;color:#243142;font-size:clamp(2.25rem,4vw,3.15rem);font-weight:850;line-height:1.02;letter-spacing:-.035em;'>Prenotazioni Pilates Reformer</h1>
                <p style='margin:8px 0 0 0;color:#6f7780;font-size:1.06rem;'>Gestionale interno Body Center · clienti, prenotazioni, pagamenti</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
'''
    )

    css_marker = '''    .stApp {{ background: #fbfcfb; }}
'''
    css_insert = '''    .stApp {{ background: #fbfcfb; }}
    .block-container {{ padding-top:1rem !important; max-width:1240px !important; }}
    div[data-testid="stRadio"] > div {{ gap:.65rem !important; flex-wrap:wrap !important; }}
    div[data-testid="stRadio"] label {{ min-height:42px !important; padding:.55rem 1rem !important; border-radius:999px !important; border:1px solid #dce6dc !important; background:#fff !important; box-shadow:0 3px 10px rgba(36,49,66,.045) !important; }}
    div[data-testid="stRadio"] input[type="radio"] {{ display:none !important; }}
    div[data-testid="stRadio"] label:has(input:checked) {{ background:#496744 !important; border-color:#496744 !important; }}
    div[data-testid="stRadio"] label:has(input:checked) p {{ color:#fff !important; }}
    @media (max-width:760px) {{
        .block-container {{ padding-left:.45rem !important; padding-right:.45rem !important; max-width:100% !important; }}
        .ag-theme-streamlit, .ag-root-wrapper {{ max-width:100vw !important; }}
    }}
'''
    if css_insert not in text:
        text = text.replace(css_marker, css_insert)

    text = text.replace(', "Inserita il", "ID", "Client ID"', ', "ID", "Client ID"')
    text = text.replace(', "Inserita il", "ID", "Client ID"]', ', "ID", "Client ID"]')
    text = text.replace(', "Inserita il": b.get("created_at")', '')
    text = text.replace('    gb.configure_column("Inserita il", editable=False, width=170, cellStyle=cell_style("center"))\n', '')
    text = text.replace('    gb.configure_column("Inserita il", editable=False, width=168, cellStyle=cell_style("center"))\n', '')

    text = text.replace(
        'return df.sort_values(["_sort", "Ora", "Cliente"]).drop(columns=["_sort"]).reset_index(drop=True)',
        'return df.sort_values(["Cliente", "_sort", "Ora"]).drop(columns=["_sort"]).reset_index(drop=True)',
    )

    text = text.replace(
        '    gb.configure_column("Data", editable=False, width=160, cellStyle=cell_style("center"))\n',
        '''    gb.configure_column(
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
    )

    mobile_functions = '''

def archive_mobile_cards(df, data, sha):
    st.caption("Vista telefono: schede verticali leggibili. Premi 'Mostra tabella PC' solo da computer.")
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

    # Remove all previous mobile toggles/blocks to avoid remembered states and duplicate widgets.
    for block in [
        '''    if st.toggle("📱 Vista compatta telefono", key="clients_mobile_view"):
        clients_mobile_cards(view, data, sha)
        return
''',
        '''    if st.toggle("📱 Vista compatta telefono", key="archive_mobile_view"):
        archive_mobile_cards(df, data, sha)
        return
''',
        '''    if st.toggle("📱 Vista compatta telefono", value=True, key="archive_mobile_view"):
        archive_mobile_cards(df, data, sha)
        return
''',
        '''    if st.toggle("📱 Vista compatta telefono", value=True, key="archive_mobile_view_v2"):
        archive_mobile_cards(df, data, sha)
        return
''',
        '''    if st.toggle("💻 Mostra tabella PC", value=False, key="archive_show_pc_table_v3"):
        pass
    else:
        return
''',
    ]:
        text = text.replace(block, '')

    old_clients_view = '''    st.caption("Tabella clienti: clicca una riga per aprire la scheda qui sotto.")
    selected = client_grid(view, "client_grid")
'''
    clients_block = '''    if st.toggle("📱 Vista compatta telefono", key="clients_mobile_view"):
        clients_mobile_cards(view, data, sha)
        return
'''
    if clients_block not in text:
        text = text.replace(old_clients_view, clients_block + old_clients_view)

    table_marker = '    st.markdown("#### Modifica importi, pagamenti e note")\n'
    forced_mobile = '''    st.markdown("#### Archivio telefono")
    archive_mobile_cards(df, data, sha)
    if not st.toggle("💻 Mostra tabella PC", value=False, key="archive_show_pc_table_v3"):
        return

'''
    text = text.replace(forced_mobile, '')
    text = text.replace(table_marker, forced_mobile + table_marker)

    if text != original:
        path.write_text(text, encoding="utf-8")


try:
    _patch_app_source()
except Exception:
    pass
