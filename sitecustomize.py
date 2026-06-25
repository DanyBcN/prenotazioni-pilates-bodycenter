from pathlib import Path
import re


def _patch_app_source():
    path = Path(__file__).with_name("app.py")
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8")
    original = text

    # Repair broken duplicate mobile guard that caused IndentationError.
    text = text.replace(
        '    if not is_mobile_client():\n    if not is_mobile_client():\n        st.dataframe(per, use_container_width=True, hide_index=True)\n',
        '    if not is_mobile_client():\n        st.dataframe(per, use_container_width=True, hide_index=True)\n'
    )
    text = re.sub(r'(?m)^    if not is_mobile_client\(\):\n(?=    if not is_mobile_client\(\):)', '', text)
    text = text.replace(
        '    if not is_mobile_client():\n    st.dataframe(per, use_container_width=True, hide_index=True)\n',
        '    if not is_mobile_client():\n        st.dataframe(per, use_container_width=True, hide_index=True)\n'
    )

    # Required client fields.
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

    if 'import streamlit.components.v1 as components' not in text:
        text = text.replace('import streamlit as st\n', 'import streamlit as st\nimport streamlit.components.v1 as components\n')
    text = text.replace(
        'from st_aggrid import AgGrid, DataReturnMode, GridOptionsBuilder, GridUpdateMode',
        'from st_aggrid import AgGrid, DataReturnMode, GridOptionsBuilder, GridUpdateMode, JsCode'
    )
    text = text.replace(', JsCode, JsCode', ', JsCode')

    # Archive dataframe: remove audit column and sort by client by default.
    text = text.replace(', "Inserita il", "ID", "Client ID"', ', "ID", "Client ID"')
    text = text.replace(', "Inserita il", "ID", "Client ID"]', ', "ID", "Client ID"]')
    text = text.replace(', "Inserita il": b.get("created_at")', '')
    text = text.replace('    gb.configure_column("Inserita il", editable=False, width=170, cellStyle=cell_style("center"))\n', '')
    text = text.replace('    gb.configure_column("Inserita il", editable=False, width=168, cellStyle=cell_style("center"))\n', '')
    text = text.replace(
        'return df.sort_values(["_sort", "Ora", "Cliente"]).drop(columns=["_sort"]).reset_index(drop=True)',
        'return df.sort_values(["Cliente", "_sort", "Ora"]).drop(columns=["_sort"]).reset_index(drop=True)'
    )

    # Force PC table initial sort by Cliente.
    text = text.replace(
        '    gb.configure_column("Cliente", editable=False, width=230, pinned="left", cellStyle=cell_style("left", bold=True, color="#1f5c8f"))\n',
        '    gb.configure_column("Cliente", editable=False, width=230, pinned="left", sort="asc", sortIndex=0, cellStyle=cell_style("left", bold=True, color="#1f5c8f"))\n'
    )

    # Correct Data sorting when clicked.
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

    # Mobile helpers.
    helpers = '''

def sync_mobile_mode():
    try:
        components.html("""
        <script>
        try {
          const mobile = (window.parent.innerWidth || window.innerWidth || 1200) <= 760;
          const url = new URL(window.parent.location.href);
          const val = mobile ? "1" : "0";
          if (url.searchParams.get("_bc_mobile") !== val) {
            url.searchParams.set("_bc_mobile", val);
            window.parent.location.replace(url.toString());
          }
        } catch(e) {}
        </script>
        """, height=0)
    except Exception:
        pass


def is_mobile_client():
    try:
        flag = str(st.query_params.get("_bc_mobile", "")).lower()
        if flag in {"1", "true", "yes", "mobile"}:
            return True
        if flag in {"0", "false", "no", "desktop"}:
            return False
    except Exception:
        pass
    try:
        headers = getattr(st, "context", None).headers
        ua = str(headers.get("user-agent", headers.get("User-Agent", ""))).lower()
    except Exception:
        ua = ""
    return any(token in ua for token in ["iphone", "android", "mobile", "ipad", "ipod"])


def archive_mobile_html(df):
    cards = []
    for _, r in df.iterrows():
        cliente = html.escape(str(r.get("Cliente", "") or ""))
        data = html.escape(str(r.get("Data", "") or ""))
        ora = html.escape(str(r.get("Ora", "") or ""))
        stato = html.escape(str(r.get("Stato", "") or ""))
        telefono_raw = str(r.get("Telefono", "") or "")
        telefono = html.escape(telefono_raw)
        email = html.escape(str(r.get("Email", "") or ""))
        note = html.escape(str(r.get("Note cliente", "") or ""))
        pagamento = "Pagato" if to_bool(r.get("Pagato", False)) else "Non pagato"
        importo = f"€ {money(r.get('Importo', 0)):.2f}"
        tel_link = f"<a href='tel:{telefono_raw}' style='color:#1f5c8f;text-decoration:none;font-weight:700;'>{telefono}</a>" if telefono_raw else ""
        email_html = f"<div style='font-size:.9rem;color:#68727d;margin-top:4px;'>✉️ {email}</div>" if email else ""
        note_html = f"<div style='margin-top:10px;background:#f5f7f4;border-radius:12px;padding:9px 10px;color:#39434d;font-size:.92rem;'>📝 {note}</div>" if note else ""
        cards.append(
            "<div style='background:white;border:1px solid #dde7dc;border-radius:18px;padding:14px 14px;margin:10px 0;box-shadow:0 4px 14px rgba(36,49,66,.06);'>"
            f"<div style='font-size:1.08rem;font-weight:850;color:#243142;margin-bottom:3px;'>{cliente}</div>"
            f"<div style='font-size:.92rem;color:#496744;font-weight:750;margin-bottom:8px;'>📅 {data} · 🕒 {ora} · {stato}</div>"
            f"<div style='font-size:.95rem;color:#39434d;'>📞 {tel_link}</div>"
            f"{email_html}"
            f"<div style='margin-top:8px;font-size:.95rem;color:#243142;'>💶 <b>{importo}</b> · {pagamento}</div>"
            f"{note_html}"
            "</div>"
        )
    st.markdown("<div class='mobile-archive'>" + "".join(cards) + "</div>", unsafe_allow_html=True)
'''
    if 'def sync_mobile_mode(' not in text:
        text = text.replace('\n\ndef render_archive(data, sha):\n', helpers + '\n\ndef render_archive(data, sha):\n')

    # Make mobile CSS defensive.
    if '.mobile-archive' not in text:
        text = text.replace(
            '    .stApp {{ background: #fbfcfb; }}\n',
            '    .stApp {{ background: #fbfcfb; }}\n    .mobile-archive {{ display:none !important; }}\n    @media (max-width:760px) {{ .mobile-archive {{ display:block !important; }} div[data-testid="stCustomComponentV1"], div[data-testid="stDataFrame"], div[data-testid="stDataEditor"], .ag-root-wrapper, .ag-theme-streamlit {{ display:none !important; height:0 !important; overflow:hidden !important; }} }}\n    @media (min-width:761px) {{ .mobile-archive {{ display:none !important; }} }}\n'
        )

    # Remove old mobile insertions and insert exactly once before the PC table.
    text = text.replace('    archive_mobile_html(df)\n    if is_mobile_client():\n        return\n', '')
    text = text.replace('    archive_mobile_html(df)\n', '')
    text = text.replace('    sync_mobile_mode()\n', '')
    text = text.replace('    total, paid, unpaid, per = summary(dfp)\n', '    sync_mobile_mode()\n    total, paid, unpaid, per = summary(dfp)\n')
    text = text.replace('    st.dataframe(per, use_container_width=True, hide_index=True)\n', '    if not is_mobile_client():\n        st.dataframe(per, use_container_width=True, hide_index=True)\n')
    text = text.replace(
        '    if not is_mobile_client():\n    if not is_mobile_client():\n        st.dataframe(per, use_container_width=True, hide_index=True)\n',
        '    if not is_mobile_client():\n        st.dataframe(per, use_container_width=True, hide_index=True)\n'
    )
    text = text.replace(
        '    st.markdown("#### Modifica importi, pagamenti e note")\n',
        '    archive_mobile_html(df)\n    if is_mobile_client():\n        return\n    st.markdown("#### Modifica importi, pagamenti e note")\n'
    )

    # Refresh and close client card after saving.
    text = text.replace(
        '''        if ok:
            save_data(data, sha, "Update client record")
            st.success(msg)
            st.rerun()
''',
        '''        if ok:
            save_data(data, sha, "Update client record")
            if str(prefix).startswith("archivio"):
                st.session_state["archive_nonce"] = int(st.session_state.get("archive_nonce", 0)) + 1
            if str(prefix).startswith("clienti"):
                st.session_state["client_nonce"] = int(st.session_state.get("client_nonce", 0)) + 1
            st.session_state.pop("open_client_id", None)
            st.success(msg)
            st.rerun()
'''
    )

    if text != original:
        path.write_text(text, encoding="utf-8")


try:
    _patch_app_source()
except Exception:
    pass
