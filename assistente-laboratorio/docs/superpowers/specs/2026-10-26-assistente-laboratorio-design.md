# Assistente del laboratorio — specifica di design (Lezione 4)

> Stato: approvata dall'utente il 26/10/2026, al termine del brainstorming con Superpowers.

## Intento e perché
Applicazione Python da terminale che conversa con un modello locale servito da LM Studio, con il flusso
organizzato in un grafo LangGraph esplicito e uno strumento orologio richiesto dal modello tramite tool
calling ed eseguito davvero dal programma. È la base su cui le prossime lezioni aggiungeranno altri
strumenti, MCP, workflow e RAG: deve essere piccola ma estendibile senza riscritture.

## Obiettivi (criteri di riuscita = evidenze della consegna)
1. Conversazione su più turni che attraversa il grafo, con cronologia conservata per la sessione.
2. Una domanda sull'ora produce una richiesta strutturata di `ora_corrente`, la sua esecuzione e il
   risultato restituito al modello, tutto visibile nei log; una domanda ordinaria non usa lo strumento;
   una seconda domanda sull'ora nella stessa sessione richiama lo strumento.
3. Avvio con `docker compose run`, container collegato a LM Studio sull'host.
4. Test automatici senza modello, separati dalle prove reali con LM Studio e Docker.
5. README, `.env.example` e CLAUDE.md coerenti, con soli comandi verificati (anche PowerShell).

## Non-obiettivi
MCP, RAG, workflow, interfacce web/grafiche, altri strumenti, persistenza della cronologia, servizi cloud,
containerizzazione di LM Studio, streaming delle risposte, comandi in chat per cambiare i log o per
svuotare la cronologia (per ripartire da zero si esce con `/esci` e si riavvia),
gestione del limite di contesto (la cronologia cresce senza tagli per tutta la sessione), correzione
automatica delle risposte del modello.

## Anti-obiettivi (fallimento anche se “funziona”)
- Risposta plausibile sull'ora senza traccia della chiamata allo strumento.
- Test con modello simulato presentati come prova del tool calling reale.
- Struttura che alla prossima lezione andrebbe rifatta (es. tutto in un unico file, modello non iniettabile).

## Vincoli (da CLAUDE.md)
Codice sincrono, moduli piccoli; separazione grafo / modello / strumenti / terminale. URL e modello solo
da variabili d'ambiente; l'identificativo è quello di `GET /v1/models`. Dipendenze motivate e con versioni
fissate. Lavoro solo in `assistente-laboratorio/`, branch corrente (`main`), Conventional Commits in
italiano, staging selettivo, nessun push senza richiesta. `LLM_Lez_3.pdf` (non tracciato) resta fuori.
Nessun branch o worktree nuovo, anche se una skill di Superpowers lo suggerisse. `.gitignore` del progetto
con almeno `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`. Le versioni esatte delle dipendenze vanno
elencate nel piano e approvate prima dell'installazione. Il CLAUDE.md del progetto si aggiorna (Python
3.14.7, struttura, comandi di test) quando queste convenzioni sono stabili, non per annotare l'avanzamento.

## Decisioni prese con l'utente
- Progetto in `Esercizi/assistente-laboratorio/`, accanto a `Lezione3/`: la radice della repo personale
  (remote GitHub `LLM-ITS`) è la cartella `Esercizi/`. Spostato il 27/10/2026 senza cambiare la storia Git.
- Python **3.14.7** in locale (`py -3.14 -m venv .venv`) e nel container (`python:3.14.7-slim`, tag
  verificato su Docker Hub). Sul PC ci sono solo 3.13 e 3.10: va installata (winget `Python.Python.3.14` 3.14.7).
- Modello `google/gemma-4-e4b`. **Prova preliminare eseguita il 26/10/2026** (richieste dirette a LM Studio,
  temperatura 0): domanda sull'ora → `tool_calls` strutturato `ora_corrente` con argomenti `{}`; dopo il
  risultato la risposta usa l'ora ricevuta ma **inventa il giorno della settimana** («sabato» invece di
  lunedì); domanda ordinaria → nessuna chiamata. Da qui le contromisure su risultato e prompt (sotto).
- Orologio senza parametri; fuso IANA fisso da variabile d'ambiente, validato all'avvio.
- Log dei passaggi: due modalità tramite `LOG_LEVEL` — `INFO` (default, passaggi visibili) e `WARNING`
  (solo dialogo). Nessun comando in chat per cambiarle.
- Risposta mostrata tutta insieme (niente streaming).
- Ora di un'altra città: il modello chiama l'orologio e converte da sé a partire dall'ora locale.
  Scelta dell'utente; il risultato della conversione non è verificabile dai test automatici (vedi Rischi).
- Controllo all'avvio: l'app interroga `GET {LMSTUDIO_BASE_URL}/models`; se LM Studio non risponde o il
  modello configurato non è nell'elenco, non parte e mostra l'URL usato e i modelli disponibili.
- Dipendenze: `langgraph`, `langchain-openai` (ChatOpenAI con `base_url` verso LM Studio), `tzdata`
  (fusi su Windows), `python-dotenv` (legge `.env` in locale) in `requirements.txt`; `pytest` in
  `requirements-dev.txt` (fuori dall'immagine Docker). Versioni fissate in fase di implementazione.
- Prove reali divise: Claude esegue quelle automatizzabili (`python -m pytest -m reale`, `docker compose build`,
  una sessione con input predefinito via `docker compose run -T`); l'utente esegue la demo interattiva
  (`docker compose run --rm --name assistente-demo assistente` + `docker logs -f` da un secondo terminale)
  nei punti di consegna indicati. Il commit di quegli incrementi aspetta l'esito dell'utente.
- Claude può installare Python 3.14.7 con winget e avviare Docker Desktop (ogni comando passa dalla conferma).

## Architettura
Pacchetto `assistente/` nella radice del progetto, avviato con `python -m assistente`.

| Modulo | Responsabilità |
|---|---|
| `config.py` | Legge e valida le variabili d'ambiente (carica `.env` se presente, senza sovrascrivere variabili già impostate); errore chiaro se mancano URL o modello o se il fuso non è valido |
| `strumenti.py` | Strumento `ora_corrente`, costruito con fuso e sorgente dell'istante iniettabili |
| `modello.py` | Crea il `ChatOpenAI` puntato a LM Studio dalla configurazione (temperatura 0); controllo all'avvio dell'elenco modelli con la libreria standard (`urllib`), separando la lettura HTTP dalla verifica dell'elenco così che la verifica sia testabile senza rete |
| `grafo.py` | Stato, nodi, instradamento; `costruisci_grafo(modello, strumenti)` riceve il modello dall'esterno |
| `cli.py` / `__main__.py` | Ciclo di chat, cronologia di sessione, stampa, gestione errori, configurazione dei log |

### Grafo
- **Stato**: `messages: Annotated[list, add_messages]` (aggiunge, non sostituisce).
- **`nodo_llm`**: antepone il prompt di sistema (non salvato nella cronologia), invoca il modello con lo
  strumento associato (`bind_tools`), restituisce il messaggio di risposta. Log di inizio e fine chiamata.
- **`instrada`** (arco condizionale): se l'ultimo messaggio ha `tool_calls` → `nodo_strumenti`, altrimenti `END`.
  Logga nome e argomenti dello strumento richiesto, oppure «nessuno strumento -> fine».
- **`nodo_strumenti`**: esegue ogni richiesta e aggiunge un `ToolMessage` con il `tool_call_id`
  corrispondente; logga il risultato. Strumento sconosciuto → `ToolMessage` di errore + log WARNING.
- **Archi**: `START → nodo_llm`, `nodo_llm →(instrada)→ nodo_strumenti | END`, `nodo_strumenti → nodo_llm`.
- **Limite passaggi**: `recursion_limit` di LangGraph = 10 a ogni invocazione; se superato → messaggio
  «limite di passaggi raggiunto», turno scartato.

### Prompt di sistema (requisiti; testo esatto al builder)
In italiano. Deve dire: per ora, data o giorno attuali chiamare **sempre** `ora_corrente`, anche se nella
conversazione c'è già un risultato precedente (è superato); non dedurre informazioni temporali che il
risultato non contiene; per l'ora di un'altra città, chiamare l'orologio e convertire dall'ora locale,
indicando nella risposta anche l'ora locale di partenza (così l'utente può controllare il calcolo);
rispondere in italiano.

### Cronologia
La CLI tiene in memoria la lista dei messaggi; a ogni turno invoca il grafo con cronologia + nuovo
`HumanMessage` e, se l'esecuzione riesce, sostituisce la sua lista con quella restituita. Nessun
checkpointer. Se il turno fallisce la cronologia resta com'era: errori tecnici e domande senza risposta
non entrano nella cronologia. Gli errori di contenuto del modello invece restano nella cronologia e
possono influenzare i turni successivi: si limitano alla fonte (risultato completo + prompt).

### Strumento `ora_corrente` (contratto)
| Parte | Decisione |
|---|---|
| Nome | `ora_corrente` |
| Descrizione | Restituisce data, giorno della settimana e ora correnti nel fuso orario configurato; da usare per ogni domanda su ora, data o giorno attuali |
| Parametri | Nessuno |
| Risultato | `<giorno in italiano> AAAA-MM-GGTHH:MM:SS±HH:MM (Fuso/IANA)`, es. `lunedì 2026-10-26T16:42:10+01:00 (Europe/Rome)`; nomi dei giorni da tabella fissa nel codice, non dal locale di sistema |
| Errori | Fuso non valido rilevato all'avvio in `config.py` → l'app non parte e lo spiega |

### Configurazione
| Variabile | Esempio (`.env.example`) | Note |
|---|---|---|
| `LMSTUDIO_BASE_URL` | `http://localhost:1234/v1` | Compose la sovrascrive con `http://host.docker.internal:1234/v1` |
| `LMSTUDIO_MODEL` | `google/gemma-4-e4b` | Obbligatoria; deve coincidere con `GET /v1/models` |
| `APP_TIMEZONE` | `Europe/Rome` | Obbligatoria; nel container non si deduce dall'host |
| `LOG_LEVEL` | `INFO` | `INFO` = passaggi visibili; `WARNING` = solo dialogo |
La chiave API non serve a LM Studio: si passa un segnaposto fisso nel codice, nessuna credenziale.

### Terminale
Prompt `Tu> `, risposte `Assistente> ` su stdout; log `[LIVELLO] messaggio` su stderr (visibili anche
con `docker logs -f`). Errori stampati dalla CLI, quindi visibili in entrambe le modalità di log.
`/esci`, Ctrl+C o fine input chiudono la sessione con un saluto. Input vuoto ignorato.
Errori di connessione/timeout verso LM Studio o modello non trovato: messaggio riconoscibile con l'URL
usato, nessuna risposta inventata, turno scartato, chat che continua.

Esempio in modalità `INFO`:
```
Tu> Che ore sono?
[INFO] nodo_llm: chiamata al modello (2 messaggi)
[INFO] nodo_llm: risposta ricevuta in 1.9 s
[INFO] instradamento: richiesta strumento ora_corrente {}
[INFO] nodo_strumenti: ora_corrente -> lunedì 2026-10-26T16:42:10+01:00 (Europe/Rome)
[INFO] nodo_llm: chiamata al modello (4 messaggi)
[INFO] nodo_llm: risposta ricevuta in 1.2 s
[INFO] instradamento: nessuno strumento -> fine
Assistente> Sono le 16:42 di lunedì 26 ottobre 2026, ora di Roma (UTC+01:00).
```

### Docker
- `Dockerfile`: `python:3.14.7-slim`, installazione da `requirements.txt`, copia del pacchetto,
  `PYTHONUNBUFFERED=1`, `CMD ["python", "-m", "assistente"]`.
- `compose.yaml`: servizio `assistente`, `build: .`, variabili da `.env`, `LMSTUDIO_BASE_URL` impostata a
  `http://host.docker.internal:1234/v1`, `stdin_open` + `tty`, `extra_hosts: host.docker.internal:host-gateway`.
  Nessuna porta pubblicata.
- `.dockerignore`: `.env`, `.venv`, cache, `.git`, `tests`, `docs`.
- Avvio: `docker compose build` poi `docker compose run --rm --name assistente-demo assistente`.
- Da verificare nell'incremento: se il container non raggiunge LM Studio, controllare che LM Studio non
  ascolti solo su `127.0.0.1` («Serve on Local Network») e il firewall di Windows; esito nel README.

## Casi limite e gestione degli errori
Ogni caso ha un comportamento definito e, dove indicato, un test automatico.

| Caso | Comportamento | Test |
|---|---|---|
| LM Studio spento all'avvio, o modello configurato assente | L'app non parte: messaggio con URL usato e modelli disponibili, codice di uscita diverso da 0 | sì (verifica dell'elenco senza rete) |
| Primo caricamento del modello in LM Studio lento (decine di secondi) | Timeout di connessione breve (~5 s, per accorgersi subito del server spento) ma timeout di lettura lungo (~180 s); tentativi automatici del client al massimo 1 | — (prova reale) |
| Risposta del modello vuota, o richiesta di strumento malformata (`invalid_tool_calls`) | Messaggio «il modello non ha prodotto una risposta valida», log WARNING, turno scartato | sì |
| Strumento richiesto con argomenti inattesi (es. `{"timezone": ...}`) | Argomenti ignorati e registrati a WARNING; lo strumento restituisce comunque l'ora del fuso configurato; nessun crash | sì |
| Più richieste di strumento nella stessa risposta | Tutte eseguite, ciascuna con il proprio `tool_call_id` | sì |
| Contesto del modello esaurito (sessione lunga) | Errore restituito da LM Studio mostrato come errore riconoscibile, turno scartato; README spiega come aumentare la lunghezza di contesto in LM Studio e che la sua politica di overflow può tagliare messaggi in silenzio | — |
| Log di librerie esterne (httpx, openai) | Solo i logger dell'applicazione seguono `LOG_LEVEL`; quelli esterni restano a WARNING, così la modalità INFO mostra solo i passaggi del grafo | sì |
| `.env` salvato con BOM (PowerShell 5.1) o con fine riga Windows | Lettura con codifica `utf-8-sig`; il README crea il file con `Copy-Item .env.example .env` | sì |
| Variabile presente ma vuota (`LMSTUDIO_MODEL=`) o URL senza `http://`/`https://` | Trattata come mancante / non valida: errore chiaro all'avvio | sì |
| Test eseguiti sul PC dello sviluppatore con un `.env` reale | `load_dotenv` chiamato solo all'avvio dell'app, non all'import: i test passano la configurazione in modo esplicito e non dipendono dal `.env`, dall'orologio reale o dalla rete | sì |
| Comandi scritti in modo diverso (`/ESCI`, ` /esci `) o sconosciuti (`/aiuto`) | Normalizzati; un comando sconosciuto mostra un suggerimento e non viene inviato al modello | sì |
| Ctrl+C durante l'attesa della risposta | Uscita pulita con saluto, senza traceback | sì |
| Container avviato con `docker compose up` invece di `run` | Senza input interattivo l'app termina: il README indica `docker compose run` e spiega il sintomo | — |
| Orologio della VM di Docker Desktop in ritardo dopo la sospensione del PC (noto con WSL2) | Diagnosi nel README: confronto tra l'ora dell'host e `docker run --rm python:3.14.7-slim date` | — |

**Limiti accettati (non coperti):** il modello può scrivere nel testo qualcosa che imita una richiesta di
strumento invece di una richiesta strutturata (lo rilevano le prove reali, non si interpreta il testo); un
incolla su più righe produce più turni; il contenuto delle risposte può essere sbagliato anche quando il
flusso è corretto.

## Test
**Automatici (pytest, nessun modello attivo)** — eseguiti con `python -m pytest`:
- strumento con istante controllato: valore atteso esatto, giorno della settimana incluso; fuso diverso →
  offset corretto (anche a cavallo del cambio d'ora);
- configurazione: fuso non valido / modello mancante → errore;
- grafo con modello finto a risposte predefinite: percorso senza strumento (una chiamata, fine); percorso
  con strumento (llm → strumenti → llm, `ToolMessage` con `tool_call_id` giusto, funzione davvero eseguita);
  modello che chiede sempre lo strumento → limite di passaggi;
- cronologia: due turni → domande e risposte nell'ordine giusto, senza duplicati; errore del modello →
  cronologia invariata;
- log: richiesta e risultato dello strumento presenti a `INFO`, assenti a `WARNING` (`caplog`).

**Reali (attivati esplicitamente, esclusi di default)** — marcatore pytest `reale`, eseguiti con
`python -m pytest -m reale` con LM Studio attivo: una domanda ordinaria riceve risposta senza strumento;
una domanda sull'ora produce un `ToolMessage` di `ora_corrente`; una seconda domanda sull'ora nella stessa
sessione produce una seconda chiamata. Se il modello non chiama lo strumento il test fallisce e lo si
riporta: non si sostituisce con risposte simulate. La prova Docker è una checklist manuale nel README
(build, run, conversazione a due turni, due domande sull'ora, giorno della settimana corretto, una domanda
sull'ora di un'altra città con controllo manuale della conversione, `docker logs -f`).

## Documentazione
README: requisiti, configurazione (`.env` da `.env.example`, verifica del modello con
`Invoke-RestMethod http://localhost:1234/v1/models`), le due modalità di log, avvio locale e con Compose,
test automatici e reali, diagnosi (sintomi della slide 17, indirizzo di ascolto di LM Studio). Solo comandi
effettivamente eseguiti. CLAUDE.md aggiornato con struttura e comandi di test quando si stabilizzano.

## Scelte mie (da controllare) e cosa resta al builder
- Mie: cronologia nella CLI senza checkpointer; `recursion_limit` 10; formato del risultato dell'orologio con
  giorno della settimana; test reali come marcatore pytest; temperatura 0; `requirements-dev.txt` separato.
- Mie anche: valori dei timeout e gestione dei casi limite della tabella sopra.
- Al builder: testo del prompt di sistema (nel rispetto dei requisiti sopra), nomi interni, forma esatta
  del modello finto; versioni esatte proposte nel piano.

## Rischi aperti
- Il modello può comunque sbagliare dati non forniti dallo strumento o riusare risultati vecchi: le prove
  reali con due domande sull'ora servono a misurarlo.
- Conversioni verso altri fusi fatte dal modello: possono sbagliare quando le due città hanno regole di ora
  legale diverse o quando la conversione cambia giorno; la risposta riporta l'ora locale di partenza per
  permettere il controllo.
- Raggiungibilità di LM Studio dal container non ancora provata; Docker Desktop al momento è spento.

## Passi dopo l'approvazione
0. Installare Python 3.14.7 (`winget install Python.Python.3.14 --version 3.14.7`) e verificare
   `py -3.14 --version` → `Python 3.14.7`.
1. Creare `assistente-laboratorio/` e copiarci il `CLAUDE.md` di `Esercizi/`; commit
   `docs: aggiunge il CLAUDE.md del progetto assistente-laboratorio`.
2. Salvare questa specifica nel percorso indicato in testa; commit `docs: aggiunge la specifica di design`.
3. Invocare `superpowers:writing-plans` per il piano a incrementi (risposta fissa → LM Studio e cronologia →
   orologio e instradamento → Docker Compose → verifica completa), da approvare prima di scrivere codice.
