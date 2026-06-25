from pathlib import Path
import re


def _patch_app_source():
    path = Path(__file__).with_name("app.py")
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8")
    original = text

    if "import streamlit.components.v1 as components" not in text:
        text = text.replace("import streamlit as st\n", "import streamlit as st\nimport streamlit.components.v1 as components\n")

    text = text.replace(
        'return df.sort_values(["_sort", "Ora", "Cliente"]).drop(columns=["_sort"]).reset_index(drop=True)',
        'return df.sort_values(["Cliente", "_sort", "Ora"]).drop(columns=["_sort"]).reset_index(drop=True)',
    )

    css_extra = '''
    /* BC_MOBILE_STABLE */
    @media (max-width:760px) {
        .block-container { padding-left:.7rem !important; padding-right:.7rem !important; max-width:100% !important; padding-top:.45rem !important; }
        h1 { font-size:1.9rem !important; line-height:1.08 !important; margin-bottom:.25rem !important; }
        img { max-width:92px !important; height:auto !important; }
        div[data-testid="stHorizontalBlock"] { gap:.35rem !important; }
        div[data-testid="stRadio"] > div { display:grid !important; grid-template-columns:1fr 1fr !important; gap:.45rem !important; }
        div[data-testid="stRadio"] label {
            width:100% !important;
            min-height:42px !important;
            padding:.45rem .55rem !important;
            border-radius:14px !important;
            border:1px solid #dce6dc !important;
            background:#ffffff !important;
            box-shadow:0 2px 8px rgba(36,49,66,.06) !important;
            overflow:visible !important;
        }
        div[data-testid="stRadio"] input[type="radio"] { display:none !important; }
        div[data-testid="stRadio"] label p {
            color:#243142 !important;
            font-size:.86rem !important;
            font-weight:800 !important;
            white-space:normal !important;
            overflow:visible !important;
            text-overflow:clip !important;
            line-height:1.1 !important;
        }
        div[data-testid="stRadio"] label:has(input:checked) { background:#496744 !important; border-color:#496744 !important; }
        div[data-testid="stRadio"] label:has(input:checked) p { color:#ffffff !important; }
    }
'''
    if "BC_MOBILE_STABLE" not in text:
        text = text.replace("    .stApp { background: #fbfcfb; }\n", "    .stApp { background: #fbfcfb; }\n" + css_extra)

    # Remove older helper block before reinserting the stable one.
    text = re.sub(r'\n\ndef bc_sync_mobile_mode\(\):\n.*?\n\ndef render_archive\(data, sha\):\n', '\n\ndef render_archive(data, sha):\n', text, flags=re.S)

    helpers = r'''

def bc_sync_mobile_mode():
    try:
        components.html("""
        <script>
        try {
          const mobile = (window.parent.innerWidth || window.innerWidth || 1200) <= 760;
          const url = new URL(window.parent.location.href);
          const wanted = mobile ? "1" : "0";
          if (url.searchParams.get("_bc_mobile") !== wanted) {
            url.searchParams.set("_bc_mobile", wanted);
            window.parent.location.replace(url.toString());
          }
        } catch(e) {}
        </script>
        """, height=0)
    except Exception:
        pass


def bc_is_mobile_client():
    if st.session_state.get("bc_force_mobile", False):
        return True
    try:
        headers = getattr(st, "context", None).headers
        ua = str(headers.get("user-agent", headers.get("User-Agent", ""))).lower()
    except Exception:
        ua = ""
    if any(t in ua for t in ["iphone", "android", "mobile", "ipad", "ipod"]):
        return True
    try:
        flag = str(st.query_params.get("_bc_mobile", "")).lower()
        if flag in {"1", "true", "yes", "mobile"}:
            return True
        if flag in {"0", "false", "no", "desktop"}:
            return False
    except Exception:
        pass
    return False


def bc_archive_mobile_cards(df, data, sha):
    st.markdown("#### Archivio telefono")
    cid_open = st.session_state.get("open_client_id")
    if cid_open:
        render_client_card(data, sha, cid_open, prefix="archivio_mobile")
        st.divider()

    if df.empty:
        st.info("Nessuna prenotazione nel filtro selezionato.")
        return

    for i, (_, r) in enumerate(df.reset_index(drop=True).iterrows()):
        cliente = str(r.get("Cliente", "") or "")
        data_txt = str(r.get("Data", "") or "")
        ora = str(r.get("Ora", "") or "")
        stato = str(r.get("Stato", "") or "")
        telefono = str(r.get("Telefono", "") or "")
        email = str(r.get("Email", "") or "")
        note = str(r.get("Note cliente", "") or "")
        istr = str(r.get("Istruttrice", "") or "")
        cid = str(r.get("Client ID", "") or "")
        bid = str(r.get("ID", i) or i)
        importo = f"€ {money(r.get('Importo', 0)):.2f}"
        pagato = "Pagato" if to_bool(r.get("Pagato", False)) else "Non pagato"

        with st.container(border=True):
            st.markdown(f"**{cliente}**")
            st.caption(f"📅 {data_txt} · 🕒 {ora} · {stato}")
            st.caption(f"👩‍🏫 {istr} · 💶 {importo} · {pagato}")
            if telefono:
                st.markdown(f"📞 [{telefono}](tel:{telefono})")
            if email:
                st.caption(f"✉️ {email}")
            if note:
                st.caption(f"📝 {note}")
            if cid:
                if st.button("Apri scheda cliente", key=f"arch_mobile_open_{bid}_{i}", use_container_width=True):
                    st.session_state["open_client_id"] = cid
                    st.session_state["bc_force_mobile"] = True
                    try:
                        st.query_params["_bc_mobile"] = "1"
                    except Exception:
                        pass
                    st.rerun()
'''
    text = text.replace("\n\ndef render_archive(data, sha):\n", helpers + "\n\ndef render_archive(data, sha):\n")

    new_render_archive = r'''def render_archive(data, sha):
    st.subheader("Archivio, pagamenti e statistiche")
    bc_sync_mobile_mode()

    dfa = archive_df(data)
    if dfa.empty:
        st.info("Nessuna prenotazione presente.")
        return

    opt = st.selectbox("Scegli periodo", ["Anno in corso", "Mese selezionato", "Periodo personalizzato", "Ultimi 3 mesi", "Ultimi 6 mesi", "Ultimo anno"], index=0)
    today = date.today()
    if opt == "Mese selezionato":
        m = parse_date(st.date_input("Mese di riferimento", value=today, format="DD/MM/YYYY"))
        start = m.replace(day=1)
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    elif opt == "Periodo personalizzato":
        a, b = st.columns(2)
        start = parse_date(a.date_input("Dal", value=date(today.year, 1, 1), format="DD/MM/YYYY"))
        end = parse_date(b.date_input("Al", value=date(today.year, 12, 31), format="DD/MM/YYYY"))
    else:
        start, end = period_range(opt)

    dfp = filter_period(dfa, start, end)
    label = f"Periodo: {start.strftime('%d-%m-%Y')} - {end.strftime('%d-%m-%Y')}"
    st.caption(label)

    total, paid, unpaid, per = summary(dfp)
    a, b, c = st.columns(3)
    a.metric("Totale complessivo", f"€ {total:.2f}")
    b.metric("Totale pagato", f"€ {paid:.2f}")
    c.metric("Totale non pagato", f"€ {unpaid:.2f}")

    status = st.multiselect("Filtra stato archivio", ["Confermata", "Lista attesa", "Annullata"], default=["Confermata", "Lista attesa"])
    only = st.checkbox("Mostra in tabella solo il periodo selezionato", value=True)
    df = dfp.copy() if only else dfa.copy()
    if status:
        df = df[df["Stato"].isin(status)]

    if bc_is_mobile_client():
        bc_archive_mobile_cards(df, data, sha)
        return

    st.dataframe(per, use_container_width=True, hide_index=True)
    st.markdown("#### Modifica importi, pagamenti e note")
    st.caption("Colonne editabili evidenziate: Email, Importo, Pagato e Note cliente. Clicca una riga per aprire la scheda cliente sotto.")
    grid_key = f"archive_grid_{st.session_state.get('archive_nonce', 0)}"
    edited, selected = archive_grid(df, grid_key)

    if selected and selected.get("Client ID"):
        st.session_state["open_client_id"] = selected.get("Client ID")
    cid_open = st.session_state.get("open_client_id")
    if cid_open:
        st.divider()
        render_client_card(data, sha, cid_open, prefix="archivio")

    a, b = st.columns(2)
    if a.button("Salva modifiche importi/pagamenti/note"):
        n = update_archive(data, edited)
        if n:
            save_data(data, sha, "Update archive")
            st.session_state["archive_nonce"] = int(st.session_state.get("archive_nonce", 0)) + 1
            st.success(f"Aggiornate {n} righe/prenotazioni.")
            st.rerun()
        else:
            st.info("Nessuna modifica da salvare.")

    ids = edited.loc[edited.get("Elimina", False).apply(to_bool) == True, "ID"].dropna().astype(str).tolist() if not edited.empty else []
    if b.button("Elimina selezionate", type="primary"):
        if not ids:
            st.error("Non hai selezionato nessuna prenotazione da eliminare.")
        else:
            n = delete_bookings(data, ids)
            save_data(data, sha, "Delete bookings")
            request_section("📋 Archivio")
            st.session_state["archive_nonce"] = int(st.session_state.get("archive_nonce", 0)) + 1
            st.success(f"Eliminate {n} prenotazioni.")
            st.rerun()

    a, b = st.columns(2)
    a.download_button("Scarica Excel", data=make_excel(edited), file_name="prenotazioni_pilates.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    b.download_button("Scarica PDF archivio", data=make_pdf(edited, label), file_name="archivio_prenotazioni_pilates.pdf", mime="application/pdf")
'''
    text = re.sub(r'def render_archive\(data, sha\):\n.*?\n\nst\.set_page_config', new_render_archive + "\n\nst.set_page_config", text, flags=re.S)

    replacement_save = '''        if ok:
            save_data(data, sha, "Update client record")
            st.session_state["archive_nonce"] = int(st.session_state.get("archive_nonce", 0)) + 1
            st.session_state["client_nonce"] = int(st.session_state.get("client_nonce", 0)) + 1
            if str(prefix).startswith("archivio"):
                st.session_state["bc_force_mobile"] = True
                st.session_state["section"] = "📋 Archivio"
                try:
                    st.query_params["_bc_mobile"] = "1"
                except Exception:
                    pass
            st.session_state.pop("open_client_id", None)
            st.success(msg)
            st.rerun()
'''
    text = re.sub(
        r'        if ok:\n            save_data\(data, sha, "Update client record"\)\n.*?            st\.rerun\(\)\n',
        replacement_save,
        text,
        count=1,
        flags=re.S,
    )

    text = text.replace('    selected = client_grid(view, "client_grid")\n', '    selected = client_grid(view, f"client_grid_{st.session_state.get(\'client_nonce\', 0)}")\n')
    text = text.replace(
        '''section = st.radio("Sezione", SECTIONS, horizontal=True, key="section", label_visibility="collapsed")
st.divider()
''',
        '''section = st.radio("Sezione", SECTIONS, horizontal=True, key="section", label_visibility="collapsed")
if st.session_state.get("_last_section") != section:
    st.session_state.pop("open_client_id", None)
    st.session_state["_last_section"] = section
st.divider()
'''
    )

    if text != original:
        path.write_text(text, encoding="utf-8")


try:
    _patch_app_source()
except Exception:
    pass
