from pathlib import Path
import re


def _patch_print_personal_planning():
    p = Path(__file__).with_name("app.py")
    if not p.exists():
        return
    s = p.read_text(encoding="utf-8")
    if "def personal_planning_print_html(" in s:
        return

    helper = r'''

def personal_planning_print_html(data, instr, days=14):
    rows = _planning_base_rows(data, days, instr)
    quota_istr = sum(money(b.get("amount", 0)) * instructor_share() for b in rows)
    quota_pal = sum(money(b.get("amount", 0)) * gym_share() for b in rows)
    paid_quota = sum(money(b.get("amount", 0)) * instructor_share() for b in rows if to_bool(b.get("paid", False)))
    unpaid_quota = quota_istr - paid_quota
    today = date.today()
    all_days = [(today + timedelta(days=i)).isoformat() for i in range(days)]
    by_day = {d: [] for d in all_days}
    for r in rows:
        by_day.setdefault(r.get("date", ""), []).append(r)

    parts = []
    parts.append("<html><head><meta charset='utf-8'><title>Planning personale</title>")
    parts.append("<style>body{font-family:Arial,sans-serif;color:#172033;margin:24px}h1{font-size:22px}h2{font-size:17px;margin-top:18px}.summary{display:flex;gap:12px;margin:14px 0}.box{border:1px solid #ddd;border-radius:8px;padding:10px 14px}.box b{display:block;font-size:18px;margin-top:4px}table{width:100%;border-collapse:collapse;margin-top:6px}th,td{border-bottom:1px solid #e5e5e5;padding:6px;text-align:left;font-size:12px}th{background:#f5f5f5}.day{page-break-inside:avoid}.muted{color:#666;font-size:12px}@media print{button{display:none}body{margin:12mm}}</style>")
    parts.append("</head><body><button onclick='window.print()'>Stampa</button>")
    parts.append(f"<h1>Planning personale { _h(instr) }</h1>")
    parts.append(f"<div class='muted'>Periodo: {date_it(all_days[0])} - {date_it(all_days[-1])}</div>")
    parts.append("<div class='summary'>")
    parts.append(f"<div class='box'>Mio incasso 40%<b>€ {quota_istr:.2f}</b></div>")
    parts.append(f"<div class='box'>Quota palestra 60%<b>€ {quota_pal:.2f}</b></div>")
    parts.append(f"<div class='box'>Mio già pagato<b>€ {paid_quota:.2f}</b></div>")
    parts.append(f"<div class='box'>Mio da incassare<b>€ {unpaid_quota:.2f}</b></div>")
    parts.append("</div>")
    for d in all_days:
        day_rows = by_day.get(d, [])
        parts.append(f"<div class='day'><h2>{_h(date_label_it(d))}</h2>")
        if not day_rows:
            parts.append("<div class='muted'>Nessuna prenotazione</div></div>")
            continue
        parts.append("<table><thead><tr><th>Ora</th><th>Cliente</th><th>Telefono</th><th>Pagato</th><th>Quota 40%</th><th>Quota palestra 60%</th><th>Note</th></tr></thead><tbody>")
        for b in sorted(day_rows, key=lambda x: (str(x.get("time", "")), str(x.get("name", "")))):
            amount = money(b.get("amount", 0))
            parts.append("<tr>" +
                f"<td>{_h(b.get('time',''))}</td>" +
                f"<td>{_h(b.get('name',''))}</td>" +
                f"<td>{_h(b.get('phone',''))}</td>" +
                f"<td>{'Sì' if to_bool(b.get('paid', False)) else 'No'}</td>" +
                f"<td>€ {amount * instructor_share():.2f}</td>" +
                f"<td>€ {amount * gym_share():.2f}</td>" +
                f"<td>{_h(b.get('note',''))}</td>" +
                "</tr>")
        parts.append("</tbody></table></div>")
    parts.append("</body></html>")
    return "".join(parts)


def render_personal_planning_download(data, instr, days=14):
    if not instr:
        return
    html = personal_planning_print_html(data, instr, days)
    st.download_button(
        "Scarica / stampa planning personale",
        data=html.encode("utf-8"),
        file_name=f"planning_{instr.lower()}_14_giorni.html",
        mime="text/html",
        use_container_width=is_mobile_client(),
        key=f"download_planning_{instr}",
    )
'''

    boot = "\n\n# -----------------------------\n# App bootstrap"
    if "def render_planning(" in s:
        insert_at = s.index("\n\ndef render_planning(")
        s = s[:insert_at] + helper + s[insert_at:]

    old = '''    with tab_miei:
        _render_planning_view(data, _planning_base_rows(data, giorni, instr), f"Prossimi impegni {instr}", giorni)
    with tab_tutti:'''
    new = '''    with tab_miei:
        render_personal_planning_download(data, instr, giorni)
        _render_planning_view(data, _planning_base_rows(data, giorni, instr), f"Prossimi impegni {instr}", giorni)
    with tab_tutti:'''
    if old in s:
        s = s.replace(old, new, 1)
    else:
        s = re.sub(r'(with tab_miei:\n\s*)_render_planning_view\(data, _planning_base_rows\(data, giorni, instr\), f"Prossimi impegni \{instr\}", giorni\)', r'\1render_personal_planning_download(data, instr, giorni)\n        _render_planning_view(data, _planning_base_rows(data, giorni, instr), f"Prossimi impegni {instr}", giorni)', s, count=1)

    p.write_text(s, encoding="utf-8")


try:
    _patch_print_personal_planning()
except Exception:
    pass
