# Prenotazioni Pilates Reformer - Body Center

Gestionale interno in Streamlit per Danilo + socia.

## Funzioni
- Inserimento prenotazioni da parte dello staff.
- Capienza 4 persone per lezione.
- Lista d'attesa.
- Vista settimanale.
- Archivio esportabile CSV.
- Salvataggio su GitHub tramite file `data/bookings.json`.

## Orari inclusi
- Lunedì: 8:30, 9:30, 10:30, 17:00, 18:00, 19:00
- Martedì: 9:30, 10:30, 11:30, 12:45, 14:30, 19:00
- Mercoledì: 8:30, 9:30, 10:30, 11:30, 12:45, 14:30, 15:30, 16:30, 17:30, 18:30
- Giovedì: 17:00, 18:00, 19:00
- Venerdì: 14:00, 15:00, 16:00, 17:00, 18:00, 19:00

## Deploy rapido
1. Crea repo GitHub: `prenotazioni-pilates-bodycenter`.
2. Carica:
   - `app.py`
   - `requirements.txt`
   - `data/bookings.json`
3. Vai su Streamlit Community Cloud e crea nuova app dal repo.
4. In Secrets incolla:
   APP_PASSWORD = "tua-password"
   GITHUB_TOKEN = "token-github"
   GITHUB_REPO = "username/prenotazioni-pilates-bodycenter"
   GITHUB_BRANCH = "main"

## Token GitHub
Serve un token con permesso di lettura/scrittura sui Contents del repository.
Consiglio: repo privato.
