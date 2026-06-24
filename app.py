import base64, json, os, re
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
import pandas as pd
import requests
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

CAPACITY=4
LOCAL_DATA_PATH="data/bookings.json"
LOGO_PATH="assets/logo.png"
INSTRUCTORS=["Grazia","Alice"]
GREEN="#496744"; DARK="#243142"
SCHEDULE={0:["08:30","09:30","10:30","17:00","18:00","19:00"],1:["09:30","10:30","11:30","12:45","14:30","19:00"],2:["08:30","09:30","10:30","11:30","12:45","14:30","15:30","16:30","17:30","18:30"],3:["17:00","18:00","19:00"],4:["14:00","15:00","16:00","17:00","18:00","19:00"]}
DAY_NAMES={0:"Lunedì",1:"Martedì",2:"Mercoledì",3:"Giovedì",4:"Venerdì",5:"Sabato",6:"Domenica"}

def get_secret(n,d=""):
    try: return str(st.secrets.get(n,d))
    except Exception: return os.environ.get(n,d)

def github_enabled(): return bool(get_secret("GITHUB_TOKEN") and get_secret("GITHUB_REPO") and get_secret("GITHUB_BRANCH","main"))
def github_headers(): return {"Authorization":f"Bearer {get_secret('GITHUB_TOKEN')}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}
def github_file_url(): return f"https://api.github.com/repos/{get_secret('GITHUB_REPO')}/contents/{LOCAL_DATA_PATH}"

def save_data(data,sha=None,message="Update data"):
    if github_enabled():
        body={"message":message,"content":base64.b64encode(json.dumps(data,ensure_ascii=False,indent=2).encode()).decode(),"branch":get_secret("GITHUB_BRANCH","main")}
        if sha: body["sha"]=sha
        r=requests.put(github_file_url(),headers=github_headers(),json=body,timeout=20)
        if r.status_code==409: st.error("Conflitto: ricarica la pagina e riprova."); st.stop()
        r.raise_for_status(); return
    Path(LOCAL_DATA_PATH).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")

def load_data():
    if github_enabled():
        r=requests.get(github_file_url(),headers=github_headers(),params={"ref":get_secret("GITHUB_BRANCH","main")},timeout=20)
        if r.status_code==404:
            data={"bookings":[],"clients":[]}; save_data(data,None,"Initialize storage"); return data,None
        r.raise_for_status(); p=r.json(); return json.loads(base64.b64decode(p["content"]).decode()),p.get("sha")
    p=Path(LOCAL_DATA_PATH)
    if not p.exists(): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps({"bookings":[],"clients":[]},ensure_ascii=False,indent=2),encoding="utf-8")
    return json.loads(p.read_text(encoding="utf-8")),None

def parse_date(d):
    if isinstance(d,date): return d
    s=str(d).strip()
    for f in ("%Y-%m-%d","%d/%m/%Y","%d-%m-%Y"):
        try: return datetime.strptime(s,f).date()
        except ValueError: pass
    return pd.to_datetime(s,dayfirst=True).date()
def date_key(d): return d.isoformat()
def date_it(d):
    try: return parse_date(d).strftime("%d-%m-%Y")
    except Exception: return str(d or "")
def money(v):
    try: return round(float(v or 0),2)
    except Exception: return 0.0
def new_id(p=""): return p+datetime.now().strftime("%Y%m%d%H%M%S%f")
def norm(s): return re.sub(r"\s+"," ",str(s or "").strip().lower())
def ckey(first,last): return f"{norm(first)}|{norm(last)}"
def full_name(c): return f"{str(c.get('last_name','')).strip()} {str(c.get('first_name','')).strip()}".strip()
def split_name(n):
    parts=str(n or "").strip().split()
    if not parts: return "",""
    if len(parts)==1: return parts[0],""
    return " ".join(parts[1:]),parts[0]

def ensure_data(data):
    data.setdefault("bookings",[]); data.setdefault("clients",[])
    keys={ckey(c.get("first_name",""),c.get("last_name","")):c for c in data["clients"]}
    for b in data["bookings"]:
        b.setdefault("amount",0); b.setdefault("paid",False); b.setdefault("note",""); b.setdefault("instructor","")
        if b.get("client_id"): continue
        first,last=split_name(b.get("name","")); k=ckey(first,last)
        if k.strip("|") and k in keys: b["client_id"]=keys[k]["id"]
        elif k.strip("|"):
            c={"id":new_id("c_"),"first_name":first,"last_name":last,"phone":b.get("phone",""),"email":b.get("email",""),"notes":"","created_at":datetime.now().isoformat(timespec="seconds")}
            data["clients"].append(c); keys[k]=c; b["client_id"]=c["id"]
    return data

def get_client(data,cid):
    return next((c for c in data.get("clients",[]) if c.get("id")==cid),None)
def client_options(data): return sorted([f"{full_name(c)} | {c.get('phone','')} | {c.get('email','')} | {c.get('id')}" for c in data.get("clients",[])],key=str.lower)
def opt_id(o): return o.split("|")[-1].strip()
def add_client(data,first,last,phone="",email="",notes=""):
    first,last=first.strip(),last.strip()
    if not first or not last: return False,"Inserisci nome e cognome.",None
    k=ckey(first,last)
    for c in data.get("clients",[]):
        if ckey(c.get("first_name",""),c.get("last_name",""))==k: return False,"Cliente già presente: nome e cognome devono essere univoci.",c.get("id")
    cid=new_id("c_"); data["clients"].append({"id":cid,"first_name":first,"last_name":last,"phone":phone.strip(),"email":email.strip(),"notes":notes.strip(),"created_at":datetime.now().isoformat(timespec="seconds")})
    return True,"Cliente salvato.",cid

def times_for(d): return SCHEDULE.get(d.weekday(),[])
def next_days(start,n=5):
    out=[]; d=start
    while len(out)<n:
        if d.weekday() in SCHEDULE: out.append(d)
        d+=timedelta(days=1)
    return out
def slot_rows(data,d,t,include_cancelled=False):
    return sorted([b for b in data.get("bookings",[]) if b.get("date")==date_key(d) and b.get("time")==t and (include_cancelled or b.get("status")!="Annullata")],key=lambda x:x.get("created_at",""))
def confirmed_count(data,d,t,exclude_id=None): return sum(1 for b in slot_rows(data,d,t) if b.get("status")=="Confermata" and b.get("id")!=exclude_id)
def auto_status(data,d,t): return "Confermata" if confirmed_count(data,d,t)<CAPACITY else "Lista attesa"
def slot_status(data,d,t):
    rows=slot_rows(data,d,t); conf=[b for b in rows if b.get("status")=="Confermata"]; wait=[b for b in rows if b.get("status")=="Lista attesa"]
    return len(conf),len(wait),conf,wait

def create_booking(data,cid,d,t,amount,paid,instr,note):
    c=get_client(data,cid)
    if not c: raise ValueError("Cliente non trovato.")
    b={"id":new_id("b_"),"created_at":datetime.now().isoformat(timespec="seconds"),"client_id":cid,"date":date_key(d),"day":DAY_NAMES[d.weekday()],"time":t,"name":full_name(c),"phone":c.get("phone",""),"email":c.get("email",""),"note":note.strip(),"status":auto_status(data,d,t),"amount":money(amount),"paid":bool(paid),"instructor":instr,"created_by":"staff"}
    data["bookings"].append(b); return b

def change_status(data,bid,status):
    for b in data.get("bookings",[]):
        if b.get("id")==bid:
            d=parse_date(b["date"]); t=b["time"]
            if status=="Confermata" and confirmed_count(data,d,t,bid)>=CAPACITY: st.error("Lezione già piena (4/4)."); return False
            b["status"]=status; return True
    return False
def delete_bookings(data,ids):
    ids=set(ids); old=len(data["bookings"]); data["bookings"]=[b for b in data["bookings"] if b.get("id") not in ids]; return old-len(data["bookings"])

def archive_df(data):
    rows=[]
    for b in data.get("bookings",[]):
        c=get_client(data,b.get("client_id"))
        rows.append({"Eliminazione":False,"ID":b.get("id"),"Data":date_it(b.get("date")),"Giorno":b.get("day"),"Ora":b.get("time"),"Cliente":full_name(c) if c else b.get("name",""),"Telefono":(c or {}).get("phone",b.get("phone","")),"Email":(c or {}).get("email",b.get("email","")),"Istruttrice":b.get("instructor",""),"Stato":b.get("status"),"Importo":money(b.get("amount",0)),"Pagato":bool(b.get("paid",False)),"Note":b.get("note",""),"Inserita il":b.get("created_at")})
    cols=["Eliminazione","ID","Data","Giorno","Ora","Cliente","Telefono","Email","Istruttrice","Stato","Importo","Pagato","Note","Inserita il"]
    if not rows: return pd.DataFrame(columns=cols)
    df=pd.DataFrame(rows); df["_s"]=pd.to_datetime(df["Data"],dayfirst=True,errors="coerce"); return df.sort_values(["_s","Ora","Cliente"]).drop(columns=["_s"])

def clients_df(data):
    rows=[]
    for c in data.get("clients",[]):
        n=sum(1 for b in data.get("bookings",[]) if b.get("client_id")==c.get("id"))
        rows.append({"ID":c.get("id"),"Cognome":c.get("last_name",""),"Nome":c.get("first_name",""),"Telefono":c.get("phone",""),"Email":c.get("email",""),"Note cliente":c.get("notes",""),"Prenotazioni":n})
    cols=["ID","Cognome","Nome","Telefono","Email","Note cliente","Prenotazioni"]
    return pd.DataFrame(rows).sort_values(["Cognome","Nome"]) if rows else pd.DataFrame(columns=cols)

def period_range(opt):
    today=date.today()
    if opt=="Anno in corso": return date(today.year,1,1),date(today.year,12,31)
    if opt=="Ultimi 3 mesi": return today-timedelta(days=90),today
    if opt=="Ultimi 6 mesi": return today-timedelta(days=180),today
    if opt=="Ultimo anno": return today-timedelta(days=365),today
    return today.replace(day=1),today
def filter_period(df,start,end):
    if df.empty: return df.copy()
    dd=pd.to_datetime(df["Data"],dayfirst=True,errors="coerce").dt.date
    return df[(dd>=start)&(dd<=end)].copy()
def summary(df):
    if df.empty: return 0,0,0,pd.DataFrame(columns=["Istruttrice","Totale complessivo","Totale pagato","Totale non pagato"])
    w=df.copy(); w["Importo"]=pd.to_numeric(w["Importo"],errors="coerce").fillna(0); w=w[w["Stato"]!="Annullata"]
    tot=float(w["Importo"].sum()); paid=float(w.loc[w["Pagato"]==True,"Importo"].sum())
    rows=[]
    for i in INSTRUCTORS:
        s=w[w["Istruttrice"]==i]; it=float(s["Importo"].sum()); ip=float(s.loc[s["Pagato"]==True,"Importo"].sum()); rows.append({"Istruttrice":i,"Totale complessivo":it,"Totale pagato":ip,"Totale non pagato":it-ip})
    return tot,paid,tot-paid,pd.DataFrame(rows)

def make_excel(df):
    bio=BytesIO()
    with pd.ExcelWriter(bio,engine="openpyxl") as w:
        df.to_excel(w,index=False,sheet_name="Archivio")
        ws=w.sheets["Archivio"]
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width=min(max(max(len(str(c.value)) if c.value is not None else 0 for c in col)+2,10),38)
    bio.seek(0); return bio.getvalue()
def make_pdf(df,label=""):
    bio=BytesIO(); doc=SimpleDocTemplate(bio,pagesize=landscape(A4),rightMargin=.8*cm,leftMargin=.8*cm,topMargin=.8*cm,bottomMargin=.8*cm); styles=getSampleStyleSheet(); tot,paid,unpaid,per=summary(df); elems=[]
    if Path(LOGO_PATH).exists(): elems.append(Image(LOGO_PATH,width=2.1*cm,height=3.2*cm))
    elems += [Paragraph("Archivio prenotazioni Pilates - Body Center",styles["Title"]),Paragraph(label,styles["Normal"]),Paragraph(f"Generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}",styles["Normal"]),Spacer(1,.25*cm)]
    t=Table([["Totale complessivo","Totale pagato","Totale non pagato"],[f"€ {tot:.2f}",f"€ {paid:.2f}",f"€ {unpaid:.2f}"]],colWidths=[5*cm]*3); t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor(GREEN)),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("ALIGN",(0,0),(-1,-1),"CENTER"),("GRID",(0,0),(-1,-1),.25,colors.lightgrey)])); elems+=[t,Spacer(1,.25*cm),Paragraph("Totali per istruttrice",styles["Heading2"])]
    it=Table([["Istruttrice","Totale complessivo","Totale pagato","Totale non pagato"]]+[[r["Istruttrice"],f"€ {r['Totale complessivo']:.2f}",f"€ {r['Totale pagato']:.2f}",f"€ {r['Totale non pagato']:.2f}"] for _,r in per.iterrows()],colWidths=[4*cm]*4); it.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor(DARK)),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("GRID",(0,0),(-1,-1),.25,colors.lightgrey)])); elems+=[it,Spacer(1,.35*cm)]
    cols=["Data","Ora","Cliente","Telefono","Email","Istruttrice","Stato","Importo","Pagato","Note"]; pdf=df[cols].copy() if not df.empty else pd.DataFrame(columns=cols); pdf["Pagato"]=pdf["Pagato"].map(lambda x:"Sì" if bool(x) else "No"); pdf["Importo"]=pdf["Importo"].map(lambda x:f"€ {money(x):.2f}"); pdf=pdf.fillna("").astype(str)
    tab=Table([cols]+pdf.values.tolist(),repeatRows=1,colWidths=[1.6*cm,1.1*cm,3.2*cm,2*cm,3*cm,1.8*cm,1.6*cm,1.4*cm,1.1*cm,5*cm]); tab.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor(GREEN)),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),6),("GRID",(0,0),(-1,-1),.25,colors.lightgrey),("VALIGN",(0,0),(-1,-1),"TOP")]))
    elems.append(tab); doc.build(elems); bio.seek(0); return bio.getvalue()

def update_archive(data,ed):
    n=0; by={b.get("id"):b for b in data.get("bookings",[])}
    for _,r in ed.iterrows():
        b=by.get(r.get("ID"));
        if not b: continue
        vals={"amount":money(r.get("Importo",0)),"paid":bool(r.get("Pagato",False)),"note":str(r.get("Note","") or "")}; ch=False
        for k,v in vals.items():
            if b.get(k)!=v: b[k]=v; ch=True
        if ch: n+=1
    return n
def update_clients(data,ed):
    n=0; by={c.get("id"):c for c in data.get("clients",[])}
    for _,r in ed.iterrows():
        c=by.get(r.get("ID"));
        if not c: continue
        for k,col in [("phone","Telefono"),("email","Email"),("notes","Note cliente")]:
            v=str(r.get(col,"") or "")
            if c.get(k,"")!=v: c[k]=v; n+=1
    return n

def login():
    st.sidebar.header("Accesso staff"); pwd=st.sidebar.text_input("Password",type="password")
    if pwd==get_secret("APP_PASSWORD","pilates123"): st.sidebar.success("Accesso consentito"); return True
    if pwd: st.sidebar.error("Password non corretta")
    return False

st.set_page_config(page_title=APP_TITLE,page_icon="🧘",layout="wide")
c1,c2=st.columns([1,6])
with c1:
    if Path(LOGO_PATH).exists(): st.image(LOGO_PATH,width=130)
with c2:
    st.markdown(f"<h1 style='margin-bottom:0;color:{DARK};'>Prenotazioni Pilates Reformer</h1>",unsafe_allow_html=True); st.caption("Gestionale interno Body Center · clienti, prenotazioni, pagamenti")
if not login(): st.info("Inserisci la password nella barra laterale."); st.stop()
try: data,sha=load_data(); data=ensure_data(data)
except Exception as e: st.error(f"Errore caricamento dati: {e}"); st.stop()
if not github_enabled(): st.warning("Modalità locale: per condivisione usa i Secrets GitHub su Streamlit.")

tab1,tab2,tab3,tab4,tab5=st.tabs(["📅 Settimana","➕ Prenota","👤 Clienti","🔎 Cerca","📋 Archivio"])
with tab1:
    st.subheader("Vista settimanale"); today=date.today(); start=max(parse_date(st.date_input("Scegli la data di partenza",value=today,min_value=today,format="DD/MM/YYYY")),today)
    for d in next_days(start,5):
        st.markdown(f"### {DAY_NAMES[d.weekday()]} {d.strftime('%d/%m/%Y')}"); cols=st.columns(3)
        for i,t in enumerate(times_for(d)):
            with cols[i%3]:
                n,_,conf,wait=slot_status(data,d,t); label=f"{t} — {n}/{CAPACITY}"; (st.error if n>=CAPACITY else st.info if n==0 else st.success)(label)
                for j,b in enumerate(conf,1): st.write(f"{j}. {b.get('name','')} · {b.get('instructor','')} · € {money(b.get('amount',0)):.2f} · {'pagato' if b.get('paid') else 'non pagato'}")
                if wait:
                    st.caption("Lista d'attesa:")
                    for b in wait: st.caption(f"• {b.get('name','')} · {b.get('phone','')}")
                with st.expander("Gestisci"):
                    for b in slot_rows(data,d,t,True):
                        st.markdown(f"**{status_icon(b.get('status'))} {b.get('name','')}** — {b.get('phone','')}"); a,b2,c=st.columns(3)
                        if a.button("Conferma",key=f"c{b['id']}") and change_status(data,b["id"],"Confermata"): save_data(data,sha,"Conferma"); st.rerun()
                        if b2.button("Attesa",key=f"w{b['id']}") and change_status(data,b["id"],"Lista attesa"): save_data(data,sha,"Attesa"); st.rerun()
                        if c.button("Annulla",key=f"x{b['id']}") and change_status(data,b["id"],"Annullata"): save_data(data,sha,"Annulla"); st.rerun()
with tab2:
    st.subheader("Prenota")
    mode=st.radio("Cliente",["Seleziona da archivio","Nuovo cliente"],horizontal=True); cid=None
    if mode=="Seleziona da archivio":
        opts=client_options(data)
        if opts: cid=opt_id(st.selectbox("Cliente",opts)); c=get_client(data,cid); st.caption(f"Telefono: {c.get('phone','')} · Email: {c.get('email','')}")
        else: st.warning("Nessun cliente in archivio.")
    else:
        a,b=st.columns(2); last=a.text_input("Cognome"); first=b.text_input("Nome"); c,d=st.columns(2); phone=c.text_input("Telefono"); email=d.text_input("Email"); notes=st.text_area("Note cliente")
        if st.button("Salva nuovo cliente"): 
            ok,msg,cid=add_client(data,first,last,phone,email,notes); (st.success if ok else st.error)(msg)
            if ok: save_data(data,sha,"Add client"); st.rerun()
    if cid:
        st.markdown("### Dati prenotazione"); a,b=st.columns(2); d=parse_date(a.date_input("Data",value=date.today(),min_value=date.today(),format="DD/MM/YYYY",key="bd")); ts=times_for(d)
        if ts:
            t=b.selectbox("Orario",ts); a,b,c=st.columns(3); amount=a.number_input("Importo (€)",min_value=0.0,value=0.0,step=1.0,format="%.2f"); paid=b.checkbox("Pagato"); instr=c.selectbox("Istruttrice",INSTRUCTORS); note=st.text_area("Note prenotazione"); st.info(f"Stato automatico: {auto_status(data,d,t)}")
            if st.button("Salva prenotazione",type="primary"):
                bk=create_booking(data,cid,d,t,amount,paid,instr,note); save_data(data,sha,f"Add booking {bk['name']}"); st.success(f"Prenotazione salvata: {bk['status']}."); st.rerun()
with tab3:
    st.subheader("Archivio clienti")
    with st.expander("➕ Inserisci nuovo cliente"):
        a,b=st.columns(2); last=a.text_input("Cognome",key="cl"); first=b.text_input("Nome",key="cf"); c,d=st.columns(2); phone=c.text_input("Telefono",key="cp"); email=d.text_input("Email",key="ce"); notes=st.text_area("Note cliente",key="cn")
        if st.button("Salva cliente"):
            ok,msg,_=add_client(data,first,last,phone,email,notes); (st.success if ok else st.error)(msg)
            if ok: save_data(data,sha,"Add client"); st.rerun()
    dfc=clients_df(data)
    if dfc.empty: st.info("Nessun cliente presente.")
    else:
        q=st.text_input("Cerca cliente").lower().strip(); view=dfc[dfc.apply(lambda r:q in " ".join(map(str,r.values)).lower(),axis=1)] if q else dfc
        ed=st.data_editor(view,use_container_width=True,hide_index=True,column_config={"ID":None},disabled=["Cognome","Nome","Prenotazioni"],key="ced")
        if st.button("Salva modifiche clienti"):
            n=update_clients(data,ed); st.success(f"Aggiornati {n} campi cliente.") if n else st.info("Nessuna modifica da salvare.")
            if n: save_data(data,sha,"Update clients"); st.rerun()
with tab4:
    st.subheader("Cerca")
    q=st.text_input("Cerca per nome, telefono o email").lower().strip(); dfa=archive_df(data)
    if q and not dfa.empty: st.dataframe(dfa[dfa.apply(lambda r:q in " ".join(map(str,r.values)).lower(),axis=1)].drop(columns=["Eliminazione","ID"],errors="ignore"),use_container_width=True,hide_index=True)
with tab5:
    st.subheader("Archivio, pagamenti e statistiche"); dfa=archive_df(data)
    if dfa.empty: st.info("Nessuna prenotazione presente.")
    else:
        opt=st.selectbox("Scegli periodo",["Anno in corso","Mese selezionato","Periodo personalizzato","Ultimi 3 mesi","Ultimi 6 mesi","Ultimo anno"],index=0); today=date.today()
        if opt=="Mese selezionato":
            m=parse_date(st.date_input("Mese di riferimento",value=today,format="DD/MM/YYYY")); start=m.replace(day=1); end=(start.replace(day=28)+timedelta(days=4)).replace(day=1)-timedelta(days=1)
        elif opt=="Periodo personalizzato":
            a,b=st.columns(2); start=parse_date(a.date_input("Dal",value=date(today.year,1,1),format="DD/MM/YYYY")); end=parse_date(b.date_input("Al",value=date(today.year,12,31),format="DD/MM/YYYY"))
        else: start,end=period_range(opt)
        dfp=filter_period(dfa,start,end); label=f"Periodo: {start.strftime('%d-%m-%Y')} - {end.strftime('%d-%m-%Y')}"; st.caption(label)
        tot,paid,unpaid,per=summary(dfp); a,b,c=st.columns(3); a.metric("Totale complessivo",f"€ {tot:.2f}"); b.metric("Totale pagato",f"€ {paid:.2f}"); c.metric("Totale non pagato",f"€ {unpaid:.2f}")
        st.dataframe(per,use_container_width=True,hide_index=True)
        status=st.multiselect("Filtra stato archivio",["Confermata","Lista attesa","Annullata"],default=["Confermata","Lista attesa"]); only=st.checkbox("Mostra in tabella solo il periodo selezionato",value=True)
        df=dfp.copy() if only else dfa.copy(); df=df[df["Stato"].isin(status)] if status else df
        cols=["Eliminazione","Data","Giorno","Ora","Cliente","Telefono","Email","Istruttrice","Stato","Importo","Pagato","Note","Inserita il","ID"]
        ed=st.data_editor(df[cols],use_container_width=True,hide_index=True,column_config={"Eliminazione":st.column_config.CheckboxColumn("Eliminazione"),"Pagato":st.column_config.CheckboxColumn("Pagato"),"Importo":st.column_config.NumberColumn("Importo (€)",min_value=0.0,step=1.0,format="%.2f"),"Note":st.column_config.TextColumn("Note"),"ID":None},disabled=["Data","Giorno","Ora","Cliente","Telefono","Email","Istruttrice","Stato","Inserita il"],key="aed")
        a,b=st.columns(2)
        if a.button("Salva modifiche importi/pagamenti/note"):
            n=update_archive(data,ed); st.success(f"Aggiornate {n} prenotazioni.") if n else st.info("Nessuna modifica da salvare.")
            if n: save_data(data,sha,"Update archive"); st.rerun()
        ids=ed.loc[ed["Eliminazione"]==True,"ID"].dropna().astype(str).tolist()
        if b.button("Elimina selezionate",type="primary"):
            if not ids: st.error("Non hai selezionato nessuna prenotazione da eliminare.")
            else: n=delete_bookings(data,ids); save_data(data,sha,"Delete bookings"); st.success(f"Eliminate {n} prenotazioni."); st.rerun()
        vis=ed.drop(columns=["Eliminazione","ID"],errors="ignore"); a,b=st.columns(2); a.download_button("Scarica Excel",data=make_excel(vis),file_name="prenotazioni_pilates.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"); b.download_button("Scarica PDF archivio",data=make_pdf(vis,label),file_name="archivio_prenotazioni_pilates.pdf",mime="application/pdf")
