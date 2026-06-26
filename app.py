import os
import sqlite3
from datetime import date

import pandas as pd
import streamlit as st
from fpdf import FPDF

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(page_title="DB Nutrition Performance", layout="wide", page_icon="🧬")

DB_NAME = "performance_lab_pro.db"
LOGO_PATH = "Logo NUTRITION AND PERFORMANCE.png"
PROFILI = ["Scalatore", "Passista", "Triatleta", "Granfondista", "Altro"]
TIPI_TEST = ["Manuale", "Test 20'", "Test 8'", "Incrementale"]


# =========================================================
# DATABASE
# =========================================================
def get_connection():
    return sqlite3.connect(DB_NAME)


def init_db():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS atleti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                cognome TEXT NOT NULL,
                altezza REAL,
                profilo TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS visite (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                atleta_id INTEGER NOT NULL,
                data TEXT,
                peso REAL,
                fm REAL,
                ftp REAL,
                lthr INTEGER,
                peso_t REAL,
                fm_t REAL,
                ftp_t REAL,
                dist_km REAL,
                grad REAL,
                bike_w REAL,
                t_att REAL,
                t_tar REAL,
                wkg_att REAL,
                wkg_tar REAL,
                FOREIGN KEY(atleta_id) REFERENCES atleti(id)
            )
        """)

        # Migrazione per database vecchi già creati
        c.execute("PRAGMA table_info(visite)")
        existing_cols = [x[1] for x in c.fetchall()]
        migrations = {
            "wkg_att": "ALTER TABLE visite ADD COLUMN wkg_att REAL",
            "wkg_tar": "ALTER TABLE visite ADD COLUMN wkg_tar REAL",
        }
        for col, sql in migrations.items():
            if col not in existing_cols:
                c.execute(sql)
        conn.commit()


init_db()


def get_all_atleti():
    with get_connection() as conn:
        return pd.read_sql_query(
            "SELECT * FROM atleti ORDER BY cognome ASC, nome ASC, id ASC",
            conn,
        )


def get_visite(atleta_id):
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT id, data, peso, fm, ftp, lthr, peso_t, fm_t, ftp_t,
                   dist_km, grad, bike_w, t_att, t_tar, wkg_att, wkg_tar
            FROM visite
            WHERE atleta_id=?
            ORDER BY data DESC, id DESC
            """,
            conn,
            params=(int(atleta_id),),
        )


# =========================================================
# MOTORE SCIENTIFICO
# =========================================================
class BioPerformance:
    @staticmethod
    def calculate_ftp(tipo, valore):
        factors = {
            "Manuale": 1.00,
            "Test 20'": 0.95,
            "Test 8'": 0.90,
            "Incrementale": 0.75,
        }
        return float(valore) * factors.get(tipo, 1.00)

    @staticmethod
    def estimate_time(watt, peso, km, pend, bike_w):
        try:
            watt = float(watt)
            peso = float(peso)
            km = float(km)
            pend = float(pend)
            bike_w = float(bike_w)
            if watt <= 0 or peso <= 0 or km <= 0:
                return 0.0
            f_res = (peso + bike_w) * 9.81 * ((pend / 100) + 0.005)
            if f_res <= 0:
                return 0.0
            speed_ms = watt / f_res
            return (km * 1000 / speed_ms) / 60
        except Exception:
            return 0.0

    @staticmethod
    def power_zones_coggan(ftp):
        ftp = float(ftp)
        return [
            ("Z1 Recupero", 0, round(ftp * 0.55)),
            ("Z2 Endurance", round(ftp * 0.56), round(ftp * 0.75)),
            ("Z3 Tempo", round(ftp * 0.76), round(ftp * 0.90)),
            ("Z4 Soglia", round(ftp * 0.91), round(ftp * 1.05)),
            ("Z5 VO2max", round(ftp * 1.06), round(ftp * 1.20)),
            ("Z6 Capacità anaerobica", round(ftp * 1.21), round(ftp * 1.50)),
            ("Z7 Neuromuscolare", round(ftp * 1.51), f"> {round(ftp * 1.50)}"),
        ]

    @staticmethod
    def hr_zones_fthr(fthr):
        fthr = int(fthr)
        return [
            ("Z1 Recupero", 0, round(fthr * 0.80)),
            ("Z2 Endurance", round(fthr * 0.81), round(fthr * 0.89)),
            ("Z3 Tempo", round(fthr * 0.90), round(fthr * 0.93)),
            ("Z4 Soglia", round(fthr * 0.94), round(fthr * 0.99)),
            ("Z5 Sopra soglia", round(fthr * 1.00), f"> {round(fthr * 1.00)}"),
        ]

    @staticmethod
    def benchmarks():
        return pd.DataFrame(
            [
                ["World Tour", "5–7%", "6.0–6.5", 65],
                ["Pro Continental", "7–9%", "5.5–6.0", 68],
                ["Elite / U23", "8–11%", "4.5–5.5", 70],
                ["Amatore Top", "10–14%", "3.5–4.5", 72],
                ["Cicloturista", ">15%", "<3.0", 78],
            ],
            columns=["Categoria", "Range FM %", "W/kg soglia", "Peso medio kg"],
        )


# =========================================================
# PDF
# =========================================================
def pdf_safe(text):
    text = "" if text is None else str(text)
    repl = {
        "à": "a", "è": "e", "é": "e", "ì": "i", "ò": "o", "ù": "u",
        "À": "A", "È": "E", "É": "E", "Ì": "I", "Ò": "O", "Ù": "U",
        "²": "2", "₂": "2", "VO₂": "VO2", "–": "-", "→": "->",
        "≥": ">=", "≤": "<=",
    }
    for k, v in repl.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


def make_report_dict(nome, cognome, altezza, profilo, data_iso, peso, fm, ftp, lthr,
                     peso_t, fm_t, ftp_t, dist, grad, bike, tipo_test="Archivio"):
    altezza = float(altezza)
    peso = float(peso)
    peso_t = float(peso_t)
    ftp = float(ftp)
    ftp_t = float(ftp_t)
    lthr = int(lthr)

    tempo_att = BioPerformance.estimate_time(ftp, peso, dist, grad, bike)
    tempo_tar = BioPerformance.estimate_time(ftp_t, peso_t, dist, grad, bike)
    wkg_att = ftp / peso if peso else 0
    wkg_tar = ftp_t / peso_t if peso_t else 0

    try:
        data_it = pd.to_datetime(data_iso).strftime("%d/%m/%Y")
    except Exception:
        data_it = str(data_iso)

    return {
        "nome": nome,
        "cognome": cognome,
        "altezza": altezza,
        "profilo": profilo,
        "data": data_it,
        "data_iso": str(data_iso),
        "peso_att": peso,
        "fm_att": float(fm),
        "ftp_att": ftp,
        "lthr": lthr,
        "bmi_att": peso / ((altezza / 100) ** 2),
        "tipo_test": tipo_test,
        "peso_tar": peso_t,
        "fm_tar": float(fm_t),
        "ftp_tar": ftp_t,
        "bmi_tar": peso_t / ((altezza / 100) ** 2),
        "dist": float(dist),
        "grad": float(grad),
        "bike": float(bike),
        "tempo_att": tempo_att,
        "tempo_tar": tempo_tar,
        "tempo_delta": tempo_tar - tempo_att,
        "wkg_att": wkg_att,
        "wkg_tar": wkg_tar,
        "wkg_delta": wkg_tar - wkg_att,
        "zones_power_att": BioPerformance.power_zones_coggan(ftp),
        "zones_power_tar": BioPerformance.power_zones_coggan(ftp_t),
        "zones_hr": BioPerformance.hr_zones_fthr(lthr),
    }


def create_pdf(r):
    pdf = FPDF()
    pdf.add_page()

    if os.path.exists(LOGO_PATH):
        try:
            pdf.image(LOGO_PATH, 10, 8, 45)
            pdf.ln(30)
        except Exception:
            pdf.ln(10)
    else:
        pdf.ln(10)

    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, pdf_safe(f"REPORT PERFORMANCE: {r['nome']} {r['cognome']}"), 0, 1, "C")
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 7, pdf_safe(f"Data: {r['data']} | Profilo: {r['profilo']} | Altezza: {r['altezza']:.0f} cm"), 0, 1, "C")
    pdf.ln(8)

    pdf.set_fill_color(230, 230, 230)

    def section(title):
        pdf.ln(4)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 9, pdf_safe(title), 1, 1, "L", True)
        pdf.set_font("Arial", "", 10)

    section("1. PARAMETRI ANTROPOMETRICI")
    pdf.cell(63, 8, pdf_safe(f"Peso attuale: {r['peso_att']:.1f} kg"), 1)
    pdf.cell(63, 8, pdf_safe(f"FM attuale: {r['fm_att']:.1f}%"), 1)
    pdf.cell(64, 8, pdf_safe(f"BMI attuale: {r['bmi_att']:.1f}"), 1, 1)
    pdf.cell(63, 8, pdf_safe(f"Peso target: {r['peso_tar']:.1f} kg"), 1)
    pdf.cell(63, 8, pdf_safe(f"FM target: {r['fm_tar']:.1f}%"), 1)
    pdf.cell(64, 8, pdf_safe(f"BMI target: {r['bmi_tar']:.1f}"), 1, 1)

    section("2. VALUTAZIONE FUNZIONALE")
    pdf.cell(63, 8, pdf_safe(f"Protocollo: {r['tipo_test']}"), 1)
    pdf.cell(63, 8, pdf_safe(f"FTP attuale: {r['ftp_att']:.0f} W"), 1)
    pdf.cell(64, 8, pdf_safe(f"FTP target: {r['ftp_tar']:.0f} W"), 1, 1)
    pdf.cell(63, 8, pdf_safe(f"W/kg attuale: {r['wkg_att']:.2f}"), 1)
    pdf.cell(63, 8, pdf_safe(f"W/kg target: {r['wkg_tar']:.2f}"), 1)
    pdf.cell(64, 8, pdf_safe(f"Delta W/kg: {r['wkg_delta']:+.2f}"), 1, 1)

    section("3. SCENARIO SALITA")
    pdf.cell(0, 8, pdf_safe(f"Parametri: {r['dist']:.1f} km | {r['grad']:.1f}% | Bici {r['bike']:.1f} kg"), 1, 1)
    pdf.cell(95, 8, pdf_safe(f"Tempo attuale: {r['tempo_att']:.2f} min"), 1)
    pdf.cell(95, 8, pdf_safe(f"Tempo target: {r['tempo_tar']:.2f} min"), 1, 1)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 8, pdf_safe(f"Differenza: {r['tempo_delta']:+.2f} min"), 1, 1, "C")

    for title, zones, c2, c3 in [
        ("4. ZONE DI POTENZA - FTP ATTUALE", r["zones_power_att"], "Watt Min", "Watt Max"),
        ("5. ZONE DI POTENZA - FTP TARGET", r["zones_power_tar"], "Watt Min", "Watt Max"),
        ("6. ZONE CARDIACHE - FTHR / LTHR", r["zones_hr"], "BPM Min", "BPM Max"),
    ]:
        section(title)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(80, 7, "Zona", 1)
        pdf.cell(55, 7, c2, 1)
        pdf.cell(55, 7, c3, 1, 1)
        pdf.set_font("Arial", "", 9)
        for z in zones:
            pdf.cell(80, 7, pdf_safe(z[0]), 1)
            pdf.cell(55, 7, str(z[1]), 1)
            pdf.cell(55, 7, str(z[2]), 1, 1)

    return pdf.output(dest="S").encode("latin-1", "ignore")


# =========================================================
# SALVATAGGIO / UPDATE
# =========================================================
def salva_visita(r):
    nome = r["nome"].strip()
    cognome = r["cognome"].strip()
    atleta_id_esistente = r.get("atleta_id_esistente")

    with get_connection() as conn:
        cur = conn.cursor()

        if atleta_id_esistente is None:
            # Nuovo atleta: crea sempre una nuova scheda atleta
            cur.execute(
                "INSERT INTO atleti (nome, cognome, altezza, profilo) VALUES (?, ?, ?, ?)",
                (nome, cognome, r["altezza"], r["profilo"]),
            )
            atleta_id = cur.lastrowid
        else:
            # Atleta esistente: aggiunge una nuova visita alla stessa scheda atleta
            atleta_id = int(atleta_id_esistente)
            cur.execute(
                "UPDATE atleti SET nome=?, cognome=?, altezza=?, profilo=? WHERE id=?",
                (nome, cognome, r["altezza"], r["profilo"], atleta_id),
            )

        cur.execute(
            """
            INSERT INTO visite (
                atleta_id, data, peso, fm, ftp, lthr, peso_t, fm_t, ftp_t,
                dist_km, grad, bike_w, t_att, t_tar, wkg_att, wkg_tar
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                atleta_id,
                r["data_iso"],
                r["peso_att"],
                r["fm_att"],
                r["ftp_att"],
                r["lthr"],
                r["peso_tar"],
                r["fm_tar"],
                r["ftp_tar"],
                r["dist"],
                r["grad"],
                r["bike"],
                r["tempo_att"],
                r["tempo_tar"],
                r["wkg_att"],
                r["wkg_tar"],
            ),
        )
        conn.commit()


def aggiorna_atleta(atleta_id, nome, cognome, altezza, profilo):
    with get_connection() as conn:
        conn.execute(
            "UPDATE atleti SET nome=?, cognome=?, altezza=?, profilo=? WHERE id=?",
            (nome.strip(), cognome.strip(), altezza, profilo, int(atleta_id)),
        )
        conn.commit()


def aggiorna_visita(visita_id, peso, fm, ftp, lthr, peso_t, fm_t, ftp_t, dist, grad, bike):
    t_att = BioPerformance.estimate_time(ftp, peso, dist, grad, bike)
    t_tar = BioPerformance.estimate_time(ftp_t, peso_t, dist, grad, bike)
    wkg_att = ftp / peso if peso > 0 else 0
    wkg_tar = ftp_t / peso_t if peso_t > 0 else 0

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE visite
            SET peso=?, fm=?, ftp=?, lthr=?, peso_t=?, fm_t=?, ftp_t=?,
                dist_km=?, grad=?, bike_w=?, t_att=?, t_tar=?, wkg_att=?, wkg_tar=?
            WHERE id=?
            """,
            (
                peso, fm, ftp, lthr, peso_t, fm_t, ftp_t,
                dist, grad, bike, t_att, t_tar, wkg_att, wkg_tar, int(visita_id),
            ),
        )
        conn.commit()


# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, use_container_width=True)
    st.markdown("---")
    menu = st.radio("NAVIGAZIONE", ["➕ Nuova Valutazione", "📂 Archivio & Edit"])


# =========================================================
# NUOVA VALUTAZIONE
# =========================================================
if menu == "➕ Nuova Valutazione":
    st.header("📋 Inserimento Protocollo Valutazione")

    with st.container(border=True):
        st.subheader("👤 Anagrafica atleta")
        db_atleti = get_all_atleti()

        modalita = st.radio(
            "Modalità inserimento",
            ["Nuovo atleta", "Nuova analisi per atleta già esistente"],
            horizontal=True,
            key="modalita_inserimento",
        )

        atleta_id_esistente = None

        if modalita == "Nuova analisi per atleta già esistente" and not db_atleti.empty:
            db_atleti = db_atleti.copy()
            db_atleti["label"] = db_atleti.apply(lambda x: f"{x['id']} - {x['cognome']} {x['nome']}", axis=1)
            atleta_label = st.selectbox("Seleziona atleta esistente", db_atleti["label"].tolist())
            atleta_id_esistente = int(atleta_label.split(" - ")[0])
            atleta_row = db_atleti[db_atleti["id"] == atleta_id_esistente].iloc[0]

            c1, c2, c3, c4 = st.columns([2, 2, 1, 2])
            cognome = c1.text_input("Cognome", value=str(atleta_row["cognome"]), key=f"cognome_existing_{atleta_id_esistente}").strip()
            nome = c2.text_input("Nome", value=str(atleta_row["nome"]), key=f"nome_existing_{atleta_id_esistente}").strip()
            altezza = c3.number_input("Altezza (cm)", 120, 230, int(atleta_row["altezza"]) if pd.notna(atleta_row["altezza"]) else 175, 1, key=f"altezza_existing_{atleta_id_esistente}")
            profilo = c4.selectbox(
                "Profilo atleta",
                PROFILI,
                index=PROFILI.index(atleta_row["profilo"]) if atleta_row["profilo"] in PROFILI else 0,
                key=f"profilo_existing_{atleta_id_esistente}",
            )

        else:
            if modalita == "Nuova analisi per atleta già esistente" and db_atleti.empty:
                st.warning("Non sono presenti atleti in archivio. Verrà creato un nuovo atleta.")

            c1, c2, c3, c4 = st.columns([2, 2, 1, 2])
            cognome = c1.text_input("Cognome", value="", key="cognome_new_input").strip()
            nome = c2.text_input("Nome", value="", key="nome_new_input").strip()
            altezza = c3.number_input("Altezza (cm)", 120, 230, 175, 1, key="altezza_new_input")
            profilo = c4.selectbox("Profilo atleta", PROFILI, key="profilo_new_input")

        data_visita = st.date_input("Data analisi", value=date.today(), key="data_visita_input")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("📊 1. Stato attuale")
        p_att = st.number_input("Peso attuale (kg)", 40.0, 150.0, 70.0, 0.1, key="p_att_input")
        fm_att = st.number_input("FM attuale (%)", 3.0, 45.0, 15.0, 0.1, key="fm_att_input")
        tipo_test = st.selectbox("Tipo test FTP", TIPI_TEST, key="tipo_test_input")
        val_test = st.number_input("Watt test / FTP manuale", 50, 700, 250, 1, key="val_test_input")
        ftp_att = BioPerformance.calculate_ftp(tipo_test, val_test)
        lthr = st.number_input("FTHR / LTHR (bpm)", 80, 220, 160, 1, key="lthr_input")

    with col2:
        st.subheader("🎯 2. Target")
        p_tar = st.number_input("Peso target (kg)", 40.0, 150.0, 68.0, 0.1, key="p_tar_input")
        fm_tar = st.number_input("FM target (%)", 3.0, 40.0, 10.0, 0.1, key="fm_tar_input")
        ftp_tar = st.number_input("FTP target (W)", 50, 700, 280, 1, key="ftp_tar_input")

    with col3:
        st.subheader("🏔️ 3. Scenario salita")
        dist = st.number_input("Km salita", 0.1, 50.0, 10.0, 0.1, key="dist_input")
        grad = st.number_input("Pendenza media (%)", 0.0, 25.0, 7.0, 0.1, key="grad_input")
        bike = st.number_input("Peso bici (kg)", 5.0, 20.0, 7.5, 0.1, key="bike_input")

    if st.button("🚀 ELABORA E STAMPA OUTPUT", use_container_width=True):
        if not nome or not cognome:
            st.error("Inserire nome e cognome prima di elaborare.")
            st.stop()

        r = make_report_dict(
            nome, cognome, altezza, profilo, data_visita.isoformat(),
            p_att, fm_att, ftp_att, lthr, p_tar, fm_tar, ftp_tar,
            dist, grad, bike, tipo_test=tipo_test,
        )
        r["atleta_id_esistente"] = atleta_id_esistente
        st.session_state["rep"] = r

    if "rep" in st.session_state:
        r = st.session_state["rep"]

        st.divider()
        st.subheader("🧬 Analisi Biometrica e Funzionale")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Peso", f"{r['peso_att']:.1f} kg", f"Target: {r['peso_tar']:.1f} kg")
        c1.write(f"**BMI:** {r['bmi_att']:.1f} → **{r['bmi_tar']:.1f}**")

        fm_kg_att = r["peso_att"] * (r["fm_att"] / 100)
        fm_kg_tar = r["peso_tar"] * (r["fm_tar"] / 100)
        c2.metric("FM %", f"{r['fm_att']:.1f} %", f"Target: {r['fm_tar']:.1f} %")
        c2.write(f"**Massa grassa:** {fm_kg_att:.1f} kg → **{fm_kg_tar:.1f} kg**")

        c3.metric("FTP attuale", f"{r['ftp_att']:.0f} W", f"Target: {r['ftp_tar']:.0f} W")
        c3.write(f"**Protocollo:** {r['tipo_test']}")

        c4.metric("Rapporto W/kg", f"{r['wkg_att']:.2f}", f"Target: {r['wkg_tar']:.2f}")
        c4.write(f"**Delta:** {r['wkg_delta']:+.2f} W/kg")

        st.subheader("🏔️ Analisi Scenario Salita")
        s1, s2 = st.columns(2)
        s1.info(f"**Input:** {r['dist']:.1f} km | {r['grad']:.1f}% | Bici {r['bike']:.1f} kg")
        s2.success(f"**Tempo attuale:** {r['tempo_att']:.2f} min  \n**Tempo target:** {r['tempo_tar']:.2f} min  \n**Differenza:** {r['tempo_delta']:+.2f} min")

        st.subheader("⚡ Zone di Potenza Coggan - FTP attuale")
        st.table(pd.DataFrame(r["zones_power_att"], columns=["Zona", "Watt Min", "Watt Max"]))

        st.subheader("🎯 Zone di Potenza Coggan - FTP target")
        st.table(pd.DataFrame(r["zones_power_tar"], columns=["Zona", "Watt Min", "Watt Max"]))

        st.subheader("❤️ Zone Cardiache su FTHR / LTHR")
        st.table(pd.DataFrame(r["zones_hr"], columns=["Zona", "BPM Min", "BPM Max"]))

        st.subheader("🏁 Benchmark di Categoria")
        st.table(BioPerformance.benchmarks())

        save_col, pdf_col = st.columns(2)

        with save_col:
            if st.button("💾 SALVA IN ARCHIVIO", use_container_width=True):
                salva_visita(r)
                if r.get("atleta_id_esistente") is None:
                    st.success(f"Nuovo atleta {r['nome']} {r['cognome']} creato e valutazione salvata correttamente.")
                else:
                    st.success(f"Nuova analisi di {r['nome']} {r['cognome']} salvata correttamente in archivio.")

        with pdf_col:
            st.download_button(
                "📄 SCARICA PDF COMPLETO",
                data=create_pdf(r),
                file_name=f"Analisi_{r['cognome']}_{r['nome']}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )


# =========================================================
# ARCHIVIO & EDIT
# =========================================================
elif menu == "📂 Archivio & Edit":

    # --- Inizializza stato navigazione archivio ---
    if "archivio_atleta_id" not in st.session_state:
        st.session_state["archivio_atleta_id"] = None

    atleti = get_all_atleti()

    if atleti.empty:
        st.info("Nessun atleta presente in archivio.")
        st.stop()

    atleti = atleti.copy()
    atleti["label"] = atleti.apply(
        lambda x: f"{x['id']} - {x['cognome']} {x['nome']}",
        axis=1
    )

    # =====================================================
    # VISTA LISTA ATLETI
    # =====================================================
    if st.session_state["archivio_atleta_id"] is None:
        st.header("🗄️ Gestione Archivio")
        st.subheader("🔎 Cerca atleta")

        ricerca_atleta = st.text_input(
            "Digita nome o cognome",
            value="",
            placeholder="Es. Rossi, Mario, Bramard...",
            key="ricerca_atleta_archivio"
        ).strip().lower()

        if ricerca_atleta:
            atleti_filtrati = atleti[
                atleti["nome"].astype(str).str.lower().str.contains(ricerca_atleta, na=False) |
                atleti["cognome"].astype(str).str.lower().str.contains(ricerca_atleta, na=False)
            ]
        else:
            atleti_filtrati = atleti

        if atleti_filtrati.empty:
            st.warning("Nessun atleta trovato con questa ricerca.")
            st.stop()

        st.markdown(f"**{len(atleti_filtrati)} atleti trovati**")
        st.divider()

        for _, row in atleti_filtrati.iterrows():
            col_nome, col_btn = st.columns([4, 1])
            col_nome.markdown(f"**{row['cognome']} {row['nome']}**  \n{row['profilo']} | {row['altezza']} cm")
            if col_btn.button("Apri →", key=f"open_{row['id']}", use_container_width=True):
                st.session_state["archivio_atleta_id"] = int(row["id"])
                st.rerun()

        st.stop()

    # =====================================================
    # VISTA SCHEDA ATLETA
    # =====================================================
    atleta_id = st.session_state["archivio_atleta_id"]

    if st.button("← Torna all'archivio", use_container_width=False):
        st.session_state["archivio_atleta_id"] = None
        st.rerun()

    atleta_row = atleti[atleti["id"] == atleta_id].iloc[0]

    st.header(f"👤 {atleta_row['cognome']} {atleta_row['nome']}")
    st.caption(f"{atleta_row['profilo']} | {atleta_row['altezza']} cm")

    st.divider()
    st.subheader("🧾 Modifica dati anagrafici atleta")
    edit_cognome = st.text_input("Cognome atleta", value=str(atleta_row["cognome"]), key=f"edit_cognome_{atleta_id}")
    edit_nome = st.text_input("Nome atleta", value=str(atleta_row["nome"]), key=f"edit_nome_{atleta_id}")
    edit_altezza = st.number_input("Altezza atleta (cm)", 120, 230, int(atleta_row["altezza"]) if pd.notna(atleta_row["altezza"]) else 175, 1, key=f"edit_altezza_{atleta_id}")
    edit_profilo = st.selectbox("Profilo atleta", PROFILI, index=PROFILI.index(atleta_row["profilo"]) if atleta_row["profilo"] in PROFILI else 0, key=f"edit_profilo_{atleta_id}")

    if st.button("💾 AGGIORNA ANAGRAFICA ATLETA", use_container_width=True):
        if not edit_nome.strip() or not edit_cognome.strip():
            st.error("Nome e cognome non possono essere vuoti.")
            st.stop()
        aggiorna_atleta(atleta_id, edit_nome, edit_cognome, edit_altezza, edit_profilo)
        st.success("Anagrafica atleta aggiornata correttamente.")
        st.rerun()

    visite = get_visite(atleta_id)

    st.divider()
    st.subheader("📋 Visite salvate")

    if visite.empty:
        st.warning("Nessuna visita registrata per questo atleta.")
    else:
        for _, v in visite.iterrows():
            with st.expander(f"📅 {v['data']}  —  FTP: {int(v['ftp'])} W  |  W/kg: {v['wkg_att']:.2f}"):
                st.markdown(
                    f"**Peso:** {v['peso']:.1f} kg &nbsp;|&nbsp; **FM:** {v['fm']:.1f} % &nbsp;|&nbsp; **FTP:** {int(v['ftp'])} W &nbsp;|&nbsp; **LTHR:** {int(v['lthr'])} bpm  \n"
                    f"**Peso target:** {v['peso_t']:.1f} kg &nbsp;|&nbsp; **FM target:** {v['fm_t']:.1f} % &nbsp;|&nbsp; **FTP target:** {int(v['ftp_t'])} W  \n"
                    f"**W/kg:** {v['wkg_att']:.2f} → {v['wkg_tar']:.2f} &nbsp;|&nbsp; **Tempo att/tar:** {v['t_att']:.1f} / {v['t_tar']:.1f} min  \n"
                    f"**Km:** {v['dist_km']:.1f} &nbsp;|&nbsp; **Pendenza:** {v['grad']:.1f}% &nbsp;|&nbsp; **Bici:** {v['bike_w']:.1f} kg"
                )

        st.divider()
        st.subheader("✏️ Modifica visita salvata e sovrascrivi")

        visita_id = st.selectbox("Seleziona ID visita da modificare", visite["id"].tolist(), key="visita_modifica_id")
        visita_sel = visite[visite["id"] == visita_id].iloc[0]

        st.markdown("**Stato attuale**")
        nuovo_peso = st.number_input("Peso attuale (kg)", 40.0, 150.0, float(visita_sel["peso"]), 0.1, key=f"edit_peso_{visita_id}")
        nuova_fm = st.number_input("FM attuale (%)", 3.0, 45.0, float(visita_sel["fm"]), 0.1, key=f"edit_fm_{visita_id}")
        nuova_ftp = st.number_input("FTP attuale (W)", 50, 700, int(visita_sel["ftp"]), 1, key=f"edit_ftp_{visita_id}")
        nuova_lthr = st.number_input("FTHR / LTHR (bpm)", 80, 220, int(visita_sel["lthr"]), 1, key=f"edit_lthr_{visita_id}")

        st.markdown("**Target**")
        nuovo_peso_t = st.number_input("Peso target (kg)", 40.0, 150.0, float(visita_sel["peso_t"]), 0.1, key=f"edit_peso_t_{visita_id}")
        nuova_fm_t = st.number_input("FM target (%)", 3.0, 40.0, float(visita_sel["fm_t"]), 0.1, key=f"edit_fm_t_{visita_id}")
        nuova_ftp_t = st.number_input("FTP target (W)", 50, 700, int(visita_sel["ftp_t"]), 1, key=f"edit_ftp_t_{visita_id}")

        st.markdown("**Scenario salita**")
        nuova_dist = st.number_input("Km salita", 0.1, 50.0, float(visita_sel["dist_km"]), 0.1, key=f"edit_dist_{visita_id}")
        nuova_grad = st.number_input("Pendenza media (%)", 0.0, 25.0, float(visita_sel["grad"]), 0.1, key=f"edit_grad_{visita_id}")
        nuova_bike = st.number_input("Peso bici (kg)", 5.0, 20.0, float(visita_sel["bike_w"]), 0.1, key=f"edit_bike_{visita_id}")

        r_edit = make_report_dict(
            edit_nome, edit_cognome, edit_altezza, edit_profilo, visita_sel["data"],
            nuovo_peso, nuova_fm, nuova_ftp, nuova_lthr,
            nuovo_peso_t, nuova_fm_t, nuova_ftp_t,
            nuova_dist, nuova_grad, nuova_bike,
            tipo_test="Archivio",
        )

        st.info(
            f"Nuovo W/kg attuale: **{r_edit['wkg_att']:.2f}** | "
            f"Nuovo W/kg target: **{r_edit['wkg_tar']:.2f}** | "
            f"Tempo attuale: **{r_edit['tempo_att']:.2f} min** | "
            f"Tempo target: **{r_edit['tempo_tar']:.2f} min**"
        )

        st.write("**Zone Coggan aggiornate - FTP attuale**")
        st.table(pd.DataFrame(r_edit["zones_power_att"], columns=["Zona", "Watt Min", "Watt Max"]))
        st.write("**Zone cardiache aggiornate**")
        st.table(pd.DataFrame(r_edit["zones_hr"], columns=["Zona", "BPM Min", "BPM Max"]))

        update_col, print_col = st.columns(2)
        with update_col:
            if st.button("💾 AGGIORNA VISITA SELEZIONATA", use_container_width=True):
                aggiorna_visita(
                    int(visita_id), nuovo_peso, nuova_fm, nuova_ftp, nuova_lthr,
                    nuovo_peso_t, nuova_fm_t, nuova_ftp_t,
                    nuova_dist, nuova_grad, nuova_bike,
                )
                st.success("Visita aggiornata e sovrascritta correttamente.")
                st.rerun()

        with print_col:
            st.download_button(
                "📄 RISTAMPA PDF VISITA SELEZIONATA",
                data=create_pdf(r_edit),
                file_name=f"Analisi_{edit_cognome}_{edit_nome}_visita_{visita_id}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

        # ---------------------------------------------------------
        # COMPARAZIONE TRA DUE VISITE
        # ---------------------------------------------------------
        if len(visite) >= 2:
            st.divider()
            st.subheader("📈 Comparazione tra due analisi")
            st.write("Seleziona due visite dello stesso atleta e imposta una salita comune.")

            visita_1_id = st.selectbox("Analisi iniziale", visite["id"].tolist(), key="comparazione_visita_1")
            visita_2_id = st.selectbox("Analisi successiva", visite["id"].tolist(), key="comparazione_visita_2")

            if visita_1_id == visita_2_id:
                st.warning("Selezionare due visite diverse per effettuare la comparazione.")
            else:
                v1 = visite[visite["id"] == visita_1_id].iloc[0]
                v2 = visite[visite["id"] == visita_2_id].iloc[0]

                st.markdown("### 🏔️ Salita comune per la comparazione")
                comp_dist = st.number_input("Km salita comparativa", 0.1, 100.0, float(v2["dist_km"]) if pd.notna(v2["dist_km"]) else 10.0, 0.1, key="comp_dist")
                comp_grad = st.number_input("Pendenza media comparativa (%)", 0.0, 25.0, float(v2["grad"]) if pd.notna(v2["grad"]) else 7.0, 0.1, key="comp_grad")
                comp_bike = st.number_input("Peso bici comparativo (kg)", 5.0, 20.0, float(v2["bike_w"]) if pd.notna(v2["bike_w"]) else 7.5, 0.1, key="comp_bike")

                peso_1 = float(v1["peso"]); fm_1 = float(v1["fm"]); ftp_1 = float(v1["ftp"])
                peso_2 = float(v2["peso"]); fm_2 = float(v2["fm"]); ftp_2 = float(v2["ftp"])
                wkg_1 = ftp_1 / peso_1 if peso_1 else 0
                wkg_2 = ftp_2 / peso_2 if peso_2 else 0
                tempo_1 = BioPerformance.estimate_time(ftp_1, peso_1, comp_dist, comp_grad, comp_bike)
                tempo_2 = BioPerformance.estimate_time(ftp_2, peso_2, comp_dist, comp_grad, comp_bike)

                delta_peso = peso_2 - peso_1
                delta_fm = fm_2 - fm_1
                delta_ftp = ftp_2 - ftp_1
                delta_wkg = wkg_2 - wkg_1
                delta_tempo = tempo_2 - tempo_1
                perc_ftp = (delta_ftp / ftp_1 * 100) if ftp_1 else 0
                perc_wkg = (delta_wkg / wkg_1 * 100) if wkg_1 else 0
                perc_tempo = (delta_tempo / tempo_1 * 100) if tempo_1 else 0

                st.markdown("### 📊 Risultato comparativo")
                st.metric("Peso", f"{peso_2:.1f} kg", f"{delta_peso:+.1f} kg")
                st.metric("FM %", f"{fm_2:.1f} %", f"{delta_fm:+.1f} %")
                st.metric("FTP", f"{ftp_2:.0f} W", f"{delta_ftp:+.0f} W / {perc_ftp:+.1f}%")
                st.metric("W/kg", f"{wkg_2:.2f}", f"{delta_wkg:+.2f} / {perc_wkg:+.1f}%")

                st.markdown("### 🏔️ Comparazione sulla stessa salita")
                st.info(f"**Analisi iniziale** — {v1['data']}  \nPeso: {peso_1:.1f} kg | FTP: {ftp_1:.0f} W | W/kg: {wkg_1:.2f} | Tempo: **{tempo_1:.2f} min**")
                st.success(f"**Analisi successiva** — {v2['data']}  \nPeso: {peso_2:.1f} kg | FTP: {ftp_2:.0f} W | W/kg: {wkg_2:.2f} | Tempo: **{tempo_2:.2f} min**")

                if delta_tempo < 0:
                    st.success(f"**Esito: MIGLIORAMENTO** — Tempo ridotto di {abs(delta_tempo):.2f} min ({abs(perc_tempo):.1f}%).")
                elif delta_tempo > 0:
                    st.error(f"**Esito: PEGGIORAMENTO** — Tempo aumentato di {delta_tempo:.2f} min ({perc_tempo:.1f}%).")
                else:
                    st.info("**Esito: INVARIATO** — Tempo stimato invariato.")

                st.markdown("### 🧬 Interpretazione sintetica")
                if delta_tempo < 0 and delta_wkg > 0:
                    st.success("La seconda analisi mostra un miglioramento prestativo coerente: incremento del rapporto W/kg e riduzione del tempo stimato sulla salita comparativa.")
                elif delta_tempo < 0 and delta_wkg <= 0:
                    st.warning("La seconda analisi mostra un miglioramento del tempo stimato, ma senza incremento del rapporto W/kg. Verificare l'influenza della riduzione ponderale o dei parametri della simulazione.")
                elif delta_tempo > 0 and delta_wkg < 0:
                    st.error("La seconda analisi evidenzia un peggioramento prestativo: riduzione del rapporto W/kg e aumento del tempo stimato sulla salita comparativa.")
                else:
                    st.info("La variazione è contenuta o mista. Interpretare il dato considerando peso, FTP, massa grassa e coerenza del protocollo di test.")
        else:
            st.info("Per effettuare una comparazione sono necessarie almeno due visite salvate per lo stesso atleta.")

    st.divider()
    st.subheader("🗑️ Eliminazione dati")
    d1, d2 = st.columns(2)

    with d1:
        if st.button("🗑️ ELIMINA ATLETA E TUTTE LE VISITE", use_container_width=True):
            with get_connection() as conn:
                conn.execute("DELETE FROM visite WHERE atleta_id=?", (atleta_id,))
                conn.execute("DELETE FROM atleti WHERE id=?", (atleta_id,))
                conn.commit()
            st.success("Atleta eliminato correttamente.")
            st.session_state["archivio_atleta_id"] = None
            st.rerun()

    with d2:
        if not visite.empty:
            visita_da_eliminare = st.selectbox("Seleziona visita da eliminare", visite["id"].tolist(), key="visita_da_eliminare")
            if st.button("🗑️ ELIMINA SOLO VISITA", use_container_width=True):
                with get_connection() as conn:
                    conn.execute("DELETE FROM visite WHERE id=?", (int(visita_da_eliminare),))
                    conn.commit()
                st.success("Visita eliminata correttamente.")
                st.rerun()
