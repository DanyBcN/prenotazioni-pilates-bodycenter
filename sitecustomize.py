from pathlib import Path

p = Path(__file__).with_name('app.py')
if p.exists():
    s = p.read_text(encoding='utf-8')
    if 'PDF_EXPORT_READY' not in s:
        fn = r'''
PDF_EXPORT_READY = True

def simple_pdf(title, rows):
    def clean(x):
        return str(x or '').replace('(', '[').replace(')', ']').replace('\\', '/')
    lines = [title, '']
    for b in rows[:70]:
        stato = 'OMAGGIO' if gift(b) else ('INCASSATO' if yes(b.get('paid')) else 'DA INCASSARE')
        lines.append(f"{dit(b.get('date'))}  {b.get('time','')}  {b.get('instructor','')}  {b.get('name','')}  {stato}")
    y = 805
    parts = []
    for i, line in enumerate(lines):
        size = 14 if i == 0 else 9
        parts.append(f"BT /F1 {size} Tf 35 {y} Td ({clean(line)[:115]}) Tj ET")
        y -= 18 if i == 0 else 12
        if y < 30:
            break
    stream = '\n'.join(parts)
    objs = [
        '1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj',
        '2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj',
        '3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj',
        '4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj',
        f"5 0 obj << /Length {len(stream.encode('latin-1','replace'))} >> stream\n{stream}\nendstream endobj"
    ]
    pdf = '%PDF-1.4\n'
    offsets = [0]
    for obj in objs:
        offsets.append(len(pdf.encode('latin-1','replace')))
        pdf += obj + '\n'
    xref = len(pdf.encode('latin-1','replace'))
    pdf += 'xref\n0 6\n0000000000 65535 f \n'
    for off in offsets[1:]:
        pdf += f'{off:010d} 00000 n \n'
    pdf += f'trailer << /Root 1 0 R /Size 6 >>\nstartxref\n{xref}\n%%EOF'
    return pdf.encode('latin-1','replace')
'''
        s = s.replace('def render_planning(data,sha):', fn + '\ndef render_planning(data,sha):', 1)
        s = s.replace('st.subheader("Planning 3 mesi")', 'st.subheader("Planning 3 mesi"); _pdf_scope=None if admin() else instr_user(); _pdf_rows=planning_rows(data,PLANNING_DAYS,_pdf_scope); st.download_button("Scarica PDF planning",data=simple_pdf("Planning 3 mesi",_pdf_rows),file_name="planning_3_mesi.pdf",mime="application/pdf")', 1)
        p.write_text(s, encoding='utf-8')
