# Catalogo della strumentazione con MCP — specifica di design (Lezione 5, feature 5)

> Stato: approvata dall'utente il 09/11/2026 (scritta dall'assistente); contenuto scelto dall'utente («strumentazione del laboratorio»).
> Branch `feature/catalogo`, nato da `dev` (`0b53f38`: calcolatrice, convertitore, giorni e scadenze, note).

## Intento e perché
In laboratorio si chiede «dov'è la centrifuga?», «il microscopio 2 è disponibile?», «che cosa è in manutenzione?».
Il modello non conosce l'inventario: lo consulta tramite un server MCP che espone **più strumenti sugli stessi dati**
(cerca, dettaglio, elenco filtrato) e il modello sceglie quello giusto.

Per non confondere gli *strumenti* del modello con quelli del laboratorio, nel codice e nei testi gli oggetti del
catalogo si chiamano **apparecchi**.

### Perché MCP
Il piano della Lezione 5 assegna MCP a questa feature: un server che raggruppa più strumenti su una stessa fonte di
dati è il caso tipico del protocollo (il client scopre il catalogo all'avvio). Il meccanismo esiste già per la
calcolatrice; qui si generalizza il client a più server.

## Obiettivi
1. «Dov'è la centrifuga?» → `cerca_apparecchi`; «Dimmi tutto su MIC-02» → `dettaglio_apparecchio`; «Che cosa è in
   manutenzione?» / «Che apparecchi ci sono nella stanza B12?» → `elenca_apparecchi`. Ogni chiamata nei log.
2. Le risposte vengono dal catalogo; un apparecchio inesistente produce un errore, non un'invenzione.
3. Il client MCP gestisce due server (calcolatrice e catalogo) con lo stesso codice; discovery di entrambi all'avvio.
4. Nulla si rompe (strumenti esistenti, `/log`, «Ragionando...», test esistenti); avvio locale e Docker; README e
   `CLAUDE.md` aggiornati.

## Non-obiettivi
Modificare il catalogo dalla chat (prenotazioni, cambi di stato), più cataloghi, collegamento con le note, scadenze di
calibrazione calcolate, workflow e RAG. Nessuna dipendenza nuova.

## Anti-obiettivi
- Apparecchi, stanze o stati inventati dal modello senza traccia della chiamata nei log.
- Un errore di un server MCP che blocca l'altro durante la chat, o un traceback.
- Testi in inglese o tecnici (`Error executing tool …`) restituiti al modello.

## Comportamento

### Dati
File `catalogo_mcp/apparecchi.json`, versionato, con circa 10 apparecchi di esempio (non reali). Campi:
`codice` (per esempio `MIC-02`), `nome`, `tipo`, `stanza`, `stato` (uno tra `disponibile`, `in uso`,
`in manutenzione`, `fuori servizio`), `ultima_calibrazione` (`AAAA-MM-GG`), `note` (facoltativo). Letto all'avvio del
server; un file mancante o malformato fa fallire l'avvio del server (quindi della discovery) con un messaggio chiaro.

### Server `catalogo_mcp/` (FastMCP su stdio, come `calcolatrice_mcp/`; logica pura separata dal server)
| Strumento | Parametri | Risultato |
|---|---|---|
| `cerca_apparecchi` | `testo` | apparecchi con `testo` in codice, nome, tipo o note, senza distinzione di maiuscole: una riga ciascuno; nessun risultato → «nessun apparecchio corrisponde a «…»» |
| `dettaglio_apparecchio` | `codice` | tutti i campi; codice inesistente → errore «nessun apparecchio con codice «…»» |
| `elenca_apparecchi` | `stanza`, `stato` facoltativi | apparecchi filtrati (entrambi senza distinzione di maiuscole); stato fuori elenco → errore con gli stati ammessi |

Riga di un apparecchio: «MIC-02 Microscopio ottico 2 (microscopio) — stanza B12, disponibile, calibrato il
15/09/2026». Ricerca vuota → errore che chiede il testo.

### Client MCP (`assistente/client_mcp.py`)
Generalizzato a un elenco di server (`calcolatrice` con `calcola`; `catalogo` con i tre strumenti), ciascuno con il
proprio comando `python -m <pacchetto>` e gli strumenti richiesti. Discovery di tutti all'avvio, con un log del
catalogo per server; se un server non parte o non espone gli strumenti richiesti, errore chiaro e codice 1 (come oggi
per la calcolatrice). Gli errori di trasporto nominano il server giusto. Resta l'unico modulo con `asyncio`.

### Prompt di sistema
Una regola in più: per domande sugli apparecchi del laboratorio (dove sono, stato, calibrazione, che cosa c'è in una
stanza) chiamare `cerca_apparecchi`, `dettaglio_apparecchio` o `elenca_apparecchi` e rispondere solo con quello che
restituiscono; se lo strumento dà errore o nessun risultato, dirlo senza inventare. Le regole esistenti restano.

### Docker
`COPY catalogo_mcp/ catalogo_mcp/` nel `Dockerfile`; il server parte come processo figlio, `compose.yaml` non cambia.

## Verifiche
- **Test senza modello**: logica pura (ricerca, filtri, errori, formato); server avviato davvero su stdio (catalogo dei
  tre strumenti, invocazione, errori in italiano); client con due server (discovery, nomi, errore di avvio di uno dei
  due, errore di trasporto con il nome del server); giro nel grafo con modello finto; test MCP esistenti verdi.
- **Prove reali con gemma**: «Dov'è la centrifuga?» → `cerca_apparecchi` e la stanza nella risposta; «Quali
  apparecchi sono in manutenzione?» → `elenca_apparecchi` con `stato` e i codici attesi nella risposta.
- **Pipe** locale e **Docker** con le stesse domande.

## Lasciato a chi costruisce
Contenuto esatto del JSON di esempio, testi delle descrizioni e dei messaggi, organizzazione interna del client.
