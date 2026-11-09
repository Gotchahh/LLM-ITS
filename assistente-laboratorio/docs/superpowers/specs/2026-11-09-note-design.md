# Note con API FastAPI — specifica di design (Lezione 5, feature 4)

> Stato: approvata dall'utente il 09/11/2026 (scritta dall'assistente, domande saltate su richiesta). Branch
> `feature/note`, nato da `dev` (`06c0bb1`: calcolatrice, convertitore, giorni e scadenze). Tutto ciò che qui non è
> detto resta come nelle specifiche precedenti.

## Intento e perché
In laboratorio serve dire all'assistente «segnati che il microscopio 2 va calibrato» e chiedergli più tardi «che
note ho?». Il modello non ha memoria tra le sessioni: le note le salva e le legge un servizio separato.

È la feature 4 di 6, nella modalità **API HTTP con FastAPI** (decisa nel piano della Lezione 5). Il ciclo del grafo
non cambia: richiesta del modello → esecuzione (chiamata HTTP) → `ToolMessage` correlato → nuova chiamata al modello.

### Perché un'API (e non funzione nel grafo o MCP)
Le note sono **dati con stato** che devono sopravvivere alla chat e appartenere a un servizio con un proprio ciclo di
vita (in Docker un container separato, con il suo volume). Un'API HTTP è il modo più semplice per esporre quel
servizio a qualsiasi client, e mostra la terza modalità del corso. La cronologia della conversazione resta senza
persistenza: persistono solo le note, salvate su richiesta esplicita.

## Obiettivi
1. «Segnati che …» → `salva_nota`; «che note ho?» / «ho note sul microscopio?» → `elenca_note`; «cancella la nota 3»
   → `cancella_nota`. Ogni chiamata visibile nei log (`nodo_strumenti: <strumento> -> ...`).
2. Le note restano dopo la chiusura dell'assistente e dopo il riavvio del servizio (file SQLite; in Docker un volume).
3. Errori (servizio spento, nota inesistente, testo vuoto o troppo lungo) → `ToolMessage` d'errore in italiano; il
   modello dice che non si può fare e perché, senza inventare note.
4. Nulla si rompe: gli strumenti esistenti, `/log`, «Ragionando...», tutti i test esistenti verdi.
5. Avvio locale (due terminali) e con Docker Compose; README e `CLAUDE.md` aggiornati con soli comandi verificati.

## Non-obiettivi
Modifica di una nota, categorie, scadenze o promemoria, ricerca per data, più utenti, autenticazione, interfaccia
web, persistenza della cronologia della chat, workflow e RAG.

## Anti-obiettivi
- Una nota «salvata» senza la chiamata riuscita all'API (il modello che dice «fatto» da solo).
- Note elencate che non vengono dal servizio.
- Il servizio spento che blocca l'avvio della chat o fa uscire l'assistente con un traceback.
- Messaggi d'errore in inglese o tecnici (422 di FastAPI, traccia di `urllib`) restituiti al modello.
- `openai`, `httpx`, `pydantic` o `fastapi` importati nel pacchetto `assistente/`.

## Vincoli (da CLAUDE.md)
Codice sincrono, moduli piccoli; nel pacchetto `assistente/` il wrapper HTTP usa `urllib`. Dipendenze nuove solo
`fastapi` e `uvicorn`, con versione fissata e verificata su Python 3.14.7 (uvicorn 0.54.0 è già installato come
dipendenza di `mcp`). SQLite con il modulo `sqlite3` della libreria standard. Lavoro solo in `assistente-laboratorio/`.

## Comportamento

### Servizio `note_api/` (pacchetto separato, non importa nulla da `assistente/`)
- Avvio: `python -m note_api` (uvicorn). Variabili: `NOTE_DB` (file SQLite, default `dati/note.db`, cartella creata
  se manca), `NOTE_HOST` (default `127.0.0.1`), `NOTE_PORT` (default `8000`).
- Tabella `note(numero INTEGER PRIMARY KEY AUTOINCREMENT, testo TEXT, creata TEXT)`; `creata` in ISO 8601 UTC.
  I numeri non vengono riusati dopo una cancellazione.
- Endpoint (JSON):
  | Metodo e percorso | Effetto | Risposta |
  |---|---|---|
  | `GET /salute` | controllo | `200 {"stato": "ok"}` |
  | `POST /note` `{"testo": ...}` | salva | `201 {"numero", "testo", "creata"}` |
  | `GET /note?cerca=...` | elenca, dalla più recente; `cerca` facoltativo, senza distinzione di maiuscole | `200 {"totale", "note": [...]}` (al massimo 20) |
  | `DELETE /note/{numero}` | cancella | `200` con la nota cancellata; `404` se non esiste |
- Testo: spazi esterni tolti, da 1 a 500 caratteri; altrimenti `400`. Ogni errore ha il corpo `{"errore": "<messaggio
  in italiano>"}`, anche quelli di validazione di FastAPI (gestore apposito invece del 422 standard).

### Strumenti nell'assistente (`assistente/note.py`, wrapper con `urllib`)
| Strumento | Parametri | Risultato (esempio) |
|---|---|---|
| `salva_nota` | `testo` | «nota 3 salvata: «calibrare il microscopio 2»» |
| `elenca_note` | `cerca` facoltativo (vuoto = tutte) | «2 note: n. 3 (9/11/2026 10:15) calibrare il microscopio 2; n. 1 (...) ...»; «nessuna nota» / «nessuna nota contiene «x»»; oltre 20: «mostrate le 20 più recenti su N» |
| `cancella_nota` | `numero` (intero) | «nota 3 cancellata: «...»» |

- Indirizzo del servizio solo da `NOTE_API_URL` (default `http://localhost:8000`, in `.env.example`; in Compose
  `http://note:8000`). Timeout 5 s.
- Data delle note mostrata nel fuso `APP_TIMEZONE`.
- Errori come `ToolException` in italiano: servizio non raggiungibile («servizio note non raggiungibile a <url>:
  avviarlo con python -m note_api»), nota inesistente (dal `404`), testo non valido (dal `400`), argomenti sbagliati.
- *(scelta dell'assistente)* All'avvio l'assistente prova `GET /salute`: se il servizio non risponde scrive un
  avviso nel log e **parte comunque**; gli strumenti delle note risponderanno con l'errore sopra.

### Prompt di sistema
Una regola in più: per salvare, elencare, cercare o cancellare note chiamare `salva_nota`, `elenca_note`,
`cancella_nota`; per cancellare «la nota sul …» prima `elenca_note` per trovare il numero; non dire mai che una nota
è salvata o cancellata senza il risultato dello strumento. Le regole esistenti restano.

### Docker Compose
Nuovo servizio `note` (stessa immagine, comando `python -m note_api`, `NOTE_HOST=0.0.0.0`, volume `note-dati` su
`/app/dati`); `assistente` con `depends_on: note` e `NOTE_API_URL=http://note:8000`. Si continua a usare
`docker compose run` per l'assistente; `docker compose down` ferma anche `note`, il volume resta.
`dati/` esclusa da Git e dal contesto di build.

## Verifiche
- **Test automatici senza modello**: servizio con `TestClient` di FastAPI su un DB temporaneo (salvataggio, elenco,
  ricerca, limite 20, cancellazione, 404, testi non validi, errori in italiano, persistenza dopo la riapertura del
  DB); wrapper e strumenti contro un vero uvicorn in un thread su porta libera (successi, errori HTTP, servizio
  spento); giro nel grafo con modello finto (successo ed errore); avviso all'avvio con servizio spento.
- **Prove reali con gemma** (servizio avviato dal test su DB temporaneo): «Segnati che il microscopio 2 va
  calibrato» → `salva_nota`; poi «Che note ho?» → `elenca_note` e «microscopio» nella risposta.
- **Pipe** locale (servizio in un secondo processo) e **Docker** (`compose build`, `run -T`): salvataggio, poi una
  nuova sessione che elenca la nota salvata (prova della persistenza).

## Lasciato a chi costruisce
Nomi interni, testo esatto di descrizioni, risultati e messaggi; organizzazione dei test; come attendere che uvicorn
sia pronto nei test.
