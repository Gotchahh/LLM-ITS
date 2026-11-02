# Assistente del laboratorio — specifica di design (Lezione 4)

> Stato: approvata dall'utente il 26/10/2026, al termine del brainstorming con Superpowers.
> Aggiornata il 28/10/2026 con la proposta approvata dall'utente: fuso facoltativo nello strumento orologio
> e scritta «Ragionando...» durante l'attesa in modalità silenziosa.
> Aggiornata di nuovo il 28/10/2026, su richiesta dell'utente: comando `/log` in chat per mostrare o
> nascondere i log senza riavviare.

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
containerizzazione di LM Studio, streaming delle risposte, comandi in chat per svuotare la cronologia
(per ripartire da zero si esce con `/esci` e si riavvia),
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
- Orologio con un parametro facoltativo `fuso` (nome IANA). Senza parametro usa il fuso configurato da
  variabile d'ambiente, validato all'avvio; con il parametro calcola l'ora di un'altra località.
  Decisione del 28/10/2026: sostituisce l'orologio senza parametri, dopo che il modello ha indicato le 4:00 a
  New York quando erano le 5:00 (in quella settimana Roma e New York distano 5 ore invece di 6).
- Log dei passaggi: due modalità, log visibili e log nascosti (solo dialogo). La modalità iniziale viene da
  `LOG_LEVEL`: `INFO` (default, passaggi visibili) o `WARNING` (solo dialogo). In chat il comando `/log`
  passa dall'una all'altra, solo per la sessione in corso. Decisione del 28/10/2026, che sostituisce la
  scelta del 26/10 di cambiare modalità solo all'avvio. Con i log nascosti, solo nella chat interattiva,
  durante l'attesa compare la scritta fissa «Ragionando...», cancellata all'arrivo della risposta
  (decisione del 28/10/2026).
- Risposta mostrata tutta insieme (niente streaming).
- Ora di un'altra città: il modello chiama l'orologio con il fuso IANA della città e il programma calcola
  l'ora con le regole dell'ora legale di `tzdata`; il modello usa il risultato senza convertire da sé.
  Decisione del 28/10/2026, che sostituisce la conversione fatta dal modello.
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
| `config.py` | Legge e valida le variabili d'ambiente (carica `.env` se presente, senza sovrascrivere variabili già impostate); errore chiaro se mancano URL o modello o se il fuso non è valido; configura i log e ne cambia la modalità (visibili o nascosti) |
| `strumenti.py` | Strumento `ora_corrente` con parametro facoltativo `fuso`, costruito con fuso configurato e sorgente dell'istante iniettabili |
| `modello.py` | Crea il `ChatOpenAI` puntato a LM Studio dalla configurazione (temperatura 0); controllo all'avvio dell'elenco modelli con la libreria standard (`urllib`), separando la lettura HTTP dalla verifica dell'elenco così che la verifica sia testabile senza rete |
| `grafo.py` | Stato, nodi, instradamento; `costruisci_grafo(modello, strumenti)` riceve il modello dall'esterno |
| `cli.py` / `__main__.py` | Ciclo di chat, cronologia di sessione, stampa, gestione errori, comandi `/esci` e `/log`, scritta di attesa con i log nascosti |

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
risultato non contiene; per l'ora di un'altra città, chiamare `ora_corrente` con il fuso IANA della città
(per esempio `America/New_York`) e usare il risultato così com'è, senza convertire da sé; rispondere in
italiano.

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
| Descrizione | Restituisce data, giorno della settimana e ora correnti: senza argomenti nel fuso orario configurato, con `fuso` nel fuso di un'altra località; da usare per ogni domanda su ora, data o giorno attuali |
| Parametri | `fuso`, facoltativo: nome IANA della località, per esempio `America/New_York`, con una descrizione visibile al modello (data con `Annotated`, senza importare `pydantic`). Assente, nullo o vuoto → fuso configurato (`APP_TIMEZONE`) |
| Risultato | `<giorno in italiano> AAAA-MM-GGTHH:MM:SS±HH:MM (Fuso/IANA)`, es. `lunedì 2026-10-26T16:42:10+01:00 (Europe/Rome)` oppure `mercoledì 2026-10-28T04:56:00-04:00 (America/New_York)`; stesso formato per ogni fuso; nomi dei giorni da tabella fissa nel codice, non dal locale di sistema |
| Errori | Fuso configurato non valido: rilevato all'avvio in `config.py` → l'app non parte e lo spiega. Fuso richiesto dal modello non valido (es. `New York`, o un valore che non è un testo): nessuna eccezione, il risultato è un testo d'errore che il modello legge e può correggere, es. `Errore: fuso orario sconosciuto «New York»: serve un nome IANA, per esempio America/New_York` |

### Configurazione
| Variabile | Esempio (`.env.example`) | Note |
|---|---|---|
| `LMSTUDIO_BASE_URL` | `http://localhost:1234/v1` | Compose la sovrascrive con `http://host.docker.internal:1234/v1` |
| `LMSTUDIO_MODEL` | `google/gemma-4-e4b` | Obbligatoria; deve coincidere con `GET /v1/models` |
| `APP_TIMEZONE` | `Europe/Rome` | Obbligatoria; nel container non si deduce dall'host |
| `LOG_LEVEL` | `INFO` | Modalità iniziale dei log: `INFO` = passaggi visibili; `WARNING` = solo dialogo, con «Ragionando...» durante l'attesa nella chat interattiva. In chat `/log` la cambia |
La chiave API non serve a LM Studio: si passa un segnaposto fisso nel codice, nessuna credenziale.

### Terminale
Prompt `Tu> `, risposte `Assistente> ` su stdout; log `[LIVELLO] messaggio` su stderr (visibili anche
con `docker logs -f`). Errori stampati dalla CLI, quindi visibili in entrambe le modalità di log.
`/esci`, Ctrl+C o fine input chiudono la sessione con un saluto. Input vuoto ignorato.
Errori di connessione/timeout verso LM Studio o modello non trovato: messaggio riconoscibile con l'URL
usato, nessuna risposta inventata, turno scartato, chat che continua.

Comando `/log`: alterna log visibili e log nascosti per la sessione in corso, senza interrogare il modello e
senza entrare nella cronologia; è normalizzato come `/esci` (`/LOG`, ` /log `), mentre `/log on` o
`/log off` sono comandi sconosciuti. Dopo il cambio la CLI stampa su stdout
`Log nascosti: solo dialogo. Scrivi /log per mostrarli.` oppure `Log visibili. Scrivi /log per nasconderli.`
Il cambio tocca solo i log dell'applicazione (quelli delle librerie esterne restano a WARNING) e riporta al
livello d'avvio quando si torna alla modalità iniziale: da `DEBUG` o `INFO` i log si nascondono con `WARNING`
e si rimostrano con il livello d'avvio; da `WARNING` o `ERROR` si mostrano con `INFO` e si rinascondono con il
livello d'avvio. Il comando sconosciuto elenca `Comandi disponibili: /esci, /log`. Alla sessione successiva
si riparte da `LOG_LEVEL`: il `.env` non viene modificato.

Scritta di attesa: quando i log sono nascosti (da `LOG_LEVEL` all'avvio o dopo `/log`) e sia l'ingresso sia
l'uscita sono un terminale, la CLI scrive `Ragionando...` su stdout, senza andare a capo, subito prima di ogni
turno inviato al modello, e la cancella esattamente (backspace, spazi, backspace) prima di stampare la
risposta, l'errore o il saluto, anche dopo Ctrl+C. Righe vuote e comandi non la mostrano. La scelta si fa a
ogni turno, quindi segue i cambi fatti con `/log`. Con l'input da pipe (test, esempi del README,
`docker compose run -T`) o con i log visibili l'output resta quello di sempre.

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
| Primo caricamento del modello in LM Studio lento (decine di secondi) | Un solo timeout di 180 s per le chiamate al modello (un server spento rifiuta subito la connessione, e all'avvio lo rileva già il controllo dell'elenco modelli con timeout di 5 s); tentativi automatici del client al massimo 1 | — (prova reale) |
| Risposta del modello vuota, o richiesta di strumento malformata (`invalid_tool_calls`) | Messaggio «il modello non ha prodotto una risposta valida», log WARNING, turno scartato | sì |
| Strumento richiesto con argomenti inattesi (es. `{"timezone": ...}`) | Argomenti ignorati e registrati a WARNING; lo strumento restituisce comunque l'ora del fuso configurato; nessun crash | sì |
| Strumento richiesto con `fuso` assente, nullo o vuoto | Ora del fuso configurato | sì |
| Strumento richiesto con un `fuso` non valido (`New York`, un numero) | Nessuna eccezione: il risultato è il testo d'errore del contratto, il modello può riprovare | sì |
| Log nascosti con input da pipe o uscita non da terminale | Nessuna scritta di attesa: output identico a quello senza scritta | sì (scelta dell'indicatore) |
| `/log` scritto in modo diverso (`/LOG`, ` /log `) o con altro testo (`/log on`) | Normalizzato come `/esci`; `/log on` è un comando sconosciuto; in nessun caso si interroga il modello | sì |
| `/log` partendo da `DEBUG` o da `ERROR` | Tornando alla modalità iniziale si ritrova il livello d'avvio (`DEBUG` o `ERROR`); l'altra modalità usa `WARNING` o `INFO` | sì |
| `/log` con l'input da pipe (anche `docker compose run -T`) | I log cambiano come da tastiera; la scritta di attesa non compare | sì (cambio dei log) + prova da pipe |
| Errore del modello o Ctrl+C mentre la scritta di attesa è visibile | Scritta cancellata prima del messaggio d'errore o del saluto | sì |
| Più richieste di strumento nella stessa risposta | Tutte eseguite, ciascuna con il proprio `tool_call_id` | sì |
| Contesto del modello esaurito (sessione lunga) | Errore restituito da LM Studio mostrato come errore riconoscibile, turno scartato; README spiega come aumentare la lunghezza di contesto in LM Studio e che la sua politica di overflow può tagliare messaggi in silenzio | — |
| Log di librerie esterne (httpx, openai) | Solo i logger dell'applicazione seguono `LOG_LEVEL` e `/log`; quelli esterni restano a WARNING, così la modalità INFO mostra solo i passaggi del grafo | sì |
| `.env` salvato con BOM (PowerShell 5.1) o con fine riga Windows | Lettura con codifica `utf-8-sig`; il README crea il file con `Copy-Item .env.example .env` | sì |
| Variabile presente ma vuota (`LMSTUDIO_MODEL=`) o URL senza `http://`/`https://` | Trattata come mancante / non valida: errore chiaro all'avvio | sì |
| Test eseguiti sul PC dello sviluppatore con un `.env` reale | `load_dotenv` chiamato solo all'avvio dell'app, non all'import: i test passano la configurazione in modo esplicito e non dipendono dal `.env`, dall'orologio reale o dalla rete | sì |
| Comandi scritti in modo diverso (`/ESCI`, ` /esci `) o sconosciuti (`/aiuto`) | Normalizzati; un comando sconosciuto mostra un suggerimento e non viene inviato al modello | sì |
| Ctrl+C durante l'attesa della risposta | Uscita pulita con saluto, senza traceback | sì |
| Container avviato con `docker compose up` invece di `run` | Il container resta `Up` in attesa di un input che nessuno può digitare, senza output nei log (osservato sia con `docker compose up -d` sia con `docker compose up`): il README indica `docker compose run`, spiega il sintomo e come fermarlo con `docker compose down` (verificato il 02/11/2026) | — |
| Orologio della VM di Docker Desktop in ritardo dopo la sospensione del PC (noto con WSL2) | Diagnosi nel README: confronto tra l'ora dell'host e `docker run --rm python:3.14.7-slim date` | — |

**Limiti accettati (non coperti):** il modello può scrivere nel testo qualcosa che imita una richiesta di
strumento invece di una richiesta strutturata (lo rilevano le prove reali, non si interpreta il testo); un
incolla su più righe produce più turni; il contenuto delle risposte può essere sbagliato anche quando il
flusso è corretto; con i log nascosti un raro avviso (WARNING) stampato durante l'attesa può lasciare
«Ragionando...» a schermo accanto all'avviso (difetto solo estetico).

## Test
**Automatici (pytest, nessun modello attivo)** — eseguiti con `python -m pytest`:
- strumento con istante controllato: valore atteso esatto, giorno della settimana incluso; fuso diverso →
  offset corretto (anche a cavallo del cambio d'ora); parametro `fuso` (New York e Tokyo, assente, vuoto,
  non valido) e sua presenza nello schema dello strumento;
- configurazione: fuso non valido / modello mancante → errore;
- grafo con modello finto a risposte predefinite: percorso senza strumento (una chiamata, fine); percorso
  con strumento (llm → strumenti → llm, `ToolMessage` con `tool_call_id` giusto, funzione davvero eseguita);
  modello che chiede sempre lo strumento → limite di passaggi; richiesta con `{"fuso": ...}` che arriva allo
  strumento senza avvisi;
- scritta di attesa: ordine mostra → nascondi → risposta (anche con errore e Ctrl+C), nessuna scritta per
  righe vuote e comandi, testo scritto e cancellato esattamente, scelta dell'indicatore secondo il
  terminale, scritta mostrata solo con i log nascosti, anche dopo un cambio con `/log`;
- comando `/log`: messaggi di conferma, normalizzazione, nessuna chiamata al modello, livello del logger
  dell'applicazione dopo uno e due cambi partendo da ciascuno dei quattro livelli;
- cronologia: due turni → domande e risposte nell'ordine giusto, senza duplicati; errore del modello →
  cronologia invariata;
- log: richiesta e risultato dello strumento presenti a `INFO`, assenti a `WARNING` (`caplog`); nella stessa
  chat, i log dei passaggi spariscono dopo `/log` e ricompaiono dopo un secondo `/log`.

**Reali (attivati esplicitamente, esclusi di default)** — marcatore pytest `reale`, eseguiti con
`python -m pytest -m reale` con LM Studio attivo: una domanda ordinaria riceve risposta senza strumento;
una domanda sull'ora produce un `ToolMessage` di `ora_corrente`; una seconda domanda sull'ora nella stessa
sessione produce una seconda chiamata; «Che ore sono a New York?» produce un `ToolMessage` di `ora_corrente`
calcolato nel fuso `America/New_York`. Se il modello non chiama lo strumento il test fallisce e lo si
riporta: non si sostituisce con risposte simulate. La prova Docker è una checklist manuale nel README
(build, run, conversazione a due turni, due domande sull'ora, giorno della settimana corretto, una domanda
sull'ora di un'altra città con controllo del fuso richiesto nel log, `docker logs -f`, `/log`). Il comando
`/log` con il modello vero si prova con l'input da pipe (log presenti, assenti, di nuovo presenti). L'aspetto
della scritta «Ragionando...» nella chat da tastiera, anche dopo `/log`, si verifica a mano.

## Documentazione
README: requisiti, configurazione (`.env` da `.env.example`, verifica del modello con
`Invoke-RestMethod http://localhost:1234/v1/models`), le due modalità di log e il comando `/log`, avvio
locale e con Compose,
test automatici e reali, diagnosi (sintomi della slide 17, indirizzo di ascolto di LM Studio). Solo comandi
effettivamente eseguiti. CLAUDE.md aggiornato con struttura e comandi di test quando si stabilizzano.

## Scelte mie (da controllare) e cosa resta al builder
- Mie: cronologia nella CLI senza checkpointer; `recursion_limit` 10; formato del risultato dell'orologio con
  giorno della settimana; test reali come marcatore pytest; temperatura 0; `requirements-dev.txt` separato.
- Mie anche: valori dei timeout e gestione dei casi limite della tabella sopra.
- Mie, del 28/10/2026: `fuso` nullo trattato come assente; un `fuso` che non è un testo gestito come fuso non
  valido; la scelta dell'indicatore di attesa in una piccola funzione di `cli.py`, testabile con stream finti.
- Mie, del 28/10/2026 (comando `/log`): un solo comando che alterna, invece di `/log on` e `/log off`; i testi
  dei messaggi di conferma; il ritorno al livello d'avvio e `WARNING`/`INFO` per l'altra modalità; nessun
  messaggio all'avvio che presenti `/log` (lo elencano il README e il messaggio dei comandi sconosciuti).
- Al builder: testo del prompt di sistema (nel rispetto dei requisiti sopra), nomi interni, forma esatta
  del modello finto; versioni esatte proposte nel piano.

## Rischi aperti
- Il modello può comunque sbagliare dati non forniti dallo strumento o riusare risultati vecchi: le prove
  reali con due domande sull'ora servono a misurarlo.
- Ora di altre città: il calcolo è del programma, ma il modello può scegliere un fuso sbagliato o non passarlo.
  Si vede nel log (argomenti della richiesta) e nel risultato (nome del fuso); il test reale su New York lo misura.
- Raggiungibilità di LM Studio dal container non ancora provata; Docker Desktop al momento è spento.

## Passi dopo l'approvazione
0. Installare Python 3.14.7 (`winget install Python.Python.3.14 --version 3.14.7`) e verificare
   `py -3.14 --version` → `Python 3.14.7`.
1. Creare `assistente-laboratorio/` e copiarci il `CLAUDE.md` di `Esercizi/`; commit
   `docs: aggiunge il CLAUDE.md del progetto assistente-laboratorio`.
2. Salvare questa specifica nel percorso indicato in testa; commit `docs: aggiunge la specifica di design`.
3. Invocare `superpowers:writing-plans` per il piano a incrementi (risposta fissa → LM Studio e cronologia →
   orologio e instradamento → Docker Compose → verifica completa), da approvare prima di scrivere codice.
