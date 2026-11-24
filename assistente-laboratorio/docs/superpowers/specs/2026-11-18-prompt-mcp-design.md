# Prompt MCP come comandi della CLI — specifica di design (Lezione 6, step 5)

> Stato: approvata dall'utente il 18/11/2026. Branch `feature/prompt`, nato da `dev` (`d630449`, con router, revisore, riassunto e
> preferenze).

## Intento e perché
Le slide (pag. 9–11) introducono la terza primitiva MCP, il **prompt**: un modello di istruzioni con argomenti,
salvato sul server e condiviso da tutti i client. Tool, resource e prompt si distinguono per **chi decide di usarli**:
il tool lo sceglie il modello, la resource l'host, il prompt **l'utente**, in modo esplicito. MCP non prevede un
comando standard: i comandi li definisce la CLI. Lo step aggiunge due prompt generici e due comandi della CLI per
elencarli e richiamarli; il testo compilato passa dal grafo come qualsiasi altra domanda.

## Requisiti delle slide (pag. 10)
1. Prompt `spiega(argomento, livello)` e `riassumi_conversazione(stile)`.
2. Comando `/prompts` con nome, descrizione e argomenti di ogni prompt.
3. Comando `/prompt nome argomento=valore`: i messaggi ottenuti si aggiungono alla cronologia e vanno al grafo.
4. Controllo nell'host rispetto a `prompts/list`: argomenti obbligatori mancanti o sconosciuti bloccano la richiesta,
   senza chiamare il modello.

Obiettivo delle slide: un prompt richiamato dall'utente passa dal grafo come qualsiasi altra domanda, compresi router,
strumenti e revisore. Evidenze richieste: `/prompt spiega argomento="Model Context Protocol" livello=base` dà una
risposta adeguata al livello; `riassumi_conversazione` riassume i turni della sessione corrente; log con prompt
richiamato, argomenti e messaggi ottenuti dal server.

## Decisioni prese con l'utente (18/11/2026)
- **Server dedicato** `prompt_mcp/`, accanto a `calcolatrice_mcp/`, `catalogo_mcp/` e `preferenze_mcp/`, con i soli due
  prompt e nessuno strumento né resource (un server per ogni cosa, come finora).
- **Prove con il modello solo manuali**, fatte dall'utente e guidate passo passo (regola del `CLAUDE.md` dal
  18/11/2026): nessun test `@pytest.mark.reale` nuovo.
- Comportamento descritto qui sotto («Decisioni dell'assistente»), approvato nella conversazione del 18/11/2026.

## Decisioni dell'assistente (approvate nella conversazione)
- **Argomenti dei prompt:**
  - `spiega(argomento, livello="base")`: `argomento` obbligatorio; `livello` facoltativo, uno tra `base`,
    `intermedio`, `avanzato`;
  - `riassumi_conversazione(stile)`: `stile` obbligatorio, uno tra `sintetico`, `dettagliato`.
- **I valori li controlla il server.** Un valore non ammesso (per esempio `livello=esperto`) fa fallire `prompts/get`
  con un messaggio in italiano che elenca i valori ammessi: la richiesta si blocca senza chiamare il modello e la CLI
  non deve conoscere i valori. L'host controlla solo nomi e presenza degli argomenti (requisito 4).
- **Elenco letto una volta all'avvio**, come il catalogo degli strumenti. Se il server non parte o l'elenco non si
  legge: WARNING e la chat parte comunque; `/prompts` e `/prompt` rispondono che i prompt non sono disponibili.
  (Come per le preferenze, a differenza dei server degli strumenti, che fermano l'avvio.)
- **`prompts/get` a ogni `/prompt`** (il server si avvia per quella richiesta, come per la resource): solo quando
  l'utente scrive `/prompt`, come dice la tabella di pag. 11.
- **Nella cronologia va il testo compilato**, non il comando `/prompt`: dal grafo in poi la richiesta è identica a una
  domanda scritta a mano (router, riassunto, strumenti, revisore). Il grafo non cambia.
- **Sintassi degli argomenti:** `nome=valore`, separati da spazi; virgolette doppie se il valore contiene spazi
  (`argomento="Model Context Protocol"`). Nome del prompt e nomi degli argomenti come li dà il server.
- **`ambito.txt`:** alla voce «domande sulla conversazione in corso» si aggiunge «e richieste di riassumerla», perché il
  router non rifiuti `riassumi_conversazione`.

## Obiettivi
1. `/prompts` mostra i due prompt con descrizione e argomenti (i facoltativi tra parentesi quadre).
2. `/prompt spiega argomento="Model Context Protocol" livello=base` porta a una risposta di livello base, passando da
   router e revisore come una domanda normale.
3. Dopo qualche turno, `/prompt riassumi_conversazione stile=sintetico` riassume i turni della sessione.
4. Prompt sconosciuto, argomento obbligatorio mancante, argomento sconosciuto, riga mal scritta, valore non ammesso:
   errore chiaro, nessuna chiamata al modello, cronologia invariata.
5. Il log mostra il prompt richiamato, gli argomenti e il testo ricevuto dal server.
6. Nulla si rompe: domande normali, `/esci`, `/log`, strumenti, preferenze, riassunto.

## Non-obiettivi
Altri prompt oltre ai due; prompt con più messaggi o con messaggi dell'assistente; completamento automatico o
richiesta interattiva degli argomenti; rileggere l'elenco durante la sessione; prompt scelti dal modello; gli step
successivi (agente come servizio HTTP, back-end, front-end, Compose a più container).

## Anti-obiettivi
- I prompt esposti come strumenti, o il modello che decide di usarli.
- Una richiesta `/prompt` sbagliata che arriva comunque al modello.
- Un `/prompt` che salta router o revisore.
- Il server dei prompt che non parte e impedisce l'avvio della chat.

## Comportamento

### Server `prompt_mcp/`
- Pacchetto come gli altri: `server.py` con FastMCP su stdio, log su stderr (silenzioso come quello delle preferenze),
  nessun import da `assistente/`; `__main__.py` per `python -m prompt_mcp`.
- Due `@server.prompt` con docstring (descrizione del prompt e degli argomenti). Ciascuno restituisce **un solo
  messaggio utente**, in italiano, per esempio:
  - `spiega`: «Spiegami «<argomento>» a livello <livello>: …» con un'indicazione diversa per livello (base: parole
    semplici e un esempio, senza formule; intermedio: …; avanzato: …);
  - `riassumi_conversazione`: «Riassumi la conversazione che abbiamo avuto finora, in modo <stile>: …» con un'indicazione
    per stile (sintetico: pochi punti; dettagliato: argomenti, risultati e decisioni).
  Testo esatto al builder.
- Valore non ammesso → eccezione con messaggio in italiano (`livello non valido («esperto»): usa base, intermedio o
  avanzato`), che arriva al client come errore di `prompts/get`.

### Assistente
- `client_mcp.py`:
  - lettura dell'elenco (`prompts/list`): nome, descrizione, argomenti con nome, descrizione e obbligatorietà;
  - richiesta di un prompt (`prompts/get`) con gli argomenti → testo del messaggio utente;
  - errori come `ErroreMCP` con un messaggio in italiano (server che non parte, prompt non letto con il motivo del
    server, risposta che non è un solo messaggio utente di testo).
- Modulo nuovo `assistente/prompt.py` (puro, sincrono): lettura della riga `/prompt …` (nome e argomenti, virgolette),
  controllo rispetto all'elenco (prompt sconosciuto, obbligatori mancanti, sconosciuti, argomento ripetuto), testo di
  `/prompts`.
- `cli.py`: `/prompts` e `/prompt` accanto a `/esci` e `/log` (il messaggio «Comando sconosciuto» li elenca). Con
  `/prompt` corretto: richiesta al server, poi lo stesso turno di una domanda scritta (`esegui_turno_con_riassunto` con
  il testo compilato), con la stessa scritta di attesa e gli stessi errori. Un errore prima del grafo stampa
  `Errore: …` e la cronologia resta com'era.
- `__main__.py`: legge l'elenco all'avvio, dopo le preferenze; un errore non fa uscire con codice 1.
- **Facoltativi tra parentesi quadre** (scelta dell'assistente dopo la rilettura): `prompts/list` dice solo nome,
  descrizione e obbligatorietà di ogni argomento, non il valore predefinito. `/prompts` scrive quindi i facoltativi
  come `[livello]`, e il predefinito sta nella descrizione dell'argomento data dal server («base (predefinito),
  intermedio o avanzato»). Le descrizioni degli argomenti compaiono in `prompts/list` solo se il server le dichiara
  per argomento (con FastMCP: `Annotated[str, Field(description=...)]`; `pydantic` è ammesso in `prompt_mcp/`, il
  divieto riguarda solo `assistente/`).
- Nella CLI solo la parola del comando (`/prompt`, `/prompts`) è confrontata in minuscolo: nome del prompt e valori
  restano come li ha scritti l'utente.
- Esempio:
  ```text
  Tu> /prompts
  spiega(argomento, [livello]): Spiega un argomento al livello richiesto.
    argomento: concetto da spiegare; livello: base (predefinito), intermedio o avanzato
  riassumi_conversazione(stile): Riassume la conversazione finora.
    stile: sintetico o dettagliato
  Tu> /prompt spiega livello=base
  Errore: al prompt spiega manca l'argomento obbligatorio argomento. Scrivi /prompts per l'elenco.
  ```
- **Log** (logger dell'assistente, separati da quelli degli strumenti):
  - INFO all'avvio: `prompt: elenco letto in 1.0 s: spiega(argomento, livello), riassumi_conversazione(stile)`;
  - INFO a ogni `/prompt` riuscito: `prompt: spiega {"argomento": "Model Context Protocol", "livello": "base"} -> «<testo
    ricevuto>»` (testo completo, su una riga);
  - WARNING all'avvio: `prompt: elenco non disponibile (<motivo>), comandi /prompt disattivati`.
- `ambito.txt`: la frase del router (decisione sopra).

### Docker
`Dockerfile`: `COPY prompt_mcp/ prompt_mcp/`. `compose.yaml` invariato (nessun file da montare).

## Verifiche
- **Test senza modello:**
  - server: avvio reale su stdio; `prompts/list` dà i due prompt con argomenti e obbligatorietà; `prompts/get` dà un
    messaggio utente con argomento e livello nel testo; `livello` predefinito `base`; valore non ammesso → errore con
    il messaggio; nessuno strumento;
  - client: elenco e testo dal server vero; errore del server con il motivo; server che non parte → `ErroreMCP`;
  - `prompt.py`: righe valide (con e senza virgolette), riga mal scritta, prompt sconosciuto, obbligatorio mancante,
    argomento sconosciuto o ripetuto; testo di `/prompts`;
  - CLI: `/prompts`; `/prompt` corretto manda il testo compilato al grafo e la cronologia contiene quel testo;
    `/prompt` sbagliato non chiama il grafo e lascia la cronologia invariata; prompt non disponibili; «Comando
    sconosciuto» con i comandi nuovi;
  - `main`: elenco letto e passato alla CLI; con l'elenco che fallisce la chat parte, WARNING, codice 0;
  - `ambito.txt` contiene la frase sui riassunti.
- **Prove manuali con gemma** (le fa l'utente, guidato; in locale, PowerShell con la riga UTF-8 del README):
  1. `/prompts`, poi `/prompt spiega argomento="Model Context Protocol" livello=base`: risposta semplice, log con
     prompt, argomenti e testo ricevuto;
  2. due domande normali, poi `/prompt riassumi_conversazione stile=sintetico`: il riassunto cita i turni precedenti.
  Docker: `docker compose build` e la prova 1 nel container.

## Lasciato a chi costruisce
Testo esatto dei prompt e delle descrizioni; nomi delle funzioni e delle strutture dati; testo esatto degli errori;
come la CLI riceve l'elenco e la funzione per `prompts/get` (parametri di `esegui_chat` o un oggetto); se l'elenco si
legge con la sessione del client o con un'altra API della libreria.
