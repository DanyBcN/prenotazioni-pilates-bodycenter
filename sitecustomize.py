from pathlib import Path


def _patch_app_source():
    path = Path(__file__).with_name("app.py")
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    original = text

    text = text.replace(
'''def render_archive_mobile(df, data, sha):
    cid_open = st.session_state.get("open_client_id")
    if cid_open:
        render_client_card(data, sha, cid_open, prefix="archivio_mobile")
        st.divider()
    if df.empty:
        st.info("Nessuna prenotazione nel filtro selezionato.")
        return
    st.markdown("#### Schede archivio")
    for i, (_, r) in enumerate(df.reset_index(drop=True).iterrows()):
        cid = str(r.get("Client ID", "") or "")
        bid = str(r.get("ID", i) or i)
        with st.container(border=True):
            st.markdown(f"**{r.get('Cliente','')}**")
            st.caption(f"📅 {r.get('Data','')} · 🕒 {r.get('Ora','')} · {r.get('Stato','')}")
            st.caption(f"👩‍🏫 {r.get('Istruttrice','')} · 💶 € {money(r.get('Importo',0)):.2f} · {'Pagato' if to_bool(r.get('Pagato', False)) else 'Non pagato'}")
            tel = str(r.get("Telefono", "") or "")
            email = str(r.get("Email", "") or "")
            note = str(r.get("Note cliente", "") or "")
            if tel:
                st.markdown(f"📞 [{tel}](tel:{tel})")
            if email:
                st.caption(f"✉️ {email}")
            if note:
                st.caption(f"📝 {note}")
            if cid:
                if st.button("Apri scheda cliente", key=f"arch_mobile_open_{bid}_{i}", use_container_width=True):
                    st.session_state["open_client_id"] = cid
                    st.session_state["section"] = "Archivio"
                    try:
                        st.query_params["_bc_mobile"] = "1"
                    except Exception:
                        pass
                    st.rerun()
''',
'''def render_archive_mobile(df, data, sha):
    cid_open = st.session_state.get("open_client_id")
    if cid_open:
        if st.button("← Torna alle schede", key="arch_mobile_back", use_container_width=True):
            st.session_state.pop("open_client_id", None)
            st.rerun()
        render_client_card(data, sha, cid_open, prefix="archivio_mobile")
        return
    if df.empty:
        st.info("Nessuna prenotazione nel filtro selezionato.")
        return
    st.markdown("#### Schede archivio")
    for i, (_, r) in enumerate(df.reset_index(drop=True).iterrows()):
        cid = str(r.get("Client ID", "") or "")
        bid = str(r.get("ID", i) or i)
        with st.container(border=True):
            st.markdown(f"**{r.get('Cliente','')}**")
            st.caption(f"📅 {r.get('Data','')} · 🕒 {r.get('Ora','')} · {r.get('Stato','')}")
            st.caption(f"👩‍🏫 {r.get('Istruttrice','')} · 💶 € {money(r.get('Importo',0)):.2f} · {'Pagato' if to_bool(r.get('Pagato', False)) else 'Non pagato'}")
            tel = str(r.get("Telefono", "") or "")
            email = str(r.get("Email", "") or "")
            note = str(r.get("Note cliente", "") or "")
            if tel:
                st.markdown(f"📞 [{tel}](tel:{tel})")
            if email:
                st.caption(f"✉️ {email}")
            if note:
                st.caption(f"📝 {note}")
            if cid:
                if st.button("Apri scheda cliente", key=f"arch_mobile_open_{bid}_{i}", use_container_width=True):
                    st.session_state["open_client_id"] = cid
                    st.session_state["section"] = "Archivio"
                    st.rerun()
''')

    text = text.replace(
'''            if prefix.startswith("archivio"):
                st.session_state["section"] = "Archivio"
                try:
                    st.query_params["_bc_mobile"] = "1"
                except Exception:
                    pass
''',
'''            if prefix.startswith("archivio"):
                st.session_state["section"] = "Archivio"
''')

    if text != original:
        path.write_text(text, encoding="utf-8")


try:
    _patch_app_source()
except Exception:
    pass
