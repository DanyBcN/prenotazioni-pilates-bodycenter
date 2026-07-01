import pandas as _pd
import streamlit as _st

_original_dataframe = _st.dataframe

def _txt_pdf_bytes(title, df):
    try:
        rows = df.astype(str).fillna("").values.tolist()
        cols = [str(c) for c in df.columns]
    except Exception:
        rows, cols = [], []
    lines = [title, " | ".join(cols)]
    for r in rows[:60]:
        lines.append(" | ".join(str(x) for x in r)[:120])
    y = 805
    chunks = []
    for i, line in enumerate(lines):
        safe = str(line).replace("(", "[").replace(")", "]").replace("\\", "/")
        size = 14 if i == 0 else 8
        chunks.append(f"BT /F1 {size} Tf 35 {y} Td ({safe[:115]}) Tj ET")
        y -= 18 if i == 0 else 12
        if y < 30:
            break
    stream = "\n".join(chunks)
    objs = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
        "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        f"5 0 obj << /Length {len(stream.encode('latin-1','replace'))} >> stream\n{stream}\nendstream endobj",
    ]
    pdf = "%PDF-1.4\n"
    offsets = [0]
    for obj in objs:
        offsets.append(len(pdf.encode('latin-1','replace')))
        pdf += obj + "\n"
    xref = len(pdf.encode('latin-1','replace'))
    pdf += "xref\n0 6\n0000000000 65535 f \n"
    for off in offsets[1:]:
        pdf += f"{off:010d} 00000 n \n"
    pdf += f"trailer << /Root 1 0 R /Size 6 >>\nstartxref\n{xref}\n%%EOF"
    return pdf.encode('latin-1','replace')


def _bodycenter_dataframe(data=None, *args, **kwargs):
    if isinstance(data, _pd.DataFrame) and not data.empty:
        cols = set(str(c) for c in data.columns)
        if {"Quando", "Istruttrice", "Cliente"}.issubset(cols):
            _st.download_button("Scarica PDF planning", data=_txt_pdf_bytes("Planning", data), file_name="planning.pdf", mime="application/pdf", key="pdf_planning_auto")
        elif {"Data", "Ora", "Cliente"}.issubset(cols):
            _st.download_button("Scarica PDF elenco", data=_txt_pdf_bytes("Elenco", data), file_name="elenco.pdf", mime="application/pdf", key="pdf_elenco_auto")
    return _original_dataframe(data, *args, **kwargs)

_st.dataframe = _bodycenter_dataframe
