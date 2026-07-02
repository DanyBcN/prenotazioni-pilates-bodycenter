# AGENTS.md

Regole operative per lavorare su questo progetto.

## Vincoli sui dati
- Non modificare mai `data/bookings.json` salvo richiesta esplicita dell'utente.
- Non committare backup locali, file temporanei, cache Python o secrets.
- `__pycache__/`, `*.pyc`, `.streamlit/secrets.toml` e `data/backups/` devono restare esclusi dal versionamento.

## Runtime e struttura
- Non usare patch runtime in `sitecustomize.py` o `usercustomize.py`.
- Mantieni `app.py` come entrypoint principale dell'app.
- Mantieni il planning fisso a 92 giorni, salvo richiesta esplicita.

## Verifiche obbligatorie
- Eseguire sempre `python -m py_compile app.py` prima di consegnare modifiche.
- Eseguire sempre `python -m unittest discover -s tests` prima di consegnare modifiche.
- Prima del commit controllare sempre `git status`.

## UI e comportamento
- Mantenere l'app leggibile e usabile sia da PC sia da telefono.
- Mantenere gli utenti previsti:
  - BodyCenter: admin
  - Grazia: istruttrice
  - Alice: istruttrice
- Rispettare la gestione esistente di omaggi, incassi e quota 40/60.
- Non cambiare funzionalita o flussi senza richiesta esplicita.
