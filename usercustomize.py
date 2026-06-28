from pathlib import Path
import re


def _patch_instructor_personal_planning_names():
    p = Path(__file__).with_name("app.py")
    if not p.exists():
        return
    s = p.read_text(encoding="utf-8")

    # Nel Planning personale dell'istruttrice non ripete il nome dell'istruttrice
    old = '_render_planning_view(data, _planning_base_rows(data, giorni, instr), f"Prossimi impegni {instr}", giorni)'
    new = '_render_planning_view(data, [dict(x, instructor="") for x in _planning_base_rows(data, giorni, instr)], f"Prossimi impegni {instr}", giorni)'
    if old in s:
        s = s.replace(old, new, 1)

    # Pulizia estetica: se lo span istruttrice è vuoto, non lascia spazio evidente.
    s = s.replace('<span>{_h(instr)}</span> <em>', '<span>{_h(instr)}</span><em>')
    s = s.replace('<b>{_h(t)}</b> <span>', '<b>{_h(t)}</b> <span>')

    p.write_text(s, encoding="utf-8")


try:
    _patch_instructor_personal_planning_names()
except Exception:
    pass
