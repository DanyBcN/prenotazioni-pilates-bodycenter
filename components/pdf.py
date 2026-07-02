from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd

from config import LOGO_PATH

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
except Exception:
    colors = None
    A4 = landscape = getSampleStyleSheet = cm = SimpleDocTemplate = Paragraph = Spacer = Table = TableStyle = Image = None

def pdf_bytes(title: str, df: pd.DataFrame) -> bytes:
    if SimpleDocTemplate is None:
        return simple_pdf_bytes(title, df)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=1 * cm, leftMargin=1 * cm, topMargin=1 * cm, bottomMargin=1 * cm)
    styles = getSampleStyleSheet()
    story = []

    if Path(LOGO_PATH).exists():
        try:
            story.append(Image(LOGO_PATH, width=2.0 * cm, height=2.0 * cm))
        except Exception:
            pass

    story.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
    story.append(Paragraph(f"Generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]))
    story.append(Spacer(1, 0.3 * cm))

    show_df = df.copy()
    for col in show_df.columns:
        show_df[col] = show_df[col].astype(str)
    show_df = show_df.iloc[:120]
    data = [list(show_df.columns)] + show_df.values.tolist()

    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243142")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return buffer.getvalue()

def simple_pdf_bytes(title: str, df: pd.DataFrame) -> bytes:
    def clean(value):
        return str(value or "").replace("\\", "/").replace("(", "[").replace(")", "]")

    lines = [title, " | ".join(map(str, df.columns))]
    for _, row in df.head(70).iterrows():
        lines.append(" | ".join(clean(x) for x in row.tolist())[:130])

    y = 805
    chunks = []
    for i, line in enumerate(lines):
        font_size = 14 if i == 0 else 8
        chunks.append(f"BT /F1 {font_size} Tf 35 {y} Td ({clean(line)[:125]}) Tj ET")
        y -= 18 if i == 0 else 11
        if y < 30:
            break

    stream = "\n".join(chunks)
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
        "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        f"5 0 obj << /Length {len(stream.encode('latin-1', 'replace'))} >> stream\n{stream}\nendstream endobj",
    ]
    pdf = "%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf.encode("latin-1", "replace")))
        pdf += obj + "\n"
    xref = len(pdf.encode("latin-1", "replace"))
    pdf += "xref\n0 6\n0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n"
    pdf += f"trailer << /Root 1 0 R /Size 6 >>\nstartxref\n{xref}\n%%EOF"
    return pdf.encode("latin-1", "replace")
