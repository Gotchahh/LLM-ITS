# Calcolatrice sicura via MCP — specifica di design (Lezione 5, feature 1)

> Stato: approvata dall'utente il 03/11/2026, al termine del brainstorming con Superpowers. Branch
> `feature/calcolatrice`, nato da `dev` (`6f7f5ab`).
> Parte dalla specifica della Lezione 4 (`2026-10-26-assistente-laboratorio-design.md`): tutto ciò che qui non
> è detto resta com'è là.

## Intento e perché
La Lezione 5 chiede di estendere l'assistente della Lezione 4 con strumenti ottenuti in tre modalità (funzione
nel grafo, API HTTP, MCP) e, come requisito minimo del laboratorio, con **almeno un'integrazione MCP dimostrata
con evidenze**. La calcolatrice è la prima delle sei feature: senza stato e con un contratto piccolo, è il modo
meno rischioso per costruire e provare il percorso MCP completo. La slide del Blocco 5 la descrive così:
«Espressioni aritmetiche senza eval: solo operazioni consentite. Allena il rifiuto esplicito di input non validi».

Il **ciclo del grafo non cambia**: richiesta del modello → esecuzione → `ToolMessage` correlato → nuova chiamata
al modello. Cambia solo il modo in cui il nodo strumenti ottiene il risultato: invece di eseguire una funzione
locale, chiede a un server MCP separato, il cui catalogo l'agente scopre all'avvio. La struttura deve servire
anche alle feature MCP successive (catalogo, meteo), senza riscritture.

## Obiettivi (criteri di riuscita = evidenze della consegna)
1. **Discovery**: all'avvio l'agente avvia il server, ne legge il catalogo (`tools/list`) e lo scrive nel log.
2. **Invocazione diretta**: il server risponde a `tools/call` senza modello (test automatici).
3. **Richiesta del modello**: una domanda di calcolo produce una richiesta strutturata di `calcola`, l'esecuzione
   nel server MCP e un `ToolMessage` con il `tool_call_id` della richiesta; la risposta usa il risultato. Tutto
   visibile nei log.
4. **Errore controllato**: un'espressione non valida (o una divisione per zero) produce un `ToolMessage` d'errore
   correlato e nessun numero inventato; un server non raggiungibile durante la chat produce un errore
   riconoscibile e diverso; un server che non parte all'avvio ferma l'app con codice 1.
5. **Nulla si rompe**: cronologia, limite dei passaggi, orologio, `/log`, scritta «Ragionando...» invariati; tutti
   i test automatici esistenti ancora verdi.
6. Avvio locale e con Docker Compose; README e `CLAUDE.md` aggiornati con soli comandi verificati (PowerShell).

## Non-obiettivi
Funzioni matematiche (`sqrt`, `sin`, `log`…), costanti (`pi`), variabili, aritmetica decimale esatta (`Decimal`)
o frazioni; sessione MCP persistente; trasporti diversi da stdio; server MCP di terzi; altri strumenti (le
feature 2–6 avranno la loro specifica); orologio via MCP (resta locale); nuove variabili d'ambiente; workflow e
RAG.

## Anti-obiettivi (fallimento anche se “funziona”)
- `eval`, `exec`, `compile` o qualsiasi esecuzione di codice sull'espressione.
- Un numero restituito quando il calcolo è fallito (falso successo), in qualsiasi punto della catena.
- Una risposta di calcolo senza traccia della chiamata MCP nei log, o test simulati presentati come prova che il
  modello locale usa lo strumento.
- Asincronia che si sparge fuori dal modulo client MCP.
- Log del server su stdout (romperebbe il protocollo).

## Vincoli (da CLAUDE.md)
Codice sincrono, moduli piccoli; l'asincronia delle librerie MCP resta confinata nel modulo client MCP. Nel
pacchetto `assistente/` non si importano direttamente `openai`, `httpx` né `pydantic` (eccezione: i tipi di
`langchain_core`). Le dipendenze della feature si aggiungono solo con questa feature, con versione fissata e
verificata su Python 3.14.7. Lavoro solo in `assistente-laboratorio/`, sul branch `feature/calcolatrice`;
Conventional Commits in italiano, staging selettivo; merge e push solo su richiesta dell'utente. Test
automatici senza modello separati dalle prove reali; le prove da pipe senza `PYTHONIOENCODING`, in una
PowerShell pulita.

## Decisioni prese con l'utente
- **Modalità MCP**, server FastMCP con trasporto **stdio**: l'agente avvia il server come processo figlio
  (02/11/2026). L'orologio resta locale.
- **Librerie (03/11/2026, alternativa A)**: `langchain-mcp-adapters==0.3.2` + `mcp==1.30.0`; il server usa il
  FastMCP incluso nell'SDK ufficiale (`mcp.server.fastmcp.FastMCP`). Motivo: la coppia del 02/11
  (`fastmcp` 4.x + adattatore) non è installabile, perché `fastmcp` 4.x richiede `mcp>=2.3` e
  `langchain-mcp-adapters` 0.3.2 (l'ultima) richiede `mcp<2.0`. Scartate: `fastmcp` 3.4.11 + adattatore (53
  pacchetti nuovi) e `fastmcp` 4.1.6 senza adattatore (46 pacchetti e un adattatore da scrivere).
- **Approvate il 03/11/2026** le proposte dell'handoff: contratto `calcola(espressione)` con `ast` e whitelist,
  limiti, errori come testo e mai come risultato falso; pacchetto server separato + modulo client nell'agente;
  involucro sincrono con `asyncio.run` e una sessione stdio per chiamata, durata misurata; discovery all'avvio con
  log del catalogo e codice 1 se fallisce; errori dello strumento come `ToolMessage` d'errore correlato con log
  WARNING, trasporto e validazione distinguibili; log del server solo su stderr; una riga nel prompt di sistema;
  server nella stessa immagine Docker con `compose.yaml` invariato; tabella dei casi limite e dei test.
- Timeout: restano il valore unico di 180 s per il modello e i 5 s del controllo di LM Studio all'avvio.

## Verifiche preliminari (03/11/2026, senza installare nulla)
- `pip install --dry-run -r requirements.txt langchain-mcp-adapters==0.3.2` nella `.venv` (Python 3.14.7):
  risolto; **19 pacchetti nuovi, nessuna versione esistente cambia**. Oltre ai due diretti (`mcp` 1.30.0 arriva
  con l'adattatore): attrs 26.1.0, cffi 2.1.1, click 8.5.0, cryptography 50.0.2, httpx-sse 0.4.3,
  jsonschema 4.26.0, jsonschema-specifications 2025.9.1, pycparser 3.12, pydantic-settings 2.16.2,
  PyJWT 2.15.1, python-multipart 0.0.33, pywin32 312 (solo Windows), referencing 0.37.0, rpds-py 2026.9.1,
  sse-starlette 3.6.0, starlette 1.10.0, uvicorn 0.54.0.
- Pacchetto `mcp` 1.30.0 (letto dalla wheel): contiene `mcp/server/fastmcp/` (`FastMCP.run(transport="stdio")`)
  e `mcp/client/stdio/`. Un'eccezione nello strumento diventa un risultato `isError=True` con il testo
  `Error executing tool <nome>: <messaggio>`. I log del server usano `logging.StreamHandler()` (stderr; `rich`
  non è installato). Il client stdio passa al figlio solo un ambiente ridotto e gli inoltra lo stderr del padre.
- `langchain-mcp-adapters` 0.3.2 (letto dalla wheel): gli strumenti sono `StructuredTool` **solo asincroni**
  (`coroutine=`); senza sessione esplicita ogni chiamata apre una sessione nuova (avvia il server, `initialize`,
  `call_tool`, chiude); con `MultiServerMCPClient(..., handle_tool_errors=False)` un risultato `isError=True`
  solleva una `ToolException` con il testo del server; gli errori di trasporto sollevano eccezioni di altro tipo.
  La connessione stdio accetta `command`, `args`, `cwd`, `env`.
- Orologio: i suoi errori sono già testo (`Errore: fuso orario sconosciuto…`), non `ToolException`: non cambia.

## Architettura
| Parte | Responsabilità |
|---|---|
| `calcolatrice_mcp/calcolo.py` | Logica pura: `calcola(espressione: str) -> str` e `ErroreCalcolo`. Nessuna dipendenza esterna, nessun MCP |
| `calcolatrice_mcp/server.py` | Server FastMCP `"calcolatrice"` con lo strumento `calcola`, che delega a `calcolo.calcola`; log su stderr a WARNING |
| `calcolatrice_mcp/__main__.py` | `python -m calcolatrice_mcp`: avvia il server su stdio |
| `assistente/client_mcp.py` | Unico punto con codice asincrono: discovery all'avvio, involucri sincroni degli strumenti MCP, conversione degli errori, log del catalogo e delle durate |
| `assistente/__main__.py` | Dopo il controllo di LM Studio carica gli strumenti MCP; strumenti del grafo = orologio + strumenti MCP |
| `assistente/grafo.py` | `nodo_strumenti` trasforma una `ToolException` in un `ToolMessage` d'errore; una riga nuova nel prompt |

Il pacchetto del server è separato dall'agente: non importa nulla da `assistente/` e potrebbe essere usato da un
altro client MCP. L'agente non importa nulla dal server: lo conosce solo tramite il protocollo.

### Strumento `calcola` (contratto)
| Parte | Decisione |
|---|---|
| Nome | `calcola` |
| Descrizione (visibile al modello) | Calcola un'espressione aritmetica e restituisce il risultato esatto; da usare per ogni calcolo. Ammessi numeri (punto per i decimali), `+ - * / // % **` e parentesi; `%` è il resto della divisione, non la percentuale; `**` è la potenza. La descrizione sta nella docstring della funzione, senza importare `pydantic` |
| Parametro | `espressione`, testo obbligatorio, per esempio `2*(3+4)` o `12.5*8-3` |
| Analisi | `ast.parse(espressione, mode="eval")`, poi visita ricorsiva con whitelist; operazioni con il modulo `operator`. Nodi ammessi: `Expression`; `BinOp` con `Add`, `Sub`, `Mult`, `Div`, `FloorDiv`, `Mod`, `Pow`; `UnaryOp` con `UAdd`, `USub`; `Constant` con `type(valore)` esattamente `int` o `float` (quindi niente `bool`, `complex`, stringhe, `None`). Qualsiasi altro nodo → errore «elemento non ammesso». Le parentesi non sono nodi: le gestisce il parser |
| Limiti | Espressione vuota (dopo `strip`) rifiutata; al massimo 200 caratteri; esponente con valore assoluto ≤ 100, controllato **prima** di calcolare la potenza; ogni costante, risultato intermedio e risultato finale con valore assoluto ≤ 10^100; float non finiti (`inf`, `nan`) rifiutati |
| Risultato | Solo il numero, come testo: interi esatti (`2**10` → `1024`); decimali con al massimo 15 cifre significative (`format(valore, ".15g")`: `0.1+0.2` → `0.3`, `1/3` → `0.333333333333333`, `7/2` → `3.5`, `4/2` → `2`); `-0` reso come `0` |
| Errori | Mai un numero: un testo in italiano che descrive il problema, sollevato come `ErroreCalcolo` e restituito dal server come risultato MCP `isError=True`. Casi: espressione vuota; troppo lunga (massimo 200 caratteri); sintassi non valida; elemento non ammesso (nomi, chiamate, attributi, indici, confronti, booleani, stringhe, liste, numeri complessi…); virgola (`2,5`) con il suggerimento di usare il punto; `^` con il suggerimento di usare `**`; divisione per zero (`/`, `//`, `%`, `0**-1`); esponente troppo grande; numero troppo grande; risultato non reale (`(-8)**0.5`) |

### Client MCP (`assistente/client_mcp.py`)
- **Connessione** (una sola, al server della calcolatrice): stdio, comando `sys.executable` con argomenti
  `["-m", "calcolatrice_mcp"]`, `cwd` uguale alla cartella del progetto (il genitore di `assistente/`), così il
  pacchetto si trova sia in locale sia nel container. Nessuna variabile d'ambiente nuova.
- **Discovery** — `carica_strumenti_mcp() -> list[BaseTool]`: con `asyncio.run` crea un
  `MultiServerMCPClient` con `handle_tool_errors=False` e chiama `get_tools()`. Scrive nel log INFO il catalogo
  (nome e descrizione di ogni strumento) e la durata della discovery. Solleva `ErroreMCP`, con un messaggio
  chiaro che nomina il comando del server, se il server non parte, se il catalogo è vuoto o se manca `calcola`.
- **Involucro sincrono**: per ogni strumento MCP restituisce un `StructuredTool` sincrono con lo **stesso
  nome, la stessa descrizione e lo stesso schema** (lo schema JSON del catalogo), così `bind_tools`,
  `strumento.args` e il filtro degli argomenti di `nodo_strumenti` funzionano come per l'orologio. La sua
  funzione esegue `asyncio.run(strumento_mcp.ainvoke(argomenti))`: ogni chiamata apre e chiude una sessione
  stdio (comportamento dell'adattatore senza sessione esplicita). Il contenuto restituito (blocchi di testo)
  diventa un unico testo. La durata della chiamata va nel log INFO.
- **Errori durante la chat**:
  - errore di validazione (risultato `isError=True` → `ToolException` dell'adattatore): l'involucro toglie il
    prefisso inglese `Error executing tool calcola: ` aggiunto dalla libreria, se presente, e risolleva una
    `ToolException` con il solo messaggio italiano del server;
  - errore di trasporto (server che non parte o si interrompe, protocollo rotto: ogni altra eccezione durante la
    chiamata): l'involucro scrive un log WARNING `client_mcp: server MCP calcolatrice non raggiungibile: …` e
    solleva `ErroreTrasportoMCP(ToolException)` con il testo `server MCP calcolatrice non raggiungibile: …`.
  I due casi si distinguono dal testo che arriva al modello e dalle righe di log.

### Avvio (`assistente/__main__.py`)
Ordine: `prepara_terminale` → configurazione → controllo di LM Studio → `carica_strumenti_mcp()` →
`costruisci_grafo(crea_modello(config), [crea_strumento_orologio(config.fuso), *strumenti_mcp])` → chat.
`ErroreMCP` si gestisce come `ErroreConfigurazione` ed `ErroreServer`: `Errore: <messaggio>` su stderr e codice
di uscita 1, senza traceback. La discovery avviene dopo `configura_log`, così la riga del catalogo segue
`LOG_LEVEL`.

### Grafo: errori degli strumenti (`assistente/grafo.py`)
In `nodo_strumenti`, `strumento.invoke(argomenti)` è protetto da `except ToolException`: il risultato diventa
`ToolMessage(content=f"Errore: {errore}", tool_call_id=<id della richiesta>, name=<nome>, status="error")` con
un log WARNING `nodo_strumenti: errore dello strumento <nome>: <messaggio>`; il turno prosegue con la nuova
chiamata al modello (slide: «un esito per ogni richiesta»). Le altre eccezioni risalgono come oggi e annullano
il turno con il messaggio della CLI. Il grafo resta generico: conosce solo `ToolException` di `langchain_core`,
non il client MCP. Nessun altro cambiamento a stato, archi, `instrada`, `LIMITE_PASSAGGI` o `esegui_turno`.

### Prompt di sistema (requisiti; testo esatto al builder)
Una riga in più, in italiano: per qualsiasi calcolo aritmetico chiamare lo strumento `calcola` con
l'espressione (numeri con il punto decimale, `**` per le potenze) invece di calcolare da sé, e usare il
risultato così com'è; se lo strumento restituisce un errore, dirlo all'utente senza inventare un risultato. Le
righe dell'orologio non cambiano.

### Log (esempio in modalità `INFO`; testi esatti al builder)
```
[INFO] client_mcp: catalogo di calcolatrice letto in 1.4 s: calcola (Calcola un'espressione aritmetica...)
Tu> Quanto fa 12,5 per 8 meno 3?
[INFO] nodo_llm: chiamata al modello (2 messaggi)
[INFO] nodo_llm: risposta ricevuta in 3.1 s
[INFO] instradamento: richiesta strumento calcola {"espressione": "12.5*8-3"}
[INFO] client_mcp: calcola eseguito in 1.2 s
[INFO] nodo_strumenti: calcola -> 97
[INFO] nodo_llm: chiamata al modello (4 messaggi)
[INFO] nodo_llm: risposta ricevuta in 2.0 s
[INFO] instradamento: nessuno strumento -> fine
Assistente> 12,5 per 8 meno 3 fa 97.
```
Errore controllato: `[WARNING] nodo_strumenti: errore dello strumento calcola: divisione per zero`. Il server
scrive su stderr solo dal livello WARNING in su; i log delle librerie `mcp` e `langchain_mcp_adapters` restano a
WARNING come quelli delle altre librerie esterne (il logger `assistente` copre già `assistente.client_mcp`).

### Docker
`Dockerfile`: una riga `COPY calcolatrice_mcp/ calcolatrice_mcp/` accanto a quella di `assistente/`; il server
gira nello stesso container come processo figlio. `compose.yaml` e `.dockerignore` non cambiano.

### Dipendenze
`requirements.txt`: si aggiungono `langchain-mcp-adapters==0.3.2` e `mcp==1.30.0` (fissato perché il server lo
importa direttamente). Le transitive elencate sopra non si fissano, come `langchain-core` nella Lezione 4. Dopo
l'installazione: `pip check` pulito e i test esistenti verdi. `requirements-dev.txt` non cambia.

## Casi limite e gestione degli errori
| Caso | Comportamento | Test |
|---|---|---|
| Precedenze e segni: `2+3*4`, `(2+3)*4`, `-2**2`, `2**-1`, `--3` | `14`, `20`, `-4` (come Python), `0.5`, `3` | sì |
| Decimali: `0.1+0.2`, `1/3`, `7/2`, `4/2`, `1e3` | `0.3`, `0.333333333333333`, `3.5`, `2`, `1000` | sì |
| `//` e `%` con negativi e decimali: `-7//2`, `-7%3`, `7.5%2` | Semantica di Python: `-4`, `2`, `1.5` | sì |
| Input malevoli: `__import__('os')`, `().__class__`, `x`, `abs(-1)`, `[1,2]`, `'a'*3`, `1<2`, `True+1`, `2j` | Errore «elemento non ammesso», nessuna esecuzione | sì |
| Virgola decimale `2,5` / potenza con `^` | Errore con il suggerimento: usare il punto / usare `**` | sì |
| Sintassi rotta: `2+`, `(2`, `2 3`, `×` | Errore «sintassi non valida» | sì |
| Vuota o solo spazi; oltre 200 caratteri | Errore «espressione vuota» / «troppo lunga» | sì |
| `1/0`, `1//0`, `1%0`, `0**-1` | Errore «divisione per zero» | sì |
| `9**9**9`, `2**101` | Errore «esponente troppo grande», senza calcolare la potenza | sì |
| `10**100*10`, `1e308*10`, costante con più di 100 cifre | Errore «numero troppo grande» | sì |
| `(-8)**0.5` | Errore «risultato non reale» | sì |
| Il modello passa argomenti con un nome diverso (`{"expression": ...}`) | Argomento ignorato con WARNING (comportamento esistente); il server segnala `espressione` mancante; `ToolMessage` d'errore | sì |
| Il modello passa un numero invece di un testo | Errore di validazione del server → `ToolMessage` d'errore, nessun crash | sì |
| Server che non parte all'avvio (pacchetto mancante, errore d'import) | `ErroreMCP`: `Errore: …` con il comando usato, codice 1 | sì |
| Catalogo vuoto o senza `calcola` | `ErroreMCP`, codice 1 | sì |
| Server che non risponde durante la chat | `ErroreTrasportoMCP` → `ToolMessage` d'errore «server MCP calcolatrice non raggiungibile», WARNING, chat che continua | sì |
| Più richieste nella stessa risposta (`calcola` + `ora_corrente`, o due `calcola`) | Tutte eseguite, ciascuna con il proprio `tool_call_id`; un errore non blocca le altre | sì |
| Il modello richiede `calcola` all'infinito (anche dopo errori) | Limite di 10 passaggi come oggi | sì |
| Il modello calcola da sé senza chiamare lo strumento | Non si corregge: lo rileva la prova reale, che fallisce e viene riportata | — (prova reale) |

**Limiti accettati:** il modello può tradurre male la domanda in espressione (per esempio scambiare `%` per
la percentuale): il log degli argomenti lo mostra e la descrizione dello strumento lo previene; ogni chiamata
avvia un processo Python, quindi costa qualche centinaio di millisecondi o qualche secondo (misurato e annotato
nel README).

## Test
**Automatici (pytest, nessun modello attivo)**, eseguiti con `python -m pytest`:
- `test_calcolo.py`: tutti i casi della tabella sopra che riguardano la logica pura, compresi gli input malevoli
  e i limiti; un controllo che il modulo non usi `eval`, `exec` o `compile`.
- `test_server_mcp.py`: server vero in un sottoprocesso stdio. Catalogo: un solo strumento `calcola`, con
  descrizione e schema (`espressione` testo obbligatorio); invocazione diretta (`2+3*4` → `14`); `1/0` →
  risultato `isError=True` con il messaggio italiano. I test possono usare `asyncio.run` (codice di test).
- `test_client_mcp.py`: discovery con il server vero (strumenti sincroni con nome, descrizione e schema; riga del
  catalogo nel log con `caplog`); `invoke({"espressione": "2+2"})` → `4`; errore di validazione →
  `ToolException` senza prefisso inglese; server che non parte → `ErroreMCP`; catalogo vuoto o senza `calcola`
  → `ErroreMCP`; errore di trasporto durante la chiamata → `ErroreTrasportoMCP`. Il modo di provocare i guasti
  (comando inesistente, server finto, sostituzione del client) è scelto dal builder.
- `test_grafo.py`: con il modello finto e uno strumento finto che solleva `ToolException`, `ToolMessage` con
  `status="error"`, testo `Errore: …` e `tool_call_id` giusto, log WARNING, seconda chiamata al modello; un'altra
  eccezione risale ancora; più richieste nella stessa risposta, una fallisce e le altre no.
- Integrazione senza modello: grafo con il modello finto e lo **strumento MCP vero**. Una richiesta di
  `calcola("12.5*8-3")` produce un `ToolMessage` `97` correlato; una richiesta di `calcola("1/0")` produce un
  `ToolMessage` d'errore e il turno finisce con la risposta del modello finto; cronologia e limite dei passaggi
  invariati.
- `test_main.py`: `ErroreMCP` all'avvio → messaggio `Errore: …` su stderr e codice 1; strumenti passati al grafo =
  orologio + strumenti MCP. Ritocco ai test esistenti: la discovery si sostituisce con una finta nella fixture, così
  i test di `main()` non avviano il server vero (e il loro `sys.stderr` finto, senza `fileno`, non arriva al figlio).
- I test esistenti (111) restano verdi.

**Reali (marcatore `reale`, LM Studio attivo)**, eseguiti con `python -m pytest -m reale -v`: una domanda di
calcolo (per esempio «Quanto fa 12,5 per 8 meno 3?») produce almeno un `ToolMessage` di `calcola` con risultato
`97` e una risposta che contiene `97`; i test dell'orologio e della domanda ordinaria restano invariati. Se il
modello non chiama lo strumento il test fallisce e lo si riporta. **Prove da pipe**: in locale in una
PowerShell pulita, senza `PYTHONIOENCODING` (domanda di calcolo + domanda con divisione per zero, osservando nei
log discovery, richiesta, esecuzione, `ToolMessage` ed errore controllato), poi in Docker con
`docker compose run --rm -T assistente`.

## Documentazione
README: che cos'è la calcolatrice e perché è un server MCP (con lo schema discovery → richiesta → esecuzione →
`ToolMessage`), dove sono server e client, le righe di log attese, la durata misurata di una chiamata, i test
nuovi, una diagnosi per livelli come nelle slide (il server da solo → discovery all'avvio → richiesta del modello
→ esecuzione → risposta). `CLAUDE.md`: struttura (`calcolatrice_mcp/`, `client_mcp.py`) e comandi, se cambiano.
`.env.example` non cambia. Solo comandi effettivamente eseguiti.

## Scelte mie (da controllare) e cosa resta al builder
- Mie: i valori dei limiti (200 caratteri, esponente 100, 10^100); il formato del risultato (solo il numero,
  15 cifre significative per i decimali, `-0` → `0`); ogni forma di numero che Python accetta come letterale
  `int` o `float` (`1e3`, `1_000`) è ammessa; i suggerimenti per `,` e `^`; `%` presentato come resto nella
  descrizione; la descrizione nella docstring, senza `pydantic`.
- Mie: `sys.executable -m calcolatrice_mcp` con `cwd` nella cartella del progetto e nessuna variabile d'ambiente
  nuova; il prefisso inglese tolto nel client; l'errore di trasporto registrato nel client e il grafo che conosce
  solo `ToolException`; il controllo che il catalogo contenga `calcola`; log del server a WARNING.
- Mie: nessun timeout nuovo per MCP (la logica è limitata dai limiti del contratto e un figlio che termina viene
  rilevato subito); `mcp` fissato in `requirements.txt` perché importato direttamente, le transitive no; i test
  possono usare `asyncio.run`; il test d'integrazione con il modello finto e il server vero.
- Al builder: testi esatti dei messaggi d'errore e del prompt (nel rispetto dei requisiti), nomi interni, come
  convertire i blocchi di contenuto in testo, come provocare i guasti nei test, l'ordine degli incrementi nel
  piano.

## Rischi aperti
- **Durata di una chiamata**: ogni chiamata avvia un processo Python che importa `mcp`; su Windows potrebbe
  costare 1–3 s. Si misura nell'incremento del client; se fosse troppo lenta, una sessione persistente è una
  decisione da riportare all'utente, non da prendere da soli.
- **Stderr del figlio sotto pytest su Windows**: il client stdio usa come stderr del figlio lo `sys.stderr` del
  padre (valore fissato all'import di `mcp.client.stdio`); la cattura di pytest potrebbe interferire. Da
  verificare per primo nell'incremento del client.
- **Wheel Linux per Python 3.14** (`cryptography`, `rpds-py`, `cffi`): la build Docker lo verifica.
- **Comportamento del modello** (`gemma-4-e4b`): può calcolare da sé, scrivere l'espressione in forma naturale
  o leggere `%` come percentuale. Gli errori con suggerimento gli permettono di riprovare entro il limite dei
  passaggi; la prova reale lo misura. Se il modello non chiama `calcola`, si ritoccano al massimo il testo del
  prompt e la descrizione dello strumento; se non basta ci si ferma e lo si riporta all'utente, senza cambiare
  limiti o contratto.
- **Linea `mcp` 1.x**: l'adattatore non supporta ancora `mcp` 2.x; il passaggio sarà una scelta futura, quando
  esisterà una coppia compatibile.

## Passi dopo l'approvazione
1. Commit di questa specifica su `feature/calcolatrice`: `docs: aggiunge la specifica della calcolatrice MCP`.
2. Su richiesta dell'utente, `superpowers:writing-plans` per il piano a incrementi (logica pura → server
   FastMCP con dipendenze → client con discovery → integrazione nel grafo → prove reali → Docker → documentazione
   e revisione finale con Opus), da approvare prima di scrivere codice.
