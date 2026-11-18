# Preferenze dell'utente come resource MCP — piano di implementazione

> **Esecuzione:** superpowers:executing-plans, task per task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** un server MCP `preferenze_mcp` espone `utente://preferenze` (lingua, fuso, stile da `preferenze.json`); l'host la legge all'avvio, controlla un campo alla volta e mette poche frasi in cima al prompt dell'agente; se qualcosa va storto usa i predefiniti con un WARNING e la chat parte.

**Architecture:** `preferenze_mcp/server.py` (FastMCP su stdio, una resource, nessuno strumento) legge il file a ogni lettura. `client_mcp.py` aggiunge una lettura di resource che non passa per `carica_server_mcp`. `assistente/preferenze.py` (sincrono, senza MCP) trasforma il testo in `Preferenze` controllate e in un blocco di testo; `carica_preferenze` riceve la funzione di lettura come argomento e scrive le righe di log. `costruisci_grafo` riceve il blocco e lo antepone a `PROMPT_DI_SISTEMA` solo per l'agente. `__main__` legge le preferenze fuori dal blocco degli errori che fanno uscire con codice 1.

**Tech Stack:** Python 3.14.7, `mcp` (FastMCP, già presente), `langchain_mcp_adapters` (`MultiServerMCPClient.get_resources`, già presente), `zoneinfo`, `json`. Nessuna dipendenza nuova.

**Spec:** `docs/superpowers/specs/2026-11-18-preferenze-design.md`

## Global Constraints
- URI `utente://preferenze`, `name="preferenze"`, `mime_type="application/json"`; il server non valida e non espone strumenti.
- `preferenze.json` versionato nella cartella del progetto: `{"lingua": "italiano", "fuso": "Europe/Rome", "stile": "sintetico"}`.
- Controlli nell'host: `lingua` testo non vuoto (dopo `strip`), `fuso` nome IANA valido per `ZoneInfo` (dopo `strip`), `stile` `sintetico` o `dettagliato` (dopo `strip().lower()`); campi in più ignorati.
- Predefiniti: lingua `italiano`, fuso `config.fuso` (`APP_TIMEZONE`), stile `None` (nessuna frase di stile).
- Log (logger `assistente.preferenze`), mai nelle righe di `nodo_strumenti` o `client_mcp`:
  - INFO `preferenze: resource utente://preferenze letta in 1.2 s: lingua=inglese, fuso=America/New_York, stile=sintetico` (`stile=nessuno` se `None`);
  - WARNING `preferenze: <campo> mancante, si usa <predefinito>`;
  - WARNING `preferenze: <campo> non valido («<valore>»), si usa <predefinito>` (`<valore>` = `json.dumps(valore, ensure_ascii=False)`; `<predefinito>` = `italiano`, la chiave del fuso, `nessuno stile`);
  - WARNING `preferenze: resource non disponibile (<motivo>), valori predefiniti`.
- Solo l'agente riceve il blocco; router, revisore e riassunto no. `bind_tools` riceve gli stessi strumenti di prima.
- `PROMPT_DI_SISTEMA` inizia con `"Sei l'assistente del laboratorio. "` (senza «rispondi sempre in italiano»).
- Nessuna variabile d'ambiente nuova. Nessun import di `pydantic`, `openai`, `httpx` in `assistente/`; `asyncio` solo in `client_mcp.py`.
- Comandi: `.\.venv\Scripts\python.exe -m pytest -q` (senza modello), `.\.venv\Scripts\python.exe -m pytest -m reale -v` (con LM Studio).
- Branch `feature/preferenze`; Conventional Commits in italiano con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; `git status` e diff prima di ogni commit, staging per percorso; niente merge né push.

## Review Focus
1. File salvato con BOM (PowerShell 5.1 `Set-Content -Encoding utf8`): letto normalmente, non «JSON non valido». Test in Task 1.
2. Valori con spazi o maiuscole (`" Dettagliato "`, `" America/New_York "`): accettati. Test in Task 3.
3. `fuso` non testo (`5`, `null`) o non IANA (`"Marte/Base"`, `"../etc"`): predefinito e WARNING, nessuna eccezione. Test in Task 3.
4. Testo JSON che non è un oggetto (`[]`, `"italiano"`, `42`) o vuoto: tutti i predefiniti con WARNING «resource non disponibile». Test in Task 3.
5. Ctrl+C durante la lettura all'avvio: esce come `KeyboardInterrupt`, non diventa «valori predefiniti». Test in Task 2.

---

### Task 1: server `preferenze_mcp` e `preferenze.json`

**Files:** Create `preferenze_mcp/__init__.py`, `preferenze_mcp/__main__.py`, `preferenze_mcp/server.py`, `preferenze.json`; Test `tests/test_preferenze_mcp.py`

**Interfaces — Produces:** `python -m preferenze_mcp [percorso]` (senza argomento: `preferenze.json` nella cartella corrente); `server.main(argv: list[str] | None = None) -> None` (`None` → `sys.argv[1:]`); resource `utente://preferenze` che restituisce `percorso.read_text(encoding="utf-8-sig")`.

- [ ] **Step 1: test che falliscono** in `tests/test_preferenze_mcp.py`, con un aiuto `col_server(operazione, *argomenti)` come in `tests/test_server_mcp.py` (avvio reale su stdio, `cwd` = radice del progetto):
  - `list_resources()` → una sola resource, `str(uri) == "utente://preferenze"`, `mimeType == "application/json"`; `list_tools().tools == []`;
  - lettura senza argomento → testo uguale a `preferenze.json` del progetto, e `json.loads` dà i tre valori versionati;
  - file in `tmp_path` passato come argomento, scritto con BOM (`"﻿{...}"` in UTF-8) → testo senza BOM (Review Focus 1);
  - file in `tmp_path` modificato tra due letture nella stessa sessione → la seconda lettura dà il testo nuovo;
  - percorso inesistente → `read_resource` solleva (`McpError`) e una `list_resources()` successiva nella stessa sessione risponde ancora.
  Run: `.\.venv\Scripts\python.exe -m pytest tests/test_preferenze_mcp.py -q` → falliscono.
- [ ] **Step 2: implementare.** `FastMCP("preferenze", log_level="WARNING")`; il percorso sta in una variabile del modulo impostata da `main`; `@server.resource("utente://preferenze", name="preferenze", mime_type="application/json")`; nessun import da `assistente/`; docstring come gli altri server (stdout riservato al protocollo). `preferenze.json` con i valori versionati.
- [ ] **Step 3:** test del file verdi, poi `.\.venv\Scripts\python.exe -m pytest -q` verde. **Step 4: commit** `feat(mcp): aggiunge il server delle preferenze con la resource utente://preferenze`.

### Task 2: lettura della resource nel client MCP

**Files:** Modify `assistente/client_mcp.py`; Test `tests/test_client_mcp.py`

**Interfaces:**
- Consumes: server del Task 1.
- Produces: `PREFERENZE = ServerMCP("preferenze", ("-m", "preferenze_mcp"), ())` (fuori da `SERVER_MCP`); `URI_PREFERENZE = "utente://preferenze"`; `leggi_resource_mcp(server: ServerMCP, uri: str) -> str`; `leggi_preferenze_mcp() -> str` (= `leggi_resource_mcp(PREFERENZE, URI_PREFERENZE)`).

- [ ] **Step 1: test che falliscono:**
  - `leggi_preferenze_mcp()` == testo di `preferenze.json` del progetto;
  - `leggi_resource_mcp(ServerMCP("preferenze", ("-m", "preferenze_mcp", str(file_tmp)), ()), URI_PREFERENZE)` == testo del file;
  - modulo inesistente (`("-m", "modulo_che_non_esiste")`) e file inesistente → `ErroreMCP` che inizia con
    `"resource utente://preferenze non letta dal server MCP preferenze (python"` e contiene il dettaglio dell'errore;
  - `PREFERENZE not in SERVER_MCP` e `carica_strumenti_mcp()` restituisce gli stessi nomi di strumenti di prima;
  - Ctrl+C durante la lettura (client finto con `get_resources` che usa `attesa_che_trasforma_la_cancellazione`, come il test della discovery) → `KeyboardInterrupt` (Review Focus 5).
- [ ] **Step 2: implementare** `leggi_resource_mcp`: stessa connessione stdio di `carica_server_mcp` (interprete corrente, `cwd` = `CARTELLA_PROGETTO`), `_esegui(client.get_resources(server.nome, uris=[uri]))`, testo con `blob.as_string()` del primo blob; nessun blob → `ErroreMCP` «… nessun contenuto». Ogni altra eccezione → `ErroreMCP(f"resource {uri} non letta dal server MCP {server.nome} ({comando}): {_dettaglio(errore)}")`, con `comando` costruito come in `carica_server_mcp`. Nessuna riga di log qui. Docstring del modulo: anche la resource delle preferenze.
- [ ] **Step 3:** suite verde. **Step 4: commit** `feat(mcp): legge la resource delle preferenze dal client MCP`.

### Task 3: modulo `preferenze.py`

**Files:** Create `assistente/preferenze.py`; Test `tests/test_preferenze.py`

**Interfaces — Produces:**
- `@dataclass(frozen=True) class Preferenze: lingua: str; fuso: ZoneInfo; stile: str | None`
- `predefinite(fuso: ZoneInfo) -> Preferenze` → `Preferenze("italiano", fuso, None)`
- `leggi_preferenze(testo: str, fuso_predefinito: ZoneInfo) -> Preferenze` — WARNING per campo; solleva `ValueError` con il motivo se il testo non è JSON o non è un oggetto
- `carica_preferenze(leggi: Callable[[], str], fuso_predefinito: ZoneInfo) -> Preferenze` — chiama `leggi()`, misura il tempo, scrive INFO; `ErroreMCP` o `ValueError` → WARNING «resource non disponibile» e `predefinite(...)`
- `blocco_preferenze(p: Preferenze) -> str`, testo esatto:
  `"Preferenze dell'utente: rispondi sempre in {lingua}. Il fuso orario predefinito dell'utente è {fuso.key}: per l'ora, la data o il giorno attuali senza una località indicata chiama ora_corrente con fuso {fuso.key}."` più, se `stile`, uno spazio e
  - `sintetico`: `"Stile: risposte brevi ed essenziali, senza tralasciare nulla di ciò che la domanda chiede."`
  - `dettagliato`: `"Stile: risposte dettagliate, con spiegazioni ed esempi quando aiutano, senza uscire dalla domanda."`

- [ ] **Step 1: test che falliscono** (fuso predefinito `ZoneInfo("Europe/Rome")`):
  - testo del file versionato → `Preferenze("italiano", ZoneInfo("Europe/Rome"), "sintetico")`, nessun WARNING;
  - `{"lingua": "inglese", "fuso": "America/New_York", "stile": "dettagliato", "colore": "blu"}` → valori presi, campo in più ignorato senza WARNING;
  - `{"lingua": " English ", "fuso": " America/New_York ", "stile": " Dettagliato "}` → `"English"`, New York, `"dettagliato"` (Review Focus 2);
  - parametrizzato, un campo alla volta: `lingua` `""`, `"   "`, `3`, `null`; `fuso` `5`, `null`, `"Marte/Base"`, `"../etc"`; `stile` `"breve"`, `1` → quel campo predefinito, gli altri presi, WARNING `preferenze: <campo> non valido («...»), si usa <predefinito>` (Review Focus 3);
  - `{}` → tre WARNING `... mancante, si usa ...` e `predefinite`;
  - `leggi_preferenze` con `"non json"`, `""`, `"[]"`, `"\"italiano\""`, `"42"` → `ValueError` (Review Focus 4);
  - `carica_preferenze(lambda: testo_valido, ...)` → INFO che inizia con `"preferenze: resource utente://preferenze letta in "` e finisce con `": lingua=italiano, fuso=Europe/Rome, stile=sintetico"`;
  - `carica_preferenze` con `leggi` che solleva `ErroreMCP("resource utente://preferenze non letta (...)")` e con testo `"[]"` → `predefinite(...)` e WARNING che inizia con `"preferenze: resource non disponibile ("` e finisce con `"), valori predefiniti"`;
  - `blocco_preferenze`: testo esatto con New York e inglese; con `stile=None` nessuna frase «Stile:»; con `sintetico` e `dettagliato` le frasi esatte.
- [ ] **Step 2: implementare.** Modulo sincrono; importa `ErroreMCP` da `assistente.client_mcp` solo per l'`except`. `ZoneInfo` su valori non validi può sollevare `ZoneInfoNotFoundError` o `ValueError`; i non-testo si scartano prima.
- [ ] **Step 3:** suite verde. **Step 4: commit** `feat(preferenze): controlla le preferenze lette dalla resource e ne costruisce il blocco del prompt`.

### Task 4: preferenze nel grafo, nel revisore e all'avvio

**Files:** Modify `assistente/grafo.py`, `assistente/__main__.py`, `revisore.txt`; Test `tests/test_grafo.py`, `tests/test_main.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: `carica_preferenze`, `blocco_preferenze` (Task 3), `leggi_preferenze_mcp` (Task 2).
- Produces: `costruisci_grafo(..., modello_riassunto=None, preferenze: str | None = None)`: con `preferenze` il prompt di sistema dell'agente è `preferenze + "\n\n" + PROMPT_DI_SISTEMA` (il riassunto resta nel messaggio successivo, `messaggi_di_contesto`).

- [ ] **Step 1: test che falliscono:**
  - `test_grafo.py`: `PROMPT_DI_SISTEMA.startswith("Sei l'assistente del laboratorio. ")` e `"italiano" not in PROMPT_DI_SISTEMA`; con `preferenze="Preferenze dell'utente: X."` il primo messaggio dell'agente è `"Preferenze dell'utente: X.\n\n" + PROMPT_DI_SISTEMA`; con router, revisore e riassunto attivi (soglia bassa) nessuno dei loro messaggi contiene `"Preferenze dell'utente"`, mentre l'agente lo riceve anche quando c'è un riassunto (secondo messaggio = riassunto); `strumenti_associati` uguale con e senza `preferenze`; senza `preferenze` il prompt è `PROMPT_DI_SISTEMA` (i test esistenti restano invariati).
  - `test_main.py`: nella fixture `ambiente_pulito` `monkeypatch.setattr(avvio, "leggi_preferenze_mcp", lambda: '{"lingua": "inglese", "fuso": "America/New_York"}')`; un test che cattura le opzioni di `costruisci_grafo` e trova in `preferenze` «rispondi sempre in inglese» e «America/New_York»; un test con `leggi_preferenze_mcp` che solleva `ErroreMCP` → `main()` == 0, il grafo riceve il blocco dei predefiniti (con `APP_TIMEZONE` del test) e c'è il WARNING «resource non disponibile».
  - `test_config.py`: `revisore.txt` del progetto contiene `"lingua"`; `preferenze.json` del progetto passa `leggi_preferenze` senza WARNING e dà i valori versionati.
- [ ] **Step 2: implementare.** `PROMPT_DI_SISTEMA`: `"Sei l'assistente del laboratorio. "` al posto di `"Sei l'assistente del laboratorio e rispondi sempre in italiano. "`. `__main__`: dopo il blocco `try` (quindi dopo modello e strumenti MCP) `preferenze = carica_preferenze(leggi_preferenze_mcp, config.fuso)` e `preferenze=blocco_preferenze(preferenze)` a `costruisci_grafo`; docstring di `main` aggiornata. `revisore.txt`: «In particolare non giudicare lo stile, la lunghezza, la lingua o la verità dei fatti…» e una frase: «La lingua della risposta non è mai un motivo per coerente=false: l'assistente può rispondere in una lingua diversa da quella della domanda.»
- [ ] **Step 3:** suite verde. **Step 4: commit** `feat(grafo): mette le preferenze dell'utente in cima al prompt dell'agente`.

### Task 5: prove reali con gemma

**Files:** Modify `tests/test_reale.py`

**Interfaces — Consumes:** `Preferenze`, `blocco_preferenze`, `carica_preferenze`, `leggi_preferenze_mcp`.

- [ ] **Step 1:** `crea_grafo(config, servizio_note, soglia, turni, preferenze: str)`; la fixture `grafo` passa `blocco_preferenze(carica_preferenze(leggi_preferenze_mcp, config.fuso))` (file versionato, server vero), le prove nuove un blocco costruito da `Preferenze(...)`, senza toccare il file.
- [ ] **Step 2: prove nuove** (`@pytest.mark.reale`):
  - `test_reale_preferenze_fuso`: `Preferenze("italiano", ZoneInfo("America/New_York"), "sintetico")`, «Che ore sono?» → una richiesta `ora_corrente` con `fuso == "America/New_York"` e nella risposta l'ora `HH:MM` del `ToolMessage`;
  - `test_reale_preferenze_lingua`: `Preferenze("inglese", ZoneInfo("Europe/Rome"), "sintetico")`, «Spiegami in due frasi a che cosa serve una centrifuga.» → risposta in inglese (almeno due tra `the`, `and`, `is`, `to` come parole, nessuna tra `il`, `che`, `è`, `una`); con il revisore attivo il turno finisce con la risposta (nessun `RispostaNonValida`, nessuna indicazione del revisore nella cronologia);
  - `test_reale_preferenze_stile`: stessa domanda con `sintetico` e con `dettagliato` → la dettagliata ha più parole.
  Run: `.\.venv\Scripts\python.exe -m pytest -m reale -v -k preferenze`. Se gemma ignora le preferenze in cima al prompt: script usa e getta su più casi; spostarle fuori dal prompt di sistema solo dopo averlo concordato con l'utente.
- [ ] **Step 3:** suite reale completa una volta, in background (`-m reale -v`), tutte verdi. **Step 4: commit** `test(reale): aggiunge le prove reali delle preferenze`.

### Task 6: Docker, documentazione e prove manuali

**Files:** Modify `Dockerfile`, `compose.yaml`, `README.md`, `CLAUDE.md`

- [ ] **Step 1:** `Dockerfile`: `COPY ambito.txt revisore.txt riassunto.txt preferenze.json ./` e `COPY preferenze_mcp/ preferenze_mcp/`. `compose.yaml`, servizio `assistente`: `volumes: - ./preferenze.json:/app/preferenze.json:ro`.
- [ ] **Step 2: pipe in PowerShell pulita** (script `.ps1` con `Remove-Item Env:PYTHONIOENCODING`, `-NoProfile`, `LOG_LEVEL=INFO`): «Che ore sono?» e «Spiegami in due frasi che cos'è una pipetta.» con il file versionato; poi file con `America/New_York`, `inglese`, `dettagliato`; stesse domande; il comportamento cambia; la riga `preferenze: resource utente://preferenze letta in` compare prima delle righe `nodo_llm`; poi file ripristinato (`git diff preferenze.json` vuoto).
- [ ] **Step 3: Docker:** `docker compose build`, stessa sequenza con `docker compose run --rm -T -e LOG_LEVEL=INFO assistente`, modificando il file sull'host tra le due sessioni senza ricostruire; `docker compose down`; file ripristinato. Nella stessa occasione la prova del riassunto rimasta in sospeso (`-e RIASSUNTO_SOGLIA=4 -e RIASSUNTO_TURNI=1`) e, se passa, via il paragrafo «Da provare in Docker». Se Docker non parte: annotarlo nel README come per il riassunto.
- [ ] **Step 4: documentazione.** README: sezione «Preferenze dell'utente (resource MCP)» con file, campi e valori ammessi, predefiniti e WARNING, righe di log, limite noto (calendario e note usano `APP_TIMEZONE`), modifica in Docker senza `build`; solo comandi eseguiti negli step 2–3. `CLAUDE.md`: `preferenze_mcp/`, `assistente/preferenze.py`, `preferenze.json`, il parametro `preferenze` di `costruisci_grafo`, la resource nel client MCP.
- [ ] **Step 5:** suite verde, `git status` pulito a parte i file del task. **Commit** `feat(docker): include il server e il file delle preferenze` (`Dockerfile`, `compose.yaml`) e `docs: documenta le preferenze dell'utente nel README e nel CLAUDE.md`.

### Dopo i task
Revisione finale dell'intero branch su `git diff 87c6f34..HEAD` (Review Focus 1–5, Global Constraints, spec); Critical/Important corretti con test RED→GREEN; resoconto con che cosa è stato eseguito, esito e che cosa resta. Merge in `dev` solo su richiesta.
