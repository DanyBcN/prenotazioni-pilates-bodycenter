from pathlib import Path
import re


def _replace(text, old, new):
    return text.replace(old, new) if old in text else text


def _patch_app_source():
    path = Path(__file__).with_name("app.py")
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8")
    original = text

    # Required client fields.
    text = _replace(
        text,
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

    # JsCode is needed for chronological sorting of the pretty date column.
    text = _replace(
        text,
        "from st_aggrid import AgGrid, DataReturnMode, GridOptionsBuilder, GridUpdateMode",
        "from st_aggrid import AgGrid, DataReturnMode, GridOptionsBuilder, GridUpdateMode, JsCode",
    )

    # Better header.
    text = _replace(
        text,
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

    # Responsive CSS: PC table, mobile cards.
    css_marker = '''    .stApp {{ background: #fbfcfb; }}
'''
    css_insert = '''    .stApp {{ background: #fbfcfb; }}
    .block-container {{ padding-top:1rem !important; max-width:1240px !important; }}
    div[data-testid="stRadio"] > div {{ gap:.65rem !important; flex-wrap:wrap !important; }}
    div[data-testid="stRadio"] label {{ min-height:42px !important; padding:.55rem 1rem !important; border-radius:999px !important; border:1px solid #dce6dc !important; background:#fff !important; box-shadow:0 3px 10px rgba(36,49,66,.045) !important; }}
    div[data-testid="stRadio"] input[type="radio"] {{ display:none !important; }}
    div[data-testid="stRadio"] label:has(input:checked) {{ background:#496744 !important; border-color:#496744 !important; }}
    div[data-testid="stRadio"] label:has(input:checked) p {{ color:#fff !important; }}
    .mobile-archive {{ display:none !important; }}
    @media (max-width:760px) {{
        .block-container {{ padding-left:.55rem !important; padding-right:.55rem !important; max-width:100% !important; }}
        .mobile-archive {{ display:block !important; }}
        div[data-testid="stCustomComponentV1"], .ag-root-wrapper, .ag-theme-streamlit {{ display:none !important; }}
    }}
    @media (min-width:761px) {{
        .mobile-archive {{ display:none !important; }}
    }}
'''
    if ".mobile-archive" not in text and css_marker in text:
        text = text.replace(css_marker, css_insert)

    # Archive: remove audit column and sort rows by client surname/name by default.
    text = text.replace(', "Inserita il", "ID", "Client ID"', ', "ID", "Client ID"')
    text = text.replace(', "Inserita il", "ID", "Client ID"]', ', "ID", "Client ID"]')
    text = text.replace(', "Inserita il": b.get("created_at")', '')
    text = text.replace('    gb.configure_column("Inserita il", editable=False, width=170, cellStyle=cell_style("center"))\n', '')
    text = text.replace('    gb.configure_column("Inserita il", editable=False, width=168, cellStyle=cell_style("center"))\n', '')
    text = text.replace(
        'return df.sort_values(["_sort", "Ora", "Cliente"]).drop(columns=["_sort"]).reset_index(drop=True)',
        'return df.sort_values(["Cliente", "_sort", "Ora"]).drop(columns=["_sort"]).reset_index(drop=True)',
    )

    # Force AgGrid itself to open sorted by Cliente on PC.
    text = text.replace(
        '    gb.configure_column("Cliente", editable=False, width=230, pinned="left", cellStyle=cell_style("left", bold=True, color="#1f5c8f"))\n',
        '    gb.configure_column("Cliente", editable=False, width=230, pinned="left", sort="asc", sortIndex=0, cellStyle=cell_style("left", bold=True, color="#1f5c8f"))\n'
    )
    text = text.replace(
        '    gb.configure_column("Cliente", editable=False, width=230, pinned="left", sort="asc", sortIndex=0, cellStyle=cell_style("left", bold=True, color="#1f5c8f"))\n',
        '    gb.configure_column("Cliente", editable=False, width=230, pinned="left", sort="asc", sortIndex=0, cellStyle=cell_style("left", bold=True, color="#1f5c8f"))\n'
    )

    # Sort Data by hidden ISO value when the user clicks the column.
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

    # PDF with revenue summary.
    new_make_pdf = '''def make_pdf(df, label=""):
    bio = BytesIO()
    doc = SimpleDocTemplate(bio, pagesize=landscape(A4), rightMargin=.6*cm, leftMargin=.6*cm, topMargin=.7*cm, bottomMargin=.7*cm)
    styles = getSampleStyleSheet()
    elems = []
    if Path(LOGO_PATH).exists():
        elems.append(Image(LOGO_PATH, width=2.0*cm, height=3.0*cm))
    elems += [Paragraph("Archivio prenotazioni Pilates - Body Center", styles["Title"]), Paragraph(label, styles["Normal"]), Spacer(1, .25*cm)]

    w = df.copy() if not df.empty else pd.DataFrame(columns=["Istruttrice", "Stato", "Importo", "Pagato"])
    if not w.empty:
        w["Importo"] = pd.to_numeric(w.get("Importo", 0), errors="coerce").fillna(0)
        w["Pagato_bool"] = w.get("Pagato", False).apply(to_bool)
        w = w[w.get("Stato", "") != "Annullata"]
    total = float(w["Importo"].sum()) if not w.empty else 0.0
    paid = float(w.loc[w["Pagato_bool"] == True, "Importo"].sum()) if not w.empty and "Pagato_bool" in w else 0.0
    unpaid = total - paid

    incassi = [["Riepilogo incassi", "Importo"], ["Totale complessivo", f"€ {total:.2f}"], ["Totale pagato", f"€ {paid:.2f}"], ["Totale non pagato", f"€ {unpaid:.2f}"]]
    inc_tab = Table(incassi, colWidths=[6*cm, 4*cm])
    inc_tab.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor(GREEN)), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .25, colors.lightgrey), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold")]))
    elems += [inc_tab, Spacer(1, .25*cm)]

    per_rows = [["Istruttrice", "Totale complessivo", "Totale pagato", "Totale non pagato"]]
    for istr in INSTRUCTORS:
        s = w[w.get("Istruttrice", "") == istr] if not w.empty else w
        it = float(s["Importo"].sum()) if not s.empty else 0.0
        ip = float(s.loc[s["Pagato_bool"] == True, "Importo"].sum()) if not s.empty and "Pagato_bool" in s else 0.0
        per_rows.append([istr, f"€ {it:.2f}", f"€ {ip:.2f}", f"€ {it - ip:.2f}"])
    per_tab = Table(per_rows, colWidths=[4*cm, 4*cm, 4*cm, 4*cm])
    per_tab.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#6f8f68")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .25, colors.lightgrey), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold")]))
    elems += [per_tab, Spacer(1, .35*cm)]

    cols = ["Data", "Ora", "Cliente", "Telefono", "Email", "Istruttrice", "Stato", "Importo", "Pagato", "Note cliente"]
    pdf = df[cols].copy() if not df.empty else pd.DataFrame(columns=cols)
    pdf["Pagato"] = pdf["Pagato"].map(lambda x: "Sì" if to_bool(x) else "No")
    pdf["Importo"] = pdf["Importo"].map(lambda x: f"€ {money(x):.2f}")
    data = [cols] + pdf.fillna("").astype(str).values.tolist()
    tab = Table(data, repeatRows=1)
    tab.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor(GREEN)), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .25, colors.lightgrey), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold")]))
    elems.append(tab)
    doc.build(elems)
    bio.seek(0)
    return bio.getvalue()
'''
    text = re.sub(r'def make_pdf\(df, label=""\):\n.*?\n\ndef app_css\(\):', new_make_pdf + '\n\ndef app_css():', text, flags=re.S)

    # Refresh and close client card after saving.
    text = _replace(
        text,
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
    text = _replace(text, '    selected = client_grid(view, "client_grid")\n', '    selected = client_grid(view, f"client_grid_{st.session_state.get(\'client_nonce\', 0)}")\n')
    text = _replace(
        text,
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

    # Mobile archive helpers.
    mobile_helpers = '''

def is_mobile_client():
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
    marker = '\n\ndef render_archive(data, sha):\n'
    if 'def is_mobile_client(' not in text:
        text = text.replace(marker, mobile_helpers + marker)

    insert_marker = '    st.markdown("#### Modifica importi, pagamenti e note")\n'
    text = text.replace('    archive_mobile_html(df)\n    if is_mobile_client():\n        return\n', '')
    text = text.replace('    archive_mobile_html(df)\n', '')
    text = text.replace(insert_marker, '    archive_mobile_html(df)\n    if is_mobile_client():\n        return\n' + insert_marker)

    if text != original:
        path.write_text(text, encoding="utf-8")


try:
    _patch_app_source()
except Exception:
    pass
