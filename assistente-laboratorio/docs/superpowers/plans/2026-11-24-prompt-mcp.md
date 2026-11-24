# Prompt MCP come comandi della CLI — piano di implementazione

> **Esecuzione:** superpowers:executing-plans, task per task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** un server MCP `prompt_mcp` espone i prompt `spiega` e `riassumi_conversazione`; la CLI li elenca con `/prompts` e li richiama con `/prompt nome arg=valore`, controlla nomi e presenza degli argomenti senza chiamare il modello e manda il testo compilato al grafo come una domanda scritta a mano.

**Architecture:** `prompt_mcp/server.py` (FastMCP su stdio, due prompt, nessuno strumento né resource) compila il testo e rifiuta i valori non ammessi. `client_mcp.py` aggiunge la lettura dell'elenco (`prompts/list`, una volta all'avvio) e la richiesta di un prompt (`prompts/get`, a ogni `/prompt`). `assistente/prompt.py` (sincrono, senza MCP) legge la riga del comando, la controlla rispetto all'elenco, scrive il testo di `/prompts` e le righe di log; riceve le funzioni del client come argomenti. `cli.py` aggiunge i due comandi e passa il testo a `esegui_turno_con_riassunto`; il grafo non cambia.

**Tech Stack:** Python 3.14.7, `mcp` (FastMCP, già presente), `pydantic` (già installato come dipendenza di `mcp`; solo in `prompt_mcp/`), `langchain_mcp_adapters` 0.3.2 (`MultiServerMCPClient.session`, `get_prompt`). Nessuna dipendenza nuova.

**Spec:** `docs/superpowers/specs/2026-11-18-prompt-mcp-design.md`

## Global Constraints
- Prompt `spiega(argomento, livello="base")` (`livello`: `base`, `intermedio`, `avanzato`) e `riassumi_conversazione(stile)` (`stile`: `sintetico`, `dettagliato`). Il server controlla i valori; l'host solo nomi e presenza degli argomenti.
- Ogni prompt restituisce **un solo messaggio utente** di testo, in italiano.
- Elenco letto una volta all'avvio; se fallisce: WARNING, chat parte, codice 0, `/prompts` e `/prompt` disattivati.
- Nella cronologia va il testo compilato, mai la riga `/prompt …`. Un errore prima del grafo stampa `Errore: …`, non chiama il modello e lascia cronologia e riassunto invariati.
- Solo la parola del comando si confronta in minuscolo; nome del prompt, nomi e valori degli argomenti restano come scritti.
- Log (logger `assistente.prompt`):
  - INFO `prompt: elenco letto in 1.0 s: spiega(argomento, livello), riassumi_conversazione(stile)`;
  - INFO `prompt: spiega {"argomento": "Model Context Protocol", "livello": "base"} -> «<testo>»` (`json.dumps(..., ensure_ascii=False)`, testo con gli a capo sostituiti da spazi);
  - WARNING `prompt: elenco non disponibile (<motivo>), comandi /prompt disattivati`.
- `ambito.txt`: «… domande sulla conversazione in corso e richieste di riassumerla;».
- Nessuna variabile d'ambiente nuova. In `assistente/` nessun import di `pydantic`, `openai`, `httpx`; `asyncio` e `langchain_mcp_adapters` solo in `client_mcp.py`. `prompt_mcp/` non importa da `assistente/`.
- **Niente prove con il modello eseguite da Claude** (né `pytest -m reale`, né pipe, né Docker con il modello) e nessun test `reale` nuovo. Claude esegue `.\.venv\Scripts\python.exe -m pytest -q` e `docker compose build`.
- Branch `feature/prompt`; Conventional Commits in italiano con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; `git status` e diff prima di ogni commit, staging per percorso; niente merge né push.

## Review Focus
1. Apostrofi nei valori, frequenti in italiano (`argomento=l'entropia`, `argomento="l'effetto Doppler"`): accettati così come sono, non «riga mal scritta». Test in Task 3.
2. Maiuscole: `/PROMPT spiega argomento=x` e `/Prompts` riconosciuti; `livello=Base` o ` intermedio` accettati dal server; `/prompt Spiega …` è un prompt sconosciuto. Test in Task 1, 3 e 4.
3. Errore del server con il prefisso inglese di FastMCP (`Error rendering prompt spiega: …`): all'utente arriva solo il messaggio italiano. Test in Task 2.
4. Riga incompleta (`/prompt` da solo, `/prompt spiega argomento`, virgolette non chiuse `argomento="Model Context`, valore vuoto `argomento=` o `argomento=""`): errore con la sintassi corretta, nessuna chiamata al server né al modello. Test in Task 3.
5. Prompt disattivati: `/prompts` e `/prompt …` rispondono «non disponibili», la chat prosegue e una domanda normale arriva al modello. Test in Task 4.

---

### Task 1: server `prompt_mcp`

**Files:** Create `prompt_mcp/__init__.py`, `prompt_mcp/__main__.py`, `prompt_mcp/server.py`; Test `tests/test_prompt_mcp.py`

**Interfaces — Produces:** `python -m prompt_mcp`; `server.main() -> None`; prompt (descrizione = docstring di una riga):
- `spiega(argomento: Annotated[str, Field(description="concetto da spiegare")], livello: Annotated[str, Field(description="base (predefinito), intermedio o avanzato")] = "base")`, descrizione `Spiega un argomento al livello richiesto.`
- `riassumi_conversazione(stile: Annotated[str, Field(description="sintetico o dettagliato")])`, descrizione `Riassume la conversazione finora.`

Testi esatti (il valore è normalizzato con `strip().lower()` prima del controllo e nel testo):
- `spiega`: `Spiegami «{argomento}» a livello {livello}: {indicazione}` con
  - base: `usa parole semplici e un esempio concreto, senza formule.`
  - intermedio: `usa i termini tecnici principali spiegandoli, con un esempio.`
  - avanzato: `usa il linguaggio tecnico, con i dettagli, le formule se servono e i limiti.`
- `riassumi_conversazione`: `Riassumi la conversazione che abbiamo avuto finora, in modo {stile}: {indicazione}` con
  - sintetico: `pochi punti brevi con gli argomenti principali.`
  - dettagliato: `gli argomenti trattati, i risultati ottenuti e le decisioni prese, nell'ordine.`
- Valore non ammesso → `ValueError("livello non valido («esperto»): usa base, intermedio o avanzato")` / `ValueError("stile non valido («breve»): usa sintetico o dettagliato")` (valore originale tra «»).

- [ ] **Step 1: test che falliscono** in `tests/test_prompt_mcp.py`, con un aiuto `col_server(operazione)` come in `tests/test_preferenze_mcp.py` (avvio reale su stdio, `cwd` = radice):
  - `list_prompts()` → nomi `["spiega", "riassumi_conversazione"]`, le due descrizioni esatte; argomenti di `spiega`: `[("argomento", "concetto da spiegare", True), ("livello", "base (predefinito), intermedio o avanzato", False)]`; di `riassumi_conversazione`: `[("stile", "sintetico o dettagliato", True)]`;
  - `list_tools().tools == []` e `list_resources().resources == []`;
  - `get_prompt("spiega", {"argomento": "Model Context Protocol", "livello": "base"})` → un solo messaggio, `role == "user"`, testo uguale alla frase base esatta;
  - `get_prompt("spiega", {"argomento": "pH"})` → testo con «a livello base»;
  - `livello` `"Base"` e `" intermedio "` → testo con «a livello base» / «a livello intermedio» (Review Focus 2);
  - `get_prompt("riassumi_conversazione", {"stile": "dettagliato"})` → frase dettagliata esatta;
  - `livello="esperto"` e `stile="breve"` → `McpError` il cui messaggio contiene il testo italiano esatto; una `list_prompts()` successiva nella stessa sessione risponde ancora.
  Run: `.\.venv\Scripts\python.exe -m pytest tests/test_prompt_mcp.py -q` → falliscono.
- [ ] **Step 2: implementare.** `FastMCP("prompt", log_level="CRITICAL")` (commento come in `preferenze_mcp/server.py`: lo stderr del server finisce nel terminale della chat); `@server.prompt()` restituisce una `str` (FastMCP la rende messaggio utente); `main()` → `server.run(transport="stdio")`; `__main__.py` come quello delle preferenze. Docstring del modulo: stdout riservato al protocollo, nessun import da `assistente/`.
- [ ] **Step 3:** test del file verdi, poi `.\.venv\Scripts\python.exe -m pytest -q` verde. **Step 4: commit** `feat(mcp): aggiunge il server dei prompt spiega e riassumi_conversazione`.

### Task 2: elenco e richiesta dei prompt nel client MCP

**Files:** Modify `assistente/client_mcp.py`; Test `tests/test_client_mcp.py`

**Interfaces:**
- Consumes: server del Task 1.
- Produces:
  - `PROMPT = ServerMCP("prompt", ("-m", "prompt_mcp"), ())` (fuori da `SERVER_MCP`);
  - `@dataclass(frozen=True) class ArgomentoPrompt: nome: str; descrizione: str; obbligatorio: bool` (`descrizione` `""` se il server non la dà);
  - `@dataclass(frozen=True) class DefinizionePrompt: nome: str; descrizione: str; argomenti: tuple[ArgomentoPrompt, ...]`;
  - `leggi_elenco_prompt(server: ServerMCP = PROMPT) -> list[DefinizionePrompt]`;
  - `richiedi_prompt(nome: str, argomenti: dict[str, str], server: ServerMCP = PROMPT) -> str`.

- [ ] **Step 1: test che falliscono:**
  - `leggi_elenco_prompt()` → due `DefinizionePrompt` con nomi, descrizioni e argomenti del Task 1;
  - `richiedi_prompt("spiega", {"argomento": "Model Context Protocol", "livello": "base"})` == frase base esatta;
  - `richiedi_prompt("spiega", {"argomento": "pH", "livello": "esperto"})` → `ErroreMCP` con messaggio esatto `"prompt spiega non letto dal server MCP prompt: livello non valido («esperto»): usa base, intermedio o avanzato"` (niente `Error rendering prompt`, Review Focus 3);
  - `leggi_elenco_prompt(ServerMCP("prompt", ("-m", "modulo_che_non_esiste"), ()))` → `ErroreMCP` che inizia con `"elenco dei prompt non letto dal server MCP prompt (python"` e ha un dettaglio non vuoto dopo `"): "`; stessa cosa per `richiedi_prompt("spiega", {"argomento": "x"}, quel_server)` (inizio `"prompt spiega non letto dal server MCP prompt (python"`);
  - client finto con `get_prompt` che restituisce due messaggi, o un `AIMessage` → `ErroreMCP` che finisce con `"risposta inattesa (atteso un solo messaggio utente di testo)"`;
  - `PROMPT not in SERVER_MCP`;
  - Ctrl+C durante `richiedi_prompt` (client finto con `attesa_che_trasforma_la_cancellazione`, come il test delle preferenze) → `KeyboardInterrupt`.
- [ ] **Step 2: implementare.** Stessa connessione stdio (`_connessione`). Elenco: `async with client.session(server.nome) as s: return await s.list_prompts()` dentro `_esegui`; ogni errore → `ErroreMCP(f"elenco dei prompt non letto dal server MCP {server.nome} ({_comando(server)}): {_causa_prima(errore)}")`. Richiesta: `_esegui(client.get_prompt(server.nome, nome, arguments=argomenti))`. Se la causa più interna è un `McpError` (il server ha risposto con un errore) → `ErroreMCP(f"prompt {nome} non letto dal server MCP {server.nome}: {motivo}")` con `motivo = PREFISSO_PROMPT.sub("", str(causa))`, `PREFISSO_PROMPT = re.compile(r"^Error rendering prompt \S+: ")`; ogni altro errore (server che non parte) → `ErroreMCP(f"prompt {nome} non letto dal server MCP {server.nome} ({_comando(server)}): {_causa_prima(errore)}")`. Risposta valida solo se è un unico `HumanMessage` con `content` stringa. Nessuna riga di log qui. Docstring del modulo: anche i prompt.
- [ ] **Step 3:** suite verde. **Step 4: commit** `feat(mcp): legge l'elenco dei prompt e richiede un prompt dal client MCP`.

### Task 3: modulo `prompt.py`

**Files:** Create `assistente/prompt.py`; Test `tests/test_prompt.py`

**Interfaces:**
- Consumes: `DefinizionePrompt`, `ArgomentoPrompt`, `ErroreMCP` (Task 2), solo come tipi e per l'`except`.
- Produces:
  - `class ErrorePrompt(Exception)` — richiesta sbagliata, messaggio in italiano pronto per `Errore: …`;
  - `leggi_comando(resto: str) -> tuple[str, dict[str, str]]` — `resto` è la riga dopo la parola `/prompt`;
  - `controlla(nome: str, argomenti: dict[str, str], elenco: Sequence[DefinizionePrompt]) -> None`;
  - `righe_elenco(elenco: Sequence[DefinizionePrompt]) -> list[str]`;
  - `carica_prompt(leggi: Callable[[], list[DefinizionePrompt]]) -> list[DefinizionePrompt] | None` — INFO o WARNING come nei Global Constraints; `None` se `leggi` solleva `ErroreMCP`;
  - `compila_prompt(resto: str, elenco, richiedi: Callable[[str, dict[str, str]], str]) -> str` — `leggi_comando`, `controlla`, `richiedi`, INFO; propaga `ErrorePrompt` ed `ErroreMCP`.

Sintassi: `nome` = primo token senza `=`; poi zero o più `chiave=valore` separati da spazi, con valore `"[^"]+"` (virgolette tolte) oppure una sequenza non vuota senza spazi né `"`. Qualsiasi altra cosa → `ErrorePrompt("riga non valida. Scrivi /prompt nome argomento=valore (virgolette doppie per i valori con spazi).")`. Si legge con una regex ancorata ripetuta sulla riga, non con `shlex` (gli apostrofi romperebbero `shlex`).

Messaggi esatti di `controlla` (tutti finiscono con ` Scrivi /prompts per l'elenco.`):
- `il prompt {nome} non esiste.`
- `al prompt {nome} manca l'argomento obbligatorio {arg}.` (il primo mancante nell'ordine del server)
- `il prompt {nome} non ha l'argomento {arg}.`
- argomento ripetuto (rilevato da `leggi_comando`): `ErrorePrompt("l'argomento {arg} è ripetuto.")`

`righe_elenco`, per ogni prompt: `{nome}({arg, …}): {descrizione}` con i facoltativi come `[arg]`; poi, se almeno un argomento ha una descrizione, `  {arg}: {descrizione}; {arg}: {descrizione}` (solo quelli con descrizione).

- [ ] **Step 1: test che falliscono** (elenco costruito a mano con le definizioni del Task 1):
  - `leggi_comando('spiega argomento="Model Context Protocol" livello=base')` → `("spiega", {"argomento": "Model Context Protocol", "livello": "base"})`; `leggi_comando("riassumi_conversazione stile=sintetico")`; spazi multipli e tab tra le coppie accettati;
  - `argomento=l'entropia` e `argomento="l'effetto Doppler"` → valori con l'apostrofo (Review Focus 1);
  - `""`, `"spiega argomento"`, `'spiega argomento="Model Context'`, `"spiega argomento="`, `'spiega argomento=""'`, `"spiega =x"` → `ErrorePrompt` riga non valida (Review Focus 4);
  - `spiega argomento=a argomento=b` → `ErrorePrompt` ripetuto;
  - `controlla`: `"Spiega"` e `"saluta"` → non esiste (Review Focus 2); `spiega` con solo `livello` → manca `argomento`; `spiega` con `colore` → non ha l'argomento `colore`; `spiega` con solo `argomento` → nessun errore;
  - `righe_elenco` → esattamente le quattro righe dell'esempio della spec;
  - `carica_prompt(lambda: elenco)` → `elenco` e INFO che inizia con `"prompt: elenco letto in "` e finisce con `" s: spiega(argomento, livello), riassumi_conversazione(stile)"`; con `leggi` che solleva `ErroreMCP("x")` → `None` e WARNING `"prompt: elenco non disponibile (x), comandi /prompt disattivati"`;
  - `compila_prompt` con `richiedi` finto che restituisce `"Riga 1\nRiga 2"` → `"Riga 1\nRiga 2"`, `richiedi` chiamato con nome e dizionario, INFO esatto `prompt: spiega {"argomento": "l'entropia"} -> «Riga 1 Riga 2»`; con riga sbagliata `richiedi` non viene chiamato.
- [ ] **Step 2: implementare.** Modulo sincrono, logger `logging.getLogger(__name__)`.
- [ ] **Step 3:** suite verde. **Step 4: commit** `feat(prompt): legge e controlla il comando /prompt e scrive l'elenco dei prompt`.

### Task 4: comandi nella CLI, avvio e ambito

**Files:** Modify `assistente/cli.py`, `assistente/__main__.py`, `ambito.txt`, `tests/conftest.py`; Test `tests/test_cli.py`, `tests/test_main.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: `compila_prompt`, `righe_elenco`, `carica_prompt`, `ErrorePrompt` (Task 3); `leggi_elenco_prompt`, `richiedi_prompt`, `ErroreMCP` (Task 2).
- Produces: `esegui_chat(grafo, server, leggi=input, scrivi=print, attesa=None, livello_log=..., elenco_prompt: list[DefinizionePrompt] | None = None, richiedi_prompt: Callable[[str, dict[str, str]], str] | None = None)`; `COMANDO_PROMPTS = "/prompts"`, `COMANDO_PROMPT = "/prompt"`; `MESSAGGIO_PROMPT_NON_DISPONIBILI = "I prompt non sono disponibili: il server dei prompt non è partito all'avvio."`. Nella CLI i prompt sono disattivati se `elenco_prompt is None`.

Comandi: la prima parola della riga, in minuscolo; `/prompt` prende il resto della riga così com'è; `/esci`, `/log`, `/prompts` restano confronti su tutta la riga in minuscolo come oggi. «Comando sconosciuto. Comandi disponibili: /esci, /log, /prompts, /prompt».

- [ ] **Step 1: test che falliscono.** `conftest.chat(..., **opzioni)` inoltra le opzioni a `esegui_chat`. In `test_cli.py`, con `ModelloFinto` ed elenco a mano:
  - `/prompts` (e `/Prompts`) → le righe di `righe_elenco`, nessuna chiamata al modello;
  - `/PROMPT spiega argomento="Model Context Protocol"` con `richiedi` finto che restituisce `"Spiegami «Model Context Protocol» a livello base: …"` → il primo `human` ricevuto dal modello ha quel testo, la risposta si stampa, e al turno dopo la cronologia contiene quel testo e non `/prompt` (Review Focus 2);
  - con un indicatore di attesa finto la scritta compare anche nel turno del prompt;
  - `/prompt spiega livello=base` → `"Errore: al prompt spiega manca l'argomento obbligatorio argomento. Scrivi /prompts per l'elenco."`, nessuna chiamata a modello né a `richiedi`; una domanda successiva arriva al modello con cronologia `["system", "human"]`;
  - `richiedi` che solleva `ErroreMCP("prompt spiega non letto dal server MCP prompt: livello non valido («esperto»): usa base, intermedio o avanzato")` → `"Errore: "` + quel messaggio, nessuna chiamata al modello;
  - senza elenco (`None`): `/prompts` e `/prompt spiega argomento=x` → `MESSAGGIO_PROMPT_NON_DISPONIBILI`, poi una domanda normale risponde (Review Focus 5);
  - `test_comandi_normalizzati_e_sconosciuti` aggiornato al nuovo «Comando sconosciuto»; `/esci ora` resta sconosciuto.
  - `test_main.py`: nella fixture `ambiente_pulito` `monkeypatch.setattr(avvio, "leggi_elenco_prompt", lambda: ELENCO)`; un test che cattura le opzioni di `esegui_chat` e trova `elenco_prompt == ELENCO` e `richiedi_prompt is avvio.richiedi_prompt`; un test con `leggi_elenco_prompt` che solleva `ErroreMCP` → `main() == 0`, `elenco_prompt is None`, WARNING «prompt: elenco non disponibile».
  - `test_config.py`: `ambito.txt` del progetto contiene `"domande sulla conversazione in corso e richieste di riassumerla"`.
- [ ] **Step 2: implementare.** `cli.py`: il turno di una domanda e quello di un prompt usano lo stesso blocco (attesa ed errori del turno invariati); `ErrorePrompt` ed `ErroreMCP` di `compila_prompt` → `scrivi(f"Errore: {errore}")` prima del grafo. `__main__.py`: dopo le preferenze `elenco_prompt = carica_prompt(leggi_elenco_prompt)`, passato con `richiedi_prompt` a `esegui_chat`; docstring di `main` aggiornata. `ambito.txt`: la frase dei Global Constraints.
- [ ] **Step 3:** suite verde. **Step 4: commit** `feat(cli): aggiunge i comandi /prompts e /prompt`.

### Task 5: Docker, prove manuali e documentazione

**Files:** Modify `Dockerfile`, `README.md`, `CLAUDE.md`

- [ ] **Step 1:** `Dockerfile`: `COPY prompt_mcp/ prompt_mcp/` dopo `preferenze_mcp/`; `compose.yaml` invariato. Claude lancia `docker compose build` → termina senza errori.
- [ ] **Step 2: prove manuali in locale (le fa l'utente, un passo alla volta).** Claude dà il comando PowerShell da incollare nel terminale di VS Code (prima la riga UTF-8 del README, poi `.\.venv\Scripts\python.exe -m assistente` con `LOG_LEVEL=INFO`) e che cosa deve vedere, e aspetta l'output incollato:
  1. `/prompts` → i due prompt come nell'esempio della spec; `/prompt spiega argomento="Model Context Protocol" livello=base` → risposta semplice, log `prompt: spiega {…} -> «…»` seguito dalle righe del router e del revisore;
  2. due domande normali, poi `/prompt riassumi_conversazione stile=sintetico` → il riassunto cita le due domande.
  Se una prova non passa: si analizza l'output con l'utente prima di cambiare codice o testi.
- [ ] **Step 3: prova Docker manuale (utente).** `docker compose run --rm --name assistente-demo -e LOG_LEVEL=INFO assistente` e la prova 1.
- [ ] **Step 4: documentazione.** README: sezione «Prompt MCP (comandi /prompts e /prompt)» con i due prompt, argomenti e valori, sintassi (virgolette doppie), errori senza modello, righe di log, comportamento se il server non parte; i comandi nuovi nella sezione dei comandi della chat; solo comandi provati negli step 1–3. `CLAUDE.md`: `prompt_mcp/`, `assistente/prompt.py`, i prompt nel client MCP, i comandi `/prompts` e `/prompt` in `cli.py`.
- [ ] **Step 5:** suite verde, `git status` pulito a parte i file del task. **Commit** `feat(docker): include il server dei prompt` (`Dockerfile`) e `docs: documenta i prompt MCP nel README e nel CLAUDE.md`.

### Dopo i task
Revisione finale dell'intero branch su `git diff d630449..HEAD` (Review Focus 1–5, Global Constraints, spec); Critical/Important corretti con test RED→GREEN; resoconto con che cosa è stato eseguito, esito e che cosa resta. Merge in `dev` solo su richiesta.
