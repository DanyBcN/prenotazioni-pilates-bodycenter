from pathlib import Path
import re


def _rf(src, name, repl):
    m = re.search(rf"(^|\n)def {name}\([^\n]*\):\n.*?(?=\n\ndef |\n\n# -----------------------------|\Z)", src, re.S)
    if not m:
        return src
    return src[:m.start()] + ("\n" if m.group(1) else "") + repl.rstrip() + src[m.end():]


def _patch_cash_workflow_visibility():
    p = Path(__file__).with_name("app.py")
    if not p.exists():
        return
    s = p.read_text(encoding="utf-8")

    repl = '''def render_cash_workflow(data, sha, compact=False):
    instr = None if is_admin() else instructor_name_from_user()
    rows = open_cash_rows(data, instr)
    pay_rows = [b for b in rows if not is_gift_booking(b)]
    gift_rows = [b for b in rows if is_gift_booking(b)]
    da_incassare = [b for b in pay_rows if not to_bool(b.get("paid", False))]
    incassati_palestra = [b for b in pay_rows if to_bool(b.get("paid", False))]
    totale = sum(money(b.get("amount", 0)) for b in pay_rows)
    da_incassare_tot = sum(money(b.get("amount", 0)) for b in da_incassare)
    incassato = sum(money(b.get("amount", 0)) for b in incassati_palestra)
    quota_da_pagare = incassato * instructor_share()

    st.markdown("### Gestione incassi")
    a, b, c, d = st.columns(4)
    a.metric("Incasso totale", f"€ {totale:.2f}")
    b.metric("Da incassare", f"€ {da_incassare_tot:.2f}")
    c.metric("Incassato dalla palestra", f"€ {incassato:.2f}")
    d.metric("Sedute omaggio", len(gift_rows))
    st.caption("Quando segni un pagamento come incassato, non sparisce: passa sotto 'Incassati dalla palestra' e poi nella quota 40% da pagare/ricevere.")

    st.markdown("#### 1. Da incassare")
    if da_incassare:
        st.dataframe(_cash_df(da_incassare), use_container_width=True, hide_index=True)
        i = st.selectbox("Seleziona pagamento incassato dalla palestra", range(len(da_incassare)), format_func=lambda k: _pay_label(da_incassare[k]), key="cash_collect_select")
        if st.button("Segna come incassato dalla palestra", key="cash_collect_btn", use_container_width=is_mobile_client()):
            ok, msg = mark_gym_collected(data, da_incassare[i].get("id"))
            if ok:
                save_data(data, sha, "Mark gym cash collected")
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    else:
        st.success("Nessun importo da incassare. Gli incassi già segnati restano visibili qui sotto.")

    st.markdown("#### 2. Incassati dalla palestra")
    if incassati_palestra:
        st.metric("Totale incassato dalla palestra", f"€ {incassato:.2f}")
        st.dataframe(_cash_df(incassati_palestra), use_container_width=True, hide_index=True)
    else:
        st.info("Nessun incasso ancora registrato dalla palestra.")

    st.markdown("#### 3. Quota 40% da pagare/ricevere")
    if incassati_palestra:
        label = "Totale quota 40% da pagare" if is_admin() else "Totale quota 40% da ricevere"
        button_label = "Segna quota 40% pagata ad Alice/Grazia" if is_admin() else "Segna quota 40% ricevuta"
        st.metric(label, f"€ {quota_da_pagare:.2f}")
        st.dataframe(_cash_df(incassati_palestra), use_container_width=True, hide_index=True)
        i = st.selectbox("Seleziona quota 40%", range(len(incassati_palestra)), format_func=lambda k: _pay_label(incassati_palestra[k]) + f" · quota € {money(incassati_palestra[k].get('amount',0))*instructor_share():.2f}", key="share_received_select")
        if st.button(button_label, key="share_received_btn", use_container_width=is_mobile_client()):
            ok, msg = mark_share_paid_or_received(data, incassati_palestra[i].get("id"))
            if ok:
                save_data(data, sha, "Mark instructor share paid")
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
    else:
        st.info("Nessuna quota da pagare/ricevere: prima il pagamento deve essere incassato dalla palestra.")

    st.markdown("#### 4. Sedute omaggio")
    if gift_rows:
        st.dataframe(_cash_df(gift_rows), use_container_width=True, hide_index=True)
    else:
        st.info("Nessuna seduta omaggio registrata.")'''

    s2 = _rf(s, "render_cash_workflow", repl)
    if s2 != s:
        p.write_text(s2, encoding="utf-8")


try:
    _patch_cash_workflow_visibility()
except Exception:
    pass
