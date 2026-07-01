import base64, json, os, re
from datetime import date, datetime, timedelta
from pathlib import Path
import pandas as pd
import requests
import streamlit as st

APP_TITLE="Prenotazioni Pilates Reformer"
DATA_PATH="data/bookings.json"
LOGO_PATH="assets/logo.png"
INSTRUCTORS=["Grazia","Alice"]
CAPACITY=4
PLANNING_DAYS=92
SCHEDULE={0:["08:30","09:30","10:30","17:00","18:00","19:00"],1:["09:30","10:30","11:30","12:45","14:30","19:00"],2:["08:30","09:30","10:30","11:30","12:45","14:30","15:30","16:30","17:30","18:30"],3:["17:00","18:00","19:00"],4:["14:00","15:00","16:00","17:00","18:00","19:00"]}
DAY={0:"Lun",1:"Mar",2:"Mer",3:"Gio",4:"Ven",5:"Sab",6:"Dom"}
MONTH={1:"gennaio",2:"febbraio",3:"marzo",4:"aprile",5:"maggio",6:"giugno",7:"luglio",8:"agosto",9:"settembre",10:"ottobre",11:"novembre",12:"dicembre"}


def sec(k,d=""):
    try: return str(st.secrets.get(k,d))
    except Exception: return os.environ.get(k,d)

def gh_on(): return bool(sec("GITHUB_TOKEN") and sec("GITHUB_REPO") and sec("GITHUB_BRANCH","main"))
def gh_url(): return f"https://api.github.com/repos/{sec('GITHUB_REPO')}/contents/{DATA_PATH}"
def gh_headers(): return {"Authorization":"token "+sec("GITHUB_TOKEN"),"Accept":"application/vnd.github+json"}

def parse_date(v):
    if isinstance(v,date): return v
    s=str(v or "").strip()
    for f in ("%Y-%m-%d","%d/%m/%Y","%d-%m-%Y"):
        try: return datetime.strptime(s,f).date()
        except Exception: pass
    return pd.to_datetime(s,dayfirst=True).date()

def dkey(d): return parse_date(d).isoformat()
def dit(v):
    try: return parse_date(v).strftime("%d-%m-%Y")
    except Exception: return ""
def dlabel(v):
    try:
        d=parse_date(v); return f"{DAY[d.weekday()]} {d.day} {MONTH[d.month]} {str(d.year)[-2:]}"
    except Exception: return str(v or "")
def money(x):
    try: return round(float(x or 0),2)
    except Exception: return 0.0
def yes(x): return x if isinstance(x,bool) else str(x).strip().lower() in {"true","1","sì","si","yes","y"}
def nid(p=""): return p+datetime.now().strftime("%Y%m%d%H%M%S%f")
def norm(x): return re.sub(r"\s+"," ",str(x or "").strip().lower())
def cname(c): return f"{c.get('last_name','').strip()} {c.get('first_name','').strip()}".strip() if c else ""
def ckey(first,last): return f"{norm(first)}|{norm(last)}"
def split_name(n):
    p=str(n or "").split()
    return (" ".join(p[1:]),p[0]) if len(p)>1 else ((p[0],"") if p else ("",""))
def gift(b): return bool(b.get("gift",False)) or "omaggio" in str(b.get("note","")).lower()
def share():
    try: return float(sec("INSTRUCTOR_SHARE","0.40"))
    except Exception: return 0.40
def gym_share():
    try: return float(sec("GYM_SHARE","0.60"))
    except Exception: return 0.60


def users():
    raw=sec("USERS","").strip()
    if raw:
        try: return {str(k).lower().strip():v for k,v in json.loads(raw).items() if isinstance(v,dict)}
        except Exception as e: st.error(f"USERS non valido: {e}"); st.stop()
    return {"bodycenter":{"password":sec("APP_PASSWORD","pilates123"),"role":"admin"}}
def user(): return st.session_state.get("current_user","bodycenter")
def admin(): return st.session_state.get("current_role","admin")=="admin"
def instr_user():
    u=user().lower().strip()
    return next((x for x in INSTRUCTORS if x.lower()==u),"")
def pages(): return ["Planning","Prenota","Incassi","Clienti","Cerca","Archivio"] if admin() else ["Planning","Prenota","Incassi","Clienti"]
def go(p): st.session_state["_next_section"]=p; st.rerun()


def load():
    if st.session_state.get("_fresh_data") is not None:
        return st.session_state.pop("_fresh_data"), st.session_state.pop("_fresh_sha",None)
    if gh_on():
        r=requests.get(gh_url(),headers=gh_headers(),params={"ref":sec("GITHUB_BRANCH","main")},timeout=20)
        if r.status_code==404:
            data={"bookings":[],"clients":[],"settlements":[]}; save(data,None,"Initialize storage"); return data,None
        r.raise_for_status(); p=r.json(); return json.loads(base64.b64decode(p["content"]).decode()), p.get("sha")
    path=Path(DATA_PATH)
    if not path.exists(): path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps({"bookings":[],"clients":[],"settlements":[]},ensure_ascii=False,indent=2),encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8")), None

def save(data,sha=None,msg="Update data"):
    if gh_on():
        body={"message":msg,"content":base64.b64encode(json.dumps(data,ensure_ascii=False,indent=2).encode()).decode(),"branch":sec("GITHUB_BRANCH","main")}
        if sha: body["sha"]=sha
        r=requests.put(gh_url(),headers=gh_headers(),json=body,timeout=20); r.raise_for_status()
        st.session_state["_fresh_data"]=data
        try: st.session_state["_fresh_sha"]=r.json().get("content",{}).get("sha")
        except Exception: st.session_state["_fresh_sha"]=None
    else:
        Path(DATA_PATH).parent.mkdir(parents=True,exist_ok=True); Path(DATA_PATH).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")


def ensure(data):
    data.setdefault("bookings",[]); data.setdefault("clients",[]); data.setdefault("settlements",[])
    for c in data["clients"]:
        c.setdefault("id",nid("c_")); c.setdefault("first_name",""); c.setdefault("last_name",""); c.setdefault("phone",""); c.setdefault("email",""); c.setdefault("notes",""); c.setdefault("birth_date","")
    keys={ckey(c.get("first_name",""),c.get("last_name","")):c for c in data["clients"]}
    for b in data["bookings"]:
        b.setdefault("id",nid("b_")); b.setdefault("amount",0); b.setdefault("paid",False); b.setdefault("gift",False); b.setdefault("status","Confermata"); b.setdefault("settlement_id",""); b.setdefault("date",date.today().isoformat()); b.setdefault("time",""); b.setdefault("note",""); b.setdefault("instructor","")
        if not b.get("client_id"):
            f,l=split_name(b.get("name","")); k=ckey(f,l)
            if k.strip("|") in keys: b["client_id"]=keys[k]["id"]
            elif k.strip("|"):
                c={"id":nid("c_"),"first_name":f,"last_name":l,"phone":b.get("phone",""),"email":b.get("email",""),"notes":"","birth_date":""}; data["clients"].append(c); keys[k]=c; b["client_id"]=c["id"]
    return data


def get_client(data,cid): return next((c for c in data.get("clients",[]) if c.get("id")==cid),None)
def client_opts(data): return sorted([f"{cname(c)} | {c.get('phone','')} | {c.get('email','')} | {c.get('id')}" for c in data.get("clients",[])],key=str.lower)
def opt_id(o): return o.split("|")[-1].strip()

def add_client(data,first,last,phone,email="",notes="",birth=""):
    if not first.strip() or not last.strip() or not phone.strip(): return False,"Inserisci cognome, nome e telefono.",None
    k=ckey(first,last)
    for c in data["clients"]:
        if ckey(c.get("first_name",""),c.get("last_name",""))==k: return False,"Cliente già presente.",c.get("id")
    cid=nid("c_"); data["clients"].append({"id":cid,"first_name":first.strip(),"last_name":last.strip(),"phone":phone.strip(),"email":email.strip(),"notes":notes.strip(),"birth_date":birth.strip()}); return True,"Cliente salvato.",cid

def update_client(data,cid,first,last,phone,email,birth,notes):
    c=get_client(data,cid)
    if not c: return False,"Cliente non trovato."
    c.update({"first_name":first.strip(),"last_name":last.strip(),"phone":phone.strip(),"email":email.strip(),"birth_date":birth.strip(),"notes":notes.strip()})
    for b in data["bookings"]:
        if b.get("client_id")==cid: b["name"]=cname(c); b["phone"]=c.get("phone",""); b["email"]=c.get("email","")
    return True,"Scheda aggiornata."


def confirmed(data,d,t,instructor=None,exclude=None):
    return sum(1 for b in data["bookings"] if b.get("status")=="Confermata" and b.get("date")==dkey(d) and b.get("time")==t and b.get("id")!=exclude and (not instructor or b.get("instructor")==instructor))
def auto_status(data,d,t,instructor): return "Confermata" if confirmed(data,d,t,instructor)<CAPACITY else "Lista attesa"

def create_booking(data,cid,d,t,amount,paid,instructor,note,gift_flag=False):
    c=get_client(data,cid)
    amount=0.0 if gift_flag else money(amount); paid=True if gift_flag else bool(paid)
    clean=note.strip()
    if gift_flag and "omaggio" not in clean.lower(): clean=(clean+" | " if clean else "")+"Seduta omaggio / prova"
    b={"id":nid("b_"),"created_at":datetime.now().isoformat(timespec="seconds"),"client_id":cid,"date":dkey(d),"time":t,"day":DAY[parse_date(d).weekday()],"name":cname(c),"phone":c.get("phone",""),"email":c.get("email",""),"note":clean,"status":auto_status(data,d,t,instructor),"amount":amount,"paid":paid,"gift":bool(gift_flag),"paid_to_gym_at":datetime.now().isoformat(timespec="seconds") if paid and not gift_flag else "","paid_to_gym_by":user() if paid and not gift_flag else "","settlement_id":"","instructor":instructor,"created_by":user()}
    data["bookings"].append(b); return b

def open_rows(data,instructor=None): return [b for b in data["bookings"] if b.get("status")!="Annullata" and not b.get("settlement_id") and (not instructor or b.get("instructor")==instructor)]
def mark_paid(data,bid):
    for b in data["bookings"]:
        if b.get("id")==bid and not gift(b): b["paid"]=True; b["paid_to_gym_at"]=datetime.now().isoformat(timespec="seconds"); b["paid_to_gym_by"]=user(); return True,"Incassato."
    return False,"Prenotazione non trovata o omaggio."
def mark_gift(data,bid,note=""):
    for b in data["bookings"]:
        if b.get("id")==bid:
            if b.get("settlement_id"): return False,"Quota già chiusa."
            b.update({"gift":True,"amount":0.0,"paid":True,"paid_to_gym_at":"","paid_to_gym_by":user()})
            if "omaggio" not in str(b.get("note","")).lower(): b["note"]=(b.get("note","")+" | " if b.get("note") else "")+("Seduta omaggio / prova"+(f" - {note}" if note else ""))
            return True,"Segnata come omaggio."
    return False,"Prenotazione non trovata."
def unmark_gift(data,bid,amount,paid,note=""):
    for b in data["bookings"]:
        if b.get("id")==bid:
            b.update({"gift":False,"amount":money(amount),"paid":bool(paid),"paid_to_gym_at":datetime.now().isoformat(timespec="seconds") if paid else "","paid_to_gym_by":user() if paid else ""}); return True,"Omaggio tolto."
    return False,"Prenotazione non trovata."
def update_amount(data,bid,amount,note=""):
    for b in data["bookings"]:
        if b.get("id")==bid:
            if b.get("settlement_id"): return False,"Quota già chiusa."
            if gift(b): return False,"Togli prima omaggio."
            old=money(b.get("amount")); b["amount"]=money(amount); b["amount_updated_at"]=datetime.now().isoformat(timespec="seconds"); b["amount_updated_by"]=user()
            if note.strip(): b["note"]=(b.get("note","")+" | " if b.get("note") else "")+f"Importo {old:.2f}->{money(amount):.2f} - {note.strip()}"
            return True,"Importo aggiornato."
    return False,"Prenotazione non trovata."
def mark_share(data,bid):
    for b in data["bookings"]:
        if b.get("id")==bid:
            if gift(b): return False,"Omaggio: nessuna quota."
            if not yes(b.get("paid")): return False,"Prima registra incasso."
            amount=money(b.get("amount")); sid=nid("sett_"); b["settlement_id"]=sid; b["share_paid_at"]=datetime.now().isoformat(timespec="seconds"); b["share_paid_by"]=user()
            data.setdefault("settlements",[]).append({"id":sid,"created_at":b["share_paid_at"],"instructor":b.get("instructor",""),"gross_amount":amount,"instructor_amount":round(amount*share(),2),"gym_amount":round(amount*gym_share(),2),"lessons":1,"closed_by":user(),"booking_id":bid}); return True,"Quota chiusa."
    return False,"Prenotazione non trovata."
def cancel_booking(data,bid,note=""):
    for b in data["bookings"]:
        if b.get("id")==bid: b["status"]="Annullata"; b["cancelled_at"]=datetime.now().isoformat(timespec="seconds"); b["cancelled_by"]=user(); return True,"Prenotazione annullata."
    return False,"Prenotazione non trovata."

def row_label(b): return f"{dit(b.get('date'))} · {b.get('time','')} · {b.get('instructor','')} · {b.get('name','')}"+(" · OMAGGIO" if gift(b) else f" · € {money(b.get('amount')):.2f}")
def df_rows(rows): return pd.DataFrame([{"Data":dit(x.get("date")),"Ora":x.get("time",""),"Istruttrice":x.get("instructor",""),"Cliente":x.get("name",""),"Tipo":"Omaggio" if gift(x) else "Pagamento","Importo":money(x.get("amount")),"Incassato":"Omaggio" if gift(x) else ("Sì" if yes(x.get("paid")) else "No"),"Quota 40%":0.0 if gift(x) else round(money(x.get("amount"))*share(),2),"Note":x.get("note","")} for x in rows])


def header():
    st.set_page_config(page_title=APP_TITLE,layout="wide")
    st.markdown("<style>.main .block-container{max-width:1350px;padding-top:1rem}.bc-title{font-size:38px;font-weight:800;color:#243142}</style>",unsafe_allow_html=True)
    logo=""
    if Path(LOGO_PATH).exists(): logo=f"<img src='data:image/png;base64,{base64.b64encode(Path(LOGO_PATH).read_bytes()).decode()}' style='width:86px;vertical-align:middle;margin-right:18px'>"
    st.markdown(f"<div>{logo}<span class='bc-title'>{APP_TITLE}</span></div>",unsafe_allow_html=True)

def login():
    if st.session_state.get("authenticated"): return True
    uconf=users(); _,c,_=st.columns([1.3,1.1,1.3])
    with c:
        st.markdown("### Accesso staff"); u=st.selectbox("Utente",list(uconf.keys())); p=st.text_input("Password",type="password")
        if st.button("Accedi",type="primary",use_container_width=True):
            cfg=uconf.get(str(u).lower().strip(),{})
            if p and p==str(cfg.get("password","")): st.session_state["authenticated"]=True; st.session_state["current_user"]=str(u).lower().strip(); st.session_state["current_role"]=str(cfg.get("role","instructor")).lower().strip(); go("Planning")
            else: st.error("Utente o password non corretti")
    return False


def render_booking(data,sha):
    st.subheader("Prenota")
    mode=st.radio("Cliente",["Seleziona da archivio","Nuovo cliente"],horizontal=True); cid=None
    if mode.startswith("Seleziona"):
        opts=client_opts(data)
        if opts: cid=opt_id(st.selectbox("Cliente",opts)); c=get_client(data,cid); st.caption(f"Telefono: {c.get('phone','')} · Email: {c.get('email','')}")
        else: st.warning("Nessun cliente.")
    else:
        a,b=st.columns(2); last=a.text_input("Cognome"); first=b.text_input("Nome"); c,d=st.columns(2); phone=c.text_input("Telefono"); email=d.text_input("Email"); birth=st.text_input("Data di nascita"); notes=st.text_area("Note cliente")
        if st.button("Salva nuovo cliente"): ok,msg,cid=add_client(data,first,last,phone,email,notes,birth); st.error(msg) if not ok else (save(data,sha,"Add client"),go("Prenota"))
    if cid:
        a,b=st.columns(2); d=parse_date(a.date_input("Data",value=date.today(),min_value=date.today(),format="DD/MM/YYYY")); ts=SCHEDULE.get(d.weekday(),[])
        if not ts: st.warning("Nessun orario previsto."); return
        t=b.selectbox("Orario",ts); default=instr_user(); idx=INSTRUCTORS.index(default) if default in INSTRUCTORS else 0
        a,b,c=st.columns(3); isom=a.checkbox("Seduta omaggio / prova gratuita"); amount=b.number_input("Importo (€)",min_value=0.0,value=0.0,step=1.0,format="%.2f",disabled=isom); paid=c.checkbox("Già incassato dalla palestra",disabled=isom)
        instr=st.selectbox("Istruttrice",INSTRUCTORS,index=idx); note=st.text_area("Note prenotazione")
        st.info(f"{instr} · {t}: {confirmed(data,d,t,instr)}/{CAPACITY} confermate · stato: {'Seduta omaggio' if isom else auto_status(data,d,t,instr)}")
        if st.button("Salva prenotazione",type="primary"): create_booking(data,cid,d,t,amount,paid,instr,note,isom); save(data,sha,"Add booking"); go("Planning")


def render_incassi(data,sha):
    instr=None if admin() else instr_user(); rows=open_rows(data,instr); pay=[b for b in rows if not gift(b)]; om=[b for b in rows if gift(b)]; unpaid=[b for b in pay if not yes(b.get("paid"))]; paid=[b for b in pay if yes(b.get("paid"))]
    collected=sum(money(b.get("amount")) for b in paid); quota=collected*share(); closed=sum(money(x.get("instructor_amount")) for x in data.get("settlements",[]) if not instr or x.get("instructor")==instr)
    st.subheader("Incassi"); a,b,c,d,e=st.columns(5); a.metric("Totale aperto",f"€ {sum(money(x.get('amount')) for x in pay):.2f}"); b.metric("Da incassare",f"€ {sum(money(x.get('amount')) for x in unpaid):.2f}"); c.metric("Incassato palestra",f"€ {collected:.2f}"); d.metric("Tuo 40% da ricevere" if not admin() else "40% da dare",f"€ {quota:.2f}"); e.metric("Omaggio",len(om)); st.info((f"Quota {instr_user()}: da ricevere € {quota:.2f} · già ricevuto € {closed:.2f}" if not admin() else f"Quote: da dare € {quota:.2f} · già pagate € {closed:.2f}"))
    allr=sorted(rows,key=lambda x:(x.get("date",""),x.get("time",""),x.get("name","")))
    st.markdown("### Azione unica")
    with st.container(border=True):
        if allr:
            i=st.selectbox("Prenotazione",range(len(allr)),format_func=lambda k:row_label(allr[k])); sel=allr[i]; bid=sel.get("id"); cur=gift(sel); x,y,z=st.columns(3); g=x.checkbox("Seduta omaggio / prova",value=cur,key=f"g{bid}"); amt=y.number_input("Importo totale (€)",0.0,value=(0.0 if g else float(money(sel.get("amount")))),step=1.0,disabled=g,key=f"a{bid}"); pdv=z.checkbox("Incassato palestra",value=(True if g else yes(sel.get("paid"))),disabled=g,key=f"p{bid}"); note=st.text_input("Nota opzionale",key=f"n{bid}")
            if st.button("Salva",type="primary",key=f"s{bid}"):
                ok,msg=(mark_gift(data,bid,note) if g else (unmark_gift(data,bid,amt,pdv,note) if cur else update_amount(data,bid,amt,note)))
                if ok and (not g) and pdv and not yes(sel.get("paid")): ok,msg=mark_paid(data,bid)
                if ok: save(data,sha,"Save incassi"); go("Incassi")
                else: st.error(msg)
        else: st.info("Nessuna prenotazione modificabile.")
    st.markdown("### Quota 40%")
    if paid:
        k=st.selectbox("Prenotazione quota",range(len(paid)),format_func=lambda j:row_label(paid[j])+f" · quota € {money(paid[j].get('amount'))*share():.2f}")
        if st.button("Segna quota 40% ricevuta/pagata"): ok,msg=mark_share(data,paid[k].get("id")); st.error(msg) if not ok else (save(data,sha,"Close share"),go("Incassi"))
    with st.expander("Da incassare",True): st.dataframe(df_rows(unpaid),use_container_width=True,hide_index=True) if unpaid else st.success("Nessun importo da incassare.")
    with st.expander("Incassati dalla palestra",True): st.dataframe(df_rows(paid),use_container_width=True,hide_index=True) if paid else st.info("Nessun incasso.")
    with st.expander("Sedute omaggio",True): st.dataframe(df_rows(om),use_container_width=True,hide_index=True) if om else st.info("Nessuna seduta omaggio.")


def planning_rows(data,days,instructor=None):
    today=date.today(); end=today+timedelta(days=days-1); out=[]
    for b in data["bookings"]:
        if b.get("status")=="Annullata" or (instructor and b.get("instructor")!=instructor): continue
        try: d=parse_date(b.get("date"))
        except Exception: continue
        if today<=d<=end: out.append(b)
    return sorted(out,key=lambda x:(x.get("date",""),x.get("time",""),x.get("instructor",""),x.get("name","")))
def esc(x): return str(x or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def plan_table(rows): return pd.DataFrame([{"Quando":f"{dlabel(b.get('date'))} · {b.get('time','')}","Istruttrice":b.get("instructor",""),"Cliente":b.get("name",""),"Telefono":b.get("phone",""),"Tipo":"Omaggio" if gift(b) else "Pagamento","Importo":money(b.get("amount")),"Incassato":"Omaggio" if gift(b) else ("Sì" if yes(b.get("paid")) else "No")} for b in rows])
def cancel_box(data,sha):
    rows=[b for b in data["bookings"] if b.get("status")!="Annullata" and not b.get("settlement_id") and parse_date(b.get("date"))>=date.today()]
    with st.expander("Annulla prenotazione",False):
        if not rows: st.info("Nessuna prenotazione futura annullabile."); return
        labs=[row_label(b) for b in rows]; lab=st.selectbox("Prenotazione",labs); note=st.text_input("Motivo / nota opzionale"); confirm=st.checkbox("Confermo l'annullamento")
        if st.button("Annulla prenotazione selezionata"):
            if not confirm: st.warning("Spunta la conferma."); return
            ok,msg=cancel_booking(data,rows[labs.index(lab)].get("id"),note); st.error(msg) if not ok else (save(data,sha,"Cancel booking"),go("Planning"))
def render_grid(rows,title,days=PLANNING_DAYS,show_instructor=True):
    st.markdown(f"### {title}"); today=date.today(); all_days=[(today+timedelta(days=i)).isoformat() for i in range(days)]; by={d:[] for d in all_days}
    for r in rows: by.setdefault(r.get("date",""),[]).append(r)
    a,b,c=st.columns(3); a.metric("Oggi",len([x for x in rows if x.get("date")==today.isoformat()])); b.metric(f"Prossimi {days} giorni",len(rows)); c.metric("Omaggio",len([x for x in rows if gift(x)]))
    cards=[]
    for d in all_days:
        slot={}
        for r in by.get(d,[]): slot.setdefault((r.get("time",""),r.get("instructor","")),[]).append(r)
        lines=[]
        for (t,ins),grp in sorted(slot.items()):
            conf=[x for x in grp if x.get("status")=="Confermata"]; wait=[x for x in grp if x.get("status")=="Lista attesa"]; names=", ".join([x.get("name","")+(" (omaggio)" if gift(x) else "") for x in conf]) or "—"; ins_txt=f" <span>{esc(ins)}</span>" if show_instructor and ins else ""
            lines.append(f"<div class='slot'><b>{esc(t)}</b>{ins_txt} <em>{len(conf)}/{CAPACITY} · lib {max(CAPACITY-len(conf),0)}"+(f" · att {len(wait)}" if wait else "")+f"</em><br><small>{esc(names)}</small></div>")
        cards.append(f"<div class='day-card{' empty' if not lines else ''}'><div class='day-title'>{esc(dlabel(d))}</div>{''.join(lines) if lines else '<div class=empty-text>—</div>'}</div>")
    st.markdown("<style>.plan-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:7px}.day-card{border:1px solid #d9dde3;border-radius:10px;padding:8px 10px;background:#fff;min-height:76px}.day-card.empty{background:#fafafa;color:#9aa0a6}.day-title{font-weight:700;font-size:.92rem;margin-bottom:5px}.slot{font-size:.84rem;line-height:1.18;margin:3px 0 5px;padding-bottom:4px;border-bottom:1px solid #eef0f2}.slot:last-child{border-bottom:0}.slot em{font-style:normal;color:#707782;font-size:.78rem}.slot small{font-size:.78rem}</style><div class='plan-grid'>"+"".join(cards)+"</div>",unsafe_allow_html=True)
    if rows:
        with st.expander("Elenco rapido",False): st.dataframe(plan_table(rows),use_container_width=True,hide_index=True)
def render_planning(data,sha):
    st.subheader("Planning 3 mesi")
    if st.button("Apri Incassi",type="primary"): go("Incassi")
    cancel_box(data,sha)
    if admin():
        view=st.selectbox("Vista",["Tutte",*INSTRUCTORS]); ins=None if view=="Tutte" else view; render_grid(planning_rows(data,PLANNING_DAYS,ins),f"Planning {view}",PLANNING_DAYS,True); return
    ins=instr_user(); tab1,tab2=st.tabs(["Planning completo","I miei impegni"])
    with tab1: render_grid(planning_rows(data,PLANNING_DAYS,None),"Planning completo",PLANNING_DAYS,True)
    with tab2: render_grid(planning_rows(data,PLANNING_DAYS,ins),f"Prossimi impegni {ins}",PLANNING_DAYS,False)


def render_clients(data,sha):
    st.subheader("Clienti")
    with st.expander("Aggiungi cliente",False):
        a,b=st.columns(2); last=a.text_input("Cognome",key="add_last"); first=b.text_input("Nome",key="add_first"); c,d=st.columns(2); phone=c.text_input("Telefono",key="add_phone"); email=d.text_input("Email",key="add_email"); birth=st.text_input("Data di nascita",key="add_birth"); notes=st.text_area("Note",key="add_notes")
        if st.button("Salva nuovo cliente",type="primary"): ok,msg,cid=add_client(data,first,last,phone,email,notes,birth); st.error(msg) if not ok else (st.session_state.__setitem__("edit_client_id",cid),save(data,sha,"Add client"),go("Clienti"))
    clients=sorted(data["clients"],key=lambda c:(str(c.get("last_name","")).lower(),str(c.get("first_name","")).lower()))
    if clients: st.dataframe(pd.DataFrame([{"Cognome":c.get("last_name",""),"Nome":c.get("first_name",""),"Telefono":c.get("phone",""),"Email":c.get("email",""),"Note":c.get("notes","")} for c in clients]),use_container_width=True,hide_index=True)
    st.markdown("### Modifica scheda cliente"); opts=client_opts(data)
    if not opts: return
    choice=st.selectbox("Scegli cliente",opts,key="pick_client"); cid=opt_id(choice)
    if st.button("Apri scheda selezionata",type="primary"): st.session_state["edit_client_id"]=cid; st.rerun()
    cid=st.session_state.get("edit_client_id",""); c=get_client(data,cid)
    if not c: st.info("Scegli un cliente e clicca 'Apri scheda selezionata'."); return
    st.success(f"Scheda aperta: {cname(c)}")
    with st.form(f"edit_{cid}"):
        a,b=st.columns(2); last=a.text_input("Cognome",value=c.get("last_name","")); first=b.text_input("Nome",value=c.get("first_name","")); x,y=st.columns(2); phone=x.text_input("Telefono",value=c.get("phone","")); email=y.text_input("Email",value=c.get("email","")); birth=st.text_input("Data nascita",value=c.get("birth_date","")); notes=st.text_area("Note",value=c.get("notes","")); sub=st.form_submit_button("Salva questa scheda cliente",type="primary")
    if sub:
        ok,msg=update_client(data,cid,first,last,phone,email,birth,notes); st.error(msg) if not ok else (save(data,sha,"Update client"),go("Clienti"))

def render_search(data):
    st.subheader("Cerca"); q=st.text_input("Cerca cliente, telefono, istruttrice, nota").lower().strip(); rows=[]
    for b in data["bookings"]:
        hay=" ".join(str(b.get(k,"")) for k in ["name","phone","email","instructor","note","date","time"]).lower()
        if not q or q in hay: rows.append({"Data":dit(b.get("date")),"Ora":b.get("time",""),"Cliente":b.get("name",""),"Telefono":b.get("phone",""),"Istruttrice":b.get("instructor",""),"Stato":b.get("status",""),"Importo":money(b.get("amount")),"Tipo":"Omaggio" if gift(b) else "Pagamento","Note":b.get("note","")})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
def render_archive(data,sha):
    st.subheader("Archivio prenotazioni"); rows=[{"Data":dit(b.get("date")),"Ora":b.get("time",""),"Cliente":b.get("name",""),"Telefono":b.get("phone",""),"Istruttrice":b.get("instructor",""),"Stato":b.get("status",""),"Tipo":"Omaggio" if gift(b) else "Pagamento","Importo":money(b.get("amount")),"Incassato":"Omaggio" if gift(b) else ("Sì" if yes(b.get("paid")) else "No"),"Quota chiusa":"Sì" if b.get("settlement_id") else "No","Note":b.get("note","")} for b in data["bookings"]]
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True) if rows else st.info("Archivio vuoto.")

def run():
    header()
    if not login(): return
    data,sha=load(); data=ensure(data); allowed=pages(); nxt=st.session_state.pop("_next_section",None)
    if nxt in allowed: st.session_state["section"]=nxt
    if st.session_state.get("section") not in allowed: st.session_state["section"]="Planning"
    section=st.radio("Sezione",allowed,horizontal=True,key="section",label_visibility="collapsed")
    a,b=st.columns([4,1]); a.caption(f"Accesso: {user().capitalize()} · {'Admin' if admin() else 'Istruttrice'}")
    if b.button("Logout",use_container_width=True):
        for k in ["authenticated","current_user","current_role","section","_next_section","edit_client_id"]: st.session_state.pop(k,None)
        st.rerun()
    st.divider(); {"Planning":render_planning,"Prenota":render_booking,"Incassi":render_incassi,"Clienti":render_clients,"Cerca":lambda d,s:render_search(d),"Archivio":render_archive}[section](data,sha)
run()
