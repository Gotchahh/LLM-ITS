# Assistente del laboratorio

Progetto del corso «Deep Learning e LLM: costruire chatbot e agenti».
La cartella del progetto è `assistente-laboratorio/`; i comandi si eseguono da lì, in PowerShell.

## Obiettivo
Un'applicazione da terminale in Python che conversa con un modello locale e:
- organizza il flusso in un grafo LangGraph esplicito (stato, nodi, instradamento riconoscibili);
- usa un modello servito da LM Studio, che resta sul computer host;
- conserva la cronologia della conversazione per la durata della sessione nella CLI; dallo step 7 della
  Lezione 6 le chat dell'interfaccia web sono salvate dal back-end in PostgreSQL;
- offre uno strumento orologio con fuso orario esplicito, richiesto dal modello tramite tool calling
  ed eseguito davvero dal programma;
- dalla Lezione 5 offre altri strumenti, eseguiti con lo stesso ciclo del grafo (richiesta del modello →
  esecuzione → `ToolMessage` correlato → nuova chiamata al modello) e ottenuti con tre modalità:
  funzione Python nel grafo, API HTTP con FastAPI, server MCP;
- dalla Lezione 6 evolve in nove step, uno alla volta e in ordine: router, revisore e riassunto della
  cronologia (nodi LLM aggiuntivi nel grafo); resource e prompt MCP; agente come servizio HTTP, back-end con
  PostgreSQL, front-end web di chat, Docker Compose con un container per componente;
- si avvia anche con Docker Compose.

## Confini
- Implementare solo i requisiti concordati. Lezione 5 (conclusa): calcolatrice, convertitore, giorni e
  scadenze, note, catalogo, ciascuna con una delle tre modalità (funzione nel grafo, API FastAPI, MCP);
  il meteo è stato abbandonato. L'orologio resta locale.
- Lezione 6: gli step si fanno uno per volta, nell'ordine delle slide, ciascuno su un'implementazione
  funzionante e verificata dello step precedente; estendere senza riscrivere e non anticipare gli step
  successivi. Non anticipare workflow e RAG.
- Interfaccia web ammessa dallo step 8 (front-end), con la tecnologia scelta nella specifica dello step;
  PostgreSQL ammesso dallo step 7. Niente servizi cloud né framework non concordati.
- Lavorare solo dentro `assistente-laboratorio/`. La repository contiene altre lezioni:
  non leggerle per copiarne il codice e non modificarle.
- Lavorare nel branch `feature/<nome>` della feature in corso; nessun worktree.

## Struttura
- `assistente/`: pacchetto avviato con `python -m assistente`.
  - `config.py`: variabili d'ambiente, validazione, configurazione dei log.
  - `strumenti.py`: strumento `ora_corrente` (fuso facoltativo, istante iniettabile).
  - `calendario.py`: strumenti `giorni_tra`, `sposta_data`, `giorno_settimana`, `pasqua` (oggi dal fuso configurato,
    istante iniettabile).
  - `convertitore.py`: strumento `converti` (lunghezze, pesi, temperature; logica pura e fabbrica dello strumento).
  - `modello.py`: `ChatOpenAI` verso LM Studio e controllo dell'elenco modelli all'avvio.
  - `grafo.py`: stato, nodi e instradamento; `costruisci_grafo(modello, strumenti, ambito, modello_router, revisore, revisioni_max)`.
  - `router.py`: schema della decisione del router, messaggi da classificare, rifiuto; il prompt del router è
    `ambito.txt` (variabile `AMBITO_FILE`).
  - `revisore.py`: schema della valutazione del revisore (motivo prima del verdetto), indicazione per l'agente;
    istruzioni in `revisore.txt` (`REVISORE_FILE`), limite `REVISIONI_MAX`.
  - `cli.py`, `__main__.py`: ciclo di chat, cronologia, comandi `/esci` e `/log`, scritta «Ragionando...».
  - `note.py`: strumenti `salva_nota`, `elenca_note`, `cancella_nota`, wrapper `urllib` verso il servizio delle
    note (`NOTE_API_URL`).
  - `client_mcp.py`: discovery dei server MCP (`SERVER_MCP`: calcolatrice e catalogo) e strumenti MCP resi sincroni
    (unico modulo con `asyncio` e `langchain_mcp_adapters`).
- `calcolatrice_mcp/`: server MCP della calcolatrice (`calcolo.py` logica pura, `server.py` FastMCP su stdio),
  avviato dall'assistente con `python -m calcolatrice_mcp`; non importa nulla da `assistente/`.
- `catalogo_mcp/`: server MCP del catalogo degli apparecchi (`apparecchi.py` logica pura, `apparecchi.json` dati,
  `server.py` FastMCP su stdio con tre strumenti), avviato con `python -m catalogo_mcp`; non importa da `assistente/`.
- `note_api/`: servizio FastAPI delle note (`archivio.py` SQLite, `server.py` endpoint), avviato con
  `python -m note_api` (`NOTE_DB`, `NOTE_HOST`, `NOTE_PORT`); non importa nulla da `assistente/`. `dati/` fuori da Git.
- `tests/`: test automatici senza modello; `test_reale.py` contiene le prove con LM Studio (marcatore `reale`).
- `docs/superpowers/`: specifica e piano.
- `Dockerfile`, `compose.yaml`, `.dockerignore`: avvio con Docker Compose.
- `.env.example` (esempio senza credenziali), `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`.

## Scelte tecniche
- Python 3.14.7 (`py -3.14 -m venv .venv`; immagine Docker `python:3.14.7-slim`). Si usa
  `.\.venv\Scripts\python.exe` direttamente, senza `Activate.ps1`.
- Codice sincrono e moduli piccoli, con una separazione semplice tra
  grafo, collegamento al modello, strumenti e interfaccia da terminale; l'asincronia richiesta dalle
  librerie MCP resta confinata nel modulo client MCP.
- LM Studio sull'host, raggiunto tramite la sua API compatibile con OpenAI.
- Indirizzo del server e identificativo del modello solo da variabili d'ambiente
  (`LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL`; inoltre `APP_TIMEZONE`, `LOG_LEVEL`, `NOTE_API_URL`, `AMBITO_FILE`, `REVISORE_FILE` e `REVISIONI_MAX`).
  L'identificativo è quello restituito dal server (`GET /v1/models`), mai inventato.
- Un file di configurazione di esempio senza credenziali; il file reale (`.env`) resta fuori da Git.
- Docker Compose per l'applicazione; LM Studio non va containerizzato. Dallo step 9 della Lezione 6 un
  container per componente (front-end, back-end, agente, PostgreSQL); credenziali del database solo in `.env`.
- Nodi LLM aggiuntivi (router, revisore, riassunto) usano lo stesso modello di LM Studio con prompt di sistema
  diversi; i testi che li configurano (per esempio l'ambito dell'agente) stanno in configurazione, non nel codice.
- Dipendenze motivate, concordate e con versioni fissate in `requirements.txt`; `pytest` solo in
  `requirements-dev.txt`. Le dipendenze di una feature si aggiungono solo con quella feature, con versione
  fissata e verificata su Python 3.14.7.
- Nel pacchetto `assistente/` non si importano direttamente `openai`, `httpx` né `pydantic` (eccezione: i
  tipi di `langchain_core`); il wrapper verso le API HTTP usa `urllib`.
- Comandi documentati anche per PowerShell (Windows).

## Comandi
- Installazione: `py -3.14 -m venv .venv`, poi `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`.
- Avvio: `.\.venv\Scripts\python.exe -m assistente` (per le note, prima `.\.venv\Scripts\python.exe -m note_api` in un
  secondo terminale).
- Test automatici (nessun modello; i `reale` sono esclusi di default): `.\.venv\Scripts\python.exe -m pytest`.
- Test reali (LM Studio attivo, `.env` compilato; richiedono diversi minuti):
  `.\.venv\Scripts\python.exe -m pytest -m reale -v`.
- Docker: `docker compose build`, poi `docker compose run --rm --name assistente-demo assistente`
  (si usa `run`, non `up`; con input da pipe `docker compose run --rm -T assistente`).
  La chat interattiva nel container (tastiera, `docker logs -f assistente-demo` da un secondo terminale) è una
  prova manuale: vedi la checklist del README.

## Metodo: Superpowers
- Usare le skill di Superpowers per brainstorming, specifica, piano, implementazione e verifica.
- Non scrivere codice prima che io abbia approvato la specifica e poi il piano.
- Salvare specifica e piano in `assistente-laboratorio/docs/superpowers/`.
- Procedere per incrementi piccoli, ciascuno verificato prima del commit.

## Test e verifiche
- Test automatici ripetibili che non richiedono un modello attivo (grafo, cronologia,
  instradamento, strumento con istante controllato).
- Prove reali con LM Studio e con Docker tenute separate e attivate esplicitamente.
- Una risposta simulata non dimostra che il modello locale sappia usare lo strumento.
- Server MCP/API e collegamenti testati senza modello (discovery, invocazione diretta, errori); la prova
  reale verifica che il modello scelga lo strumento giusto.
- Le prove da pipe si eseguono senza `PYTHONIOENCODING` (la shell di Claude la imposta), in una
  PowerShell pulita.
- Nel resoconto indicare che cosa è stato eseguito, con quale esito, e che cosa resta da provare.

## Git
- Conventional Commits in italiano, per esempio `feat(grafo): ...`, `test(strumenti): ...`,
  `docs: ...`.
- Branch: `main` contiene solo versioni complete e verificate; `dev` è il branch di integrazione; ogni
  feature va in `feature/<nome>`, creato da `dev` (per esempio `feature/calcolatrice`).
- Una feature finita, verificata e revisionata entra in `dev` con `git merge --no-ff`; `dev` entra in
  `main` con `--no-ff` solo quando lo dichiaro completo.
- Prima di ogni commit: `git status`, controllo del diff, staging selettivo dei soli file pertinenti.
- Mai versionare credenziali, `.env`, ambienti virtuali, cache o pesi dei modelli.
- Merge e push soltanto su mia richiesta.

## Documentazione
- Tenere aggiornato il README con configurazione, avvio, test e diagnosi, riportando solo
  comandi verificati.
- Aggiornare questo file quando cambiano convenzioni stabili (struttura, comandi di test,
  regole di lavoro), non per annotare l'avanzamento.
