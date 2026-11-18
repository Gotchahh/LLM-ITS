# Preferenze dell'utente come resource MCP — specifica di design (Lezione 6, step 4)

> Stato: approvata dall'utente il 18/11/2026. Branch `feature/preferenze`, nato da `dev` (`87c6f34`, con router, revisore e riassunto).

## Intento e perché
Le slide (pag. 7–8) introducono la **resource MCP**: un contenuto che il server espone con un URI e che sceglie
l'**host**, prima di chiamare il modello. Il modello non la chiama: la riceve come contesto. Lo step la usa per le
**preferenze dell'utente** (lingua, fuso orario predefinito, stile), lette all'avvio della sessione e messe in cima al
prompt di sistema dell'agente. Il vantaggio è che il contesto cambia **modificando un file, senza toccare il codice**,
e resta sotto il controllo dell'applicazione: il modello non decide se leggerlo.

## Requisiti delle slide (pag. 8 e 19)
1. Resource `utente://preferenze` con lingua delle risposte, fuso orario predefinito e stile (sintetico o dettagliato).
2. Lettura da parte dell'host a inizio sessione e inserimento in cima al prompt di sistema.
3. La resource non compare tra i tool passati a `bind_tools`.
4. Resource non disponibile: valori predefiniti, segnalati nei log.

Evidenze richieste: «Che ore sono?» usa il fuso predefinito senza chiederlo, provato con un fuso non ovvio come
`America/New_York`; cambiando lingua o stile nel file, la sessione successiva risponde di conseguenza; la lettura della
resource è visibile nei log, separata dalle chiamate ai tool. Consegna minima: preferenze applicate; modifica del file
senza modifica del codice.

## Decisioni prese con l'utente (18/11/2026)
- **Fuso solo nel prompt.** Il fuso delle preferenze entra nel prompt dell'agente e il modello lo passa a `ora_corrente`
  quando l'utente chiede l'ora senza indicare una località. `APP_TIMEZONE` resta il fuso del programma (predefinito degli
  strumenti di orologio, calendario e note) e il fuso usato se le preferenze non ci sono.
- **Server dedicato** `preferenze_mcp/`, accanto a `calcolatrice_mcp/` e `catalogo_mcp/`, con la sola resource e nessuno
  strumento: le preferenze dell'utente non c'entrano con calcolatrice e catalogo.
- **La lingua vale solo per le risposte dell'agente.** Il prompt dell'agente non impone più l'italiano: la lingua arriva
  dalle preferenze (predefinita italiano). `revisore.txt` riceve una regola: la lingua della risposta non è un motivo per
  rispondere coerente=false (altrimenti con «inglese» il revisore potrebbe far ripetere l'agente fino al limite). Il
  rifiuto del router, i messaggi della CLI, router, revisore e riassunto restano in italiano.
- **Docker: `preferenze.json` montato** da `compose.yaml` (bind mount di un solo file, sola lettura), così la sessione
  successiva nel container legge il file modificato senza `docker compose build`.

## Decisioni dell'assistente (da confermare con l'approvazione)
- **File `preferenze.json`** nella cartella del progetto, **versionato** come `ambito.txt` (così c'è sempre, anche per il
  bind mount di Docker: con il file mancante Docker creerebbe una cartella). Contenuto versionato:
  `{"lingua": "italiano", "fuso": "Europe/Rome", "stile": "sintetico"}`. Lingua e fuso sono quelli di oggi; lo stile
  «sintetico» aggiunge un'istruzione che oggi non c'è, scritta in modo da non togliere parti richieste («brevi ed
  essenziali, senza tralasciare nulla di ciò che la domanda chiede»), così il revisore non le giudica incomplete. Le
  prove reali esistenti, eseguite con il file versionato, verificano che nulla si rompa.
- **Il server passa il testo, l'host controlla.** Il server legge il file a ogni lettura della resource e ne
  restituisce il testo (`mime_type` `application/json`), come nel frammento delle slide; non valida nulla. Un file
  mancante o illeggibile fa fallire la lettura della resource (errore MCP), non l'avvio del server.
- **Controlli nell'host, campo per campo**, in un modulo puro nuovo `assistente/preferenze.py`:
  - `lingua`: testo non vuoto (nessun elenco chiuso: «inglese», «English», «spagnolo» vanno bene);
  - `fuso`: nome IANA valido (`ZoneInfo`);
  - `stile`: `sintetico` o `dettagliato`;
  - campo mancante o non valido → il suo predefinito, con un WARNING che nomina il campo e il valore ricevuto; campi in
    più ignorati.
- **Predefiniti**: lingua `italiano`, fuso quello di `APP_TIMEZONE`, stile **nessuno** (nessuna istruzione di stile,
  come oggi). Si usano tutti quando il server non parte, la resource non si legge o il testo non è un oggetto JSON:
  un WARNING `preferenze: resource non disponibile (<motivo>), valori predefiniti`; l'avvio **non** si ferma
  (requisito 4).
- **Che cosa entra nel prompt.** Non il JSON grezzo ma poche frasi in italiano costruite dai valori controllati, **in
  cima** al prompt di sistema dell'agente (prima di `PROMPT_DI_SISTEMA`), per esempio:
  «Preferenze dell'utente: rispondi sempre in inglese. Il fuso orario predefinito dell'utente è America/New_York: per
  l'ora, la data o il giorno attuali senza una località indicata chiama ora_corrente con fuso America/New_York. Stile:
  risposte brevi ed essenziali, senza tralasciare nulla di ciò che la domanda chiede.» La frase del fuso c'è sempre
  (anche con il predefinito), così il comportamento non dipende da dove viene il valore; vale sopra la descrizione di
  `ora_corrente` («omettere per il fuso configurato»), che resta invariata. Testo esatto al builder.
- `PROMPT_DI_SISTEMA` perde «e rispondi sempre in italiano»: la lingua arriva solo dal blocco delle preferenze, che c'è
  sempre (con i predefiniti dice «in italiano»).
- **Solo l'agente** riceve le preferenze. Router, revisore e riassunto no.
- **Lettura nel client MCP.** Una funzione nuova in `client_mcp.py` avvia `preferenze_mcp` su stdio, legge
  `utente://preferenze` e restituisce il testo; non passa per `carica_server_mcp` (che pretende strumenti) e il server
  non entra in `SERVER_MCP`. Nessuno strumento del server delle preferenze va a `bind_tools`.
- **Log** (separati dalle righe degli strumenti):
  - INFO `preferenze: resource utente://preferenze letta in 1.2 s: lingua=inglese, fuso=America/New_York, stile=sintetico`;
  - WARNING `preferenze: <campo> non valido («<valore>»), si usa <predefinito>`;
  - WARNING `preferenze: resource non disponibile (<motivo>), valori predefiniti`.
- **Nessuna variabile d'ambiente nuova**: il percorso del file è fisso (`preferenze.json` nella cartella da cui parte il
  server, cioè la cartella del progetto). Il processo figlio MCP su stdio non riceve tutto l'ambiente del padre, quindi
  una variabile andrebbe passata esplicitamente; per lo step non serve. Per i test il server può accettare un percorso
  come argomento della riga di comando (scelta al builder).

## Obiettivi
1. Con `"fuso": "America/New_York"` nel file, «Che ore sono?» porta a `ora_corrente` con `fuso=America/New_York` e la
   risposta dà l'ora di New York, senza che l'utente nomini la città.
2. Con `"lingua": "inglese"` la sessione successiva risponde in inglese; con `"stile": "dettagliato"` le risposte sono
   più lunghe che con `"sintetico"`. Nessuna modifica al codice.
3. Il log mostra la lettura della resource all'avvio, distinta dalle righe di `nodo_strumenti` e `client_mcp`.
4. Server spento, file mancante, JSON rotto o valori non validi: predefiniti e WARNING, la chat parte.
5. Nulla si rompe: router, revisore, riassunto, strumenti, `/log`, prove reali esistenti.

## Non-obiettivi
Prompt MCP e comandi `/prompts` (step 5) e gli step successivi; tradurre CLI, rifiuto del router, revisore o riassunto;
cambiare il fuso predefinito degli strumenti (`APP_TIMEZONE`); rileggere le preferenze durante la sessione o con un
comando; modificare le preferenze dalla chat; preferenze per più utenti.

## Anti-obiettivi
- La resource esposta come strumento, o il modello che decide se leggerla.
- Un problema delle preferenze che impedisce l'avvio della chat.
- Il revisore che rifiuta le risposte perché in un'altra lingua.
- Un fuso delle preferenze ignorato: «Che ore sono?» con l'ora di Roma mentre il file dice New York.
- Dover ricostruire l'immagine Docker per cambiare le preferenze.

## Comportamento

### Server `preferenze_mcp/`
- Pacchetto come gli altri due: `server.py` con FastMCP su stdio, log su stderr, nessun import da `assistente/`;
  `__main__.py` per `python -m preferenze_mcp`.
- `@server.resource("utente://preferenze", name="preferenze", mime_type="application/json")` che restituisce il testo
  del file letto al momento della richiesta. Nessuno strumento.

### Assistente
- `client_mcp.py`: funzione che legge la resource (stesso stile di avvio dei server esistenti: interprete corrente,
  cartella del progetto) e restituisce il testo o solleva `ErroreMCP` con un messaggio in italiano.
- `preferenze.py` (puro, sincrono): da testo a preferenze controllate (con i WARNING), predefiniti, blocco di testo per
  il prompt.
- `grafo.py`: `costruisci_grafo` riceve un parametro facoltativo con il blocco delle preferenze; senza, si comporta come
  oggi tranne la frase sulla lingua (i test esistenti che controllano il prompt vanno aggiornati di conseguenza). Il
  prompt dell'agente è `blocco preferenze + PROMPT_DI_SISTEMA`; il riassunto resta nel messaggio che segue il prompt
  (`messaggi_di_contesto`).
- `__main__.py`: legge le preferenze dopo il controllo del modello e prima di costruire il grafo; un errore di lettura
  non è tra gli errori che fanno uscire con codice 1.
- `revisore.txt`: una riga in più sulla lingua.
- `tests/test_reale.py`: la fixture `grafo` costruisce il grafo come `main`, quindi con le preferenze lette dal file
  versionato (tramite il server vero).

### Limite noto
Gli strumenti di calendario e note calcolano «oggi» nel fuso di `APP_TIMEZONE`, non in quello delle preferenze (decisione
«fuso solo nel prompt»): vicino alla mezzanotte i due fusi possono dare date diverse. Da scrivere nel README.

### Docker
- `Dockerfile`: `COPY preferenze_mcp/ preferenze_mcp/` e `COPY preferenze.json ./` (l'immagine funziona anche da sola).
- `compose.yaml`: nel servizio `assistente`, `volumes: - ./preferenze.json:/app/preferenze.json:ro`.

## Verifiche
- **Test senza modello**:
  - server: avvio reale su stdio, la resource è elencata con il suo URI e il suo tipo, la lettura restituisce il testo
    del file, nessuno strumento esposto; file mancante → la lettura dà errore, il server resta in piedi;
  - client: lettura del testo dal server vero; server che non parte → `ErroreMCP`;
  - `preferenze.py`: valori validi; ogni campo mancante o non valido → predefinito e WARNING; testo non JSON, JSON che
    non è un oggetto → tutti i predefiniti; campi in più ignorati; blocco del prompt con lingua, fuso e stile, e senza
    frase di stile quando lo stile è quello predefinito;
  - grafo: il prompt dell'agente inizia con il blocco delle preferenze; router, revisore e riassunto non lo ricevono;
    gli strumenti passati a `bind_tools` sono gli stessi di prima (nessuno del server delle preferenze);
  - `main`: preferenze lette e passate al grafo; con la lettura che fallisce la chat parte con i predefiniti, WARNING,
    codice 0;
  - `preferenze.json` del progetto è valido e dà i valori versionati; `revisore.txt` contiene la regola sulla lingua.
- **Prove reali con gemma** (preferenze costruite dal test, senza modificare il file versionato):
  - fuso `America/New_York`, «Che ore sono?» → richiesta `ora_corrente` con `fuso=America/New_York` e ora di New York
    nella risposta;
  - lingua `inglese` → risposta in inglese a una domanda in italiano, e il revisore la approva;
  - stile `dettagliato` contro `sintetico` sulla stessa domanda → la risposta dettagliata è più lunga;
  - le prove esistenti restano verdi con le preferenze versionate.
  Se gemma ignora le preferenze in cima al prompt (nello step 3 ignorava il riassunto dentro il prompt di sistema), si
  prova con uno script usa e getta su più casi prima di cambiare approccio e, se serve spostarle fuori dal prompt di
  sistema, lo si concorda con l'utente perché le slide chiedono «in cima al prompt».
- **Pipe** in PowerShell pulita e **Docker**: sessione con il file versionato, poi file modificato (New York, inglese,
  dettagliato), nuova sessione con le stesse domande: il comportamento cambia; poi il file torna com'era. Log con la riga
  della lettura della resource.

## Lasciato a chi costruisce
Testo esatto del blocco delle preferenze e della regola in `revisore.txt`; nomi delle funzioni e della struttura dati
delle preferenze; come i test indicano al server un file diverso; formato del motivo nei WARNING.
