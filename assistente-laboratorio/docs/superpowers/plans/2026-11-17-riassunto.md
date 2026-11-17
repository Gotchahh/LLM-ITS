# Riassunto della cronologia — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** un nodo LLM `nodo_riassunto` all'inizio del turno che, oltre `RIASSUNTO_SOGLIA` messaggi, sostituisce i turni più vecchi con un riassunto (campo `riassunto` dello stato, sostituito e non accumulato) e lascia intatti gli ultimi `RIASSUNTO_TURNI` turni e la domanda in corso.

**Architecture:** `assistente/riassunto.py` contiene le funzioni pure: punto di taglio a inizio turno, trascrizione testuale, messaggi per il modello, aggiunta del riassunto a un prompt di sistema. In `costruisci_grafo` il nodo si attiva solo se riceve le istruzioni e si mette tra `START` e il nodo che oggi parte per primo (router o agente); usa `(modello_router or modello)` senza strumenti e toglie i messaggi riassunti con `RemoveMessage`. Agente e router ricevono il riassunto in coda al prompt di sistema. La CLI conserva cronologia e riassunto tra un turno e l'altro tramite `esegui_turno_con_riassunto`.

**Tech Stack:** Python 3.14.7, LangGraph (`add_messages`, `RemoveMessage`), `langchain_core`. Nessuna dipendenza nuova.

**Spec:** `docs/superpowers/specs/2026-11-17-riassunto-design.md`

## Global Constraints
- Variabili: `RIASSUNTO_FILE` (default `riassunto.txt`), `RIASSUNTO_SOGLIA` (intero ≥ 1, default 20), `RIASSUNTO_TURNI` (intero ≥ 1, default 2). Valore non valido → `ErroreConfigurazione` che nomina la variabile, codice 1, nessun traceback.
- Si riassume solo se `len(messaggi) > soglia` **e** il punto di taglio è > 0; altrimenti il modello del riassunto non viene chiamato.
- Il taglio cade sempre subito prima di un `HumanMessage`; si conservano la domanda in corso e i `turni` turni precedenti.
- Log: INFO `riassunto: 24 messaggi -> 7 in 8.1 s`; DEBUG `riassunto: 12 messaggi, sotto la soglia di 20`; DEBUG `riassunto: 22 messaggi, nessun turno da riassumere`; WARNING `riassunto: errore (<Tipo>), cronologia invariata`; WARNING `riassunto: risposta vuota, cronologia invariata`.
- Errore o testo vuoto del modello del riassunto: cronologia e riassunto invariati, il turno prosegue.
- Il revisore non riceve il riassunto; agente e router sì.
- `LIMITE_PASSAGGI = 21` (20 di prima più il nodo del riassunto).
- Nessun import di `pydantic`, `openai`, `httpx` in `assistente/`.
- Comandi: `.\.venv\Scripts\python.exe -m pytest -q` (senza modello), `-m pytest -m reale -v` (con LM Studio).
- Branch `feature/riassunto`; Conventional Commits in italiano con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; `git status` e diff prima di ogni commit, staging selettivo; niente merge né push.

## Review Focus
1. Turno fallito dopo una compressione riuscita (l'agente solleva): la CLI tiene cronologia **e** riassunto di prima. Test in Task 3.
2. Seconda compressione: il modello riceve il riassunto precedente e il nuovo lo sostituisce (nessuna concatenazione). Test in Task 2.
3. Turno rifiutato dal router (domanda + rifiuto) dentro la parte da riassumere: viene trascritto e tagliato come gli altri. Test in Task 2.
4. Turni con strumenti al confine del taglio: nessun `ToolMessage` orfano né `AIMessage` con `tool_calls` senza risposta nella cronologia restante. Test in Task 2.
5. `RIASSUNTO_SOGLIA="0"`, `"-3"`, `"venti"` e `RIASSUNTO_TURNI="0"`: errore all'avvio. Test in Task 1.

---

### Task 1: configurazione del riassunto

**Files:** Create `riassunto.txt`; Modify `assistente/config.py`, `.env.example`, `Dockerfile`; Test `tests/test_config.py`

**Interfaces — Produces:** `Configurazione.riassunto_file: Path = Path("riassunto.txt")`, `riassunto_soglia: int = 20`, `riassunto_turni: int = 2`; `leggi_riassunto(percorso: Path) -> str` (stesso aiuto `_leggi_testo`, messaggi con «del riassunto» e `RIASSUNTO_FILE`).

- [ ] **Step 1: test che falliscono** in `tests/test_config.py`: default dei tre campi; `RIASSUNTO_FILE=" r.txt "` → `Path("r.txt")`; `RIASSUNTO_SOGLIA=" 6 "` → 6, `RIASSUNTO_TURNI="1"` → 1; parametrizzato `("RIASSUNTO_SOGLIA", "0"|"-3"|"venti")` e `("RIASSUNTO_TURNI", "0"|"due")` → `ErroreConfigurazione` il cui messaggio contiene il nome della variabile; `leggi_riassunto` su file mancante e vuoto → `ErroreConfigurazione` con `RIASSUNTO_FILE`; `riassunto.txt` del progetto contiene `"nome"`.
  Run: `.\.venv\Scripts\python.exe -m pytest tests/test_config.py -q` → falliscono.
- [ ] **Step 2: implementare.** Un aiuto privato per gli interi ≥ 1 (accanto al controllo di `REVISIONI_MAX`, che resta ≥ 0). `riassunto.txt`: sei il componente che riassume la conversazione dell'assistente di laboratorio; ricevi l'eventuale riassunto precedente e una trascrizione; scrivi un unico riassunto aggiornato, in italiano, breve (al massimo una decina di righe), in terza persona; conserva informazioni stabili (nome e ruolo dell'utente, preferenze, decisioni, note salvate o cancellate, apparecchi e argomenti trattati, domande lasciate aperte); non conservare ora, data o risultati che invecchiano; non inventare; rispondi solo con il riassunto. `.env.example`: le tre variabili facoltative con un commento. `Dockerfile`: `COPY ambito.txt revisore.txt riassunto.txt ./`.
- [ ] **Step 3:** `.\.venv\Scripts\python.exe -m pytest -q` verde. **Step 4: commit** `feat(config): aggiunge le istruzioni, la soglia e i turni del riassunto`.

### Task 2: riassunto nel grafo

**Files:** Create `assistente/riassunto.py`; Modify `assistente/grafo.py`; Test `tests/test_riassunto.py`, `tests/test_grafo.py`

**Interfaces:**
- Produces (`riassunto.py`):
  - `punto_di_taglio(messaggi: list[AnyMessage], turni: int) -> int`: indice del `HumanMessage` che apre il turno `turni` posizioni prima di quello in corso (cioè il (`turni`+1)-esimo `HumanMessage` contando dalla fine); 0 se i `HumanMessage` sono ≤ `turni`.
  - `trascrivi(messaggi: list[AnyMessage]) -> str`: una riga per messaggio: `Utente: <testo>`; `Assistente: <testo>` per gli `AIMessage` con testo; `Assistente chiede lo strumento <nome> <argomenti JSON>` per ogni richiesta; `Strumento <nome>: <contenuto>` per i `ToolMessage`.
  - `messaggi_per_il_riassunto(istruzioni: str, precedente: str, trascrizione: str) -> list[AnyMessage]`: `SystemMessage(istruzioni)` + un `HumanMessage` «Riassunto precedente:\n<precedente o «nessuno»>\n\nConversazione da riassumere:\n<trascrizione>».
  - `con_riassunto(prompt: str, riassunto: str) -> str`: `prompt` invariato se `riassunto` è vuoto, altrimenti `prompt + "\n\nRiassunto della conversazione precedente (i turni più vecchi):\n" + riassunto`.
- Produces (`grafo.py`):
  - `Stato.riassunto: NotRequired[str]`.
  - `costruisci_grafo(..., revisioni_max: int = 2, riassunto_istruzioni: str | None = None, riassunto_soglia: int = 20, riassunto_turni: int = 2)`; con istruzioni: `START → nodo_riassunto →` (router se c'è, altrimenti `nodo_llm`); senza: grafo di oggi.
  - `nodo_riassunto` restituisce `{}` oppure `{"riassunto": <nuovo>, "messages": [RemoveMessage(id) per ogni messaggio prima del taglio]}`; chiama `(modello_router or modello).invoke(...)` e usa `.text.strip()`.
  - `nodo_llm` e `nodo_router` usano `con_riassunto(..., stato.get("riassunto", ""))` nel `SystemMessage`.
  - `esegui_turno_con_riassunto(grafo, cronologia: list[AnyMessage], riassunto: str, testo: str) -> tuple[list[AnyMessage], str]`; `esegui_turno` resta com'è (firma e ritorno) e delega con `riassunto=""`.
  - `LIMITE_PASSAGGI = 21`.

- [ ] **Step 1: test che falliscono.**
  - `tests/test_riassunto.py`: `punto_di_taglio` con 4 turni e `turni=2` → indice del secondo `HumanMessage`; con 2 turni e `turni=2` → 0; un turno con `AIMessage(tool_calls)` + `ToolMessage` prima del taglio resta tutto prima; `trascrivi` produce le quattro forme di riga; `messaggi_per_il_riassunto` con precedente vuoto contiene «nessuno», con precedente lo contiene; `con_riassunto("P", "")` → `"P"`, `con_riassunto("P", "R")` termina con `"R"`.
  - `tests/test_grafo.py` (agente `ModelloFinto`, riassunto con un secondo `ModelloFinto` passato come `modello_router`, `ambito=None`, `riassunto_istruzioni="RIASSUMI"`):
    - `test_riassunto_sotto_la_soglia_non_chiama_il_modello` (soglia 20, cronologia di 6 messaggi: `chiamate` del riassunto vuote, cronologia restituita = vecchia + domanda + risposta, riassunto `""`, DEBUG `sotto la soglia di 20`);
    - `test_riassunto_sopra_la_soglia` (soglia 6, turni 1, 4 turni precedenti da 2 messaggi: una chiamata con «RIASSUMI» e la trascrizione dei primi 3 turni; cronologia restituita = 4° turno + domanda + risposta; riassunto = testo del finto; INFO `riassunto: 9 messaggi -> 3`);
    - `test_riassunto_sostituisce_il_precedente` (riassunto in ingresso «Si chiama Ottavio.», finto risponde «Si chiama Ottavio; ha chiesto l'ora.»: la chiamata contiene il precedente, il riassunto restituito è esattamente il nuovo);
    - `test_riassunto_con_strumenti_non_lascia_orfani` (turni con `AIMessage(tool_calls=[…id "t1"])` + `ToolMessage(tool_call_id="t1")` prima e dopo il taglio: ogni `tool_call_id` restante ha la sua richiesta e viceversa);
    - `test_riassunto_sopra_la_soglia_senza_turni_da_tagliare` (soglia 2, turni 2, un solo turno precedente con strumenti: nessuna chiamata, DEBUG `nessun turno da riassumere`);
    - `test_riassunto_errore_o_vuoto_lascia_tutto_invariato` (parametrizzato `RuntimeError("giù")` / `AIMessage("  ")`: cronologia completa, riassunto precedente invariato, WARNING, la risposta dell'agente arriva);
    - `test_agente_e_router_ricevono_il_riassunto_il_revisore_no` (grafo con ambito, revisore e riassunto in ingresso «Si chiama Ottavio.»: il `SystemMessage` dell'agente e quello del router contengono «Ottavio», i messaggi del revisore no);
    - `test_turno_rifiutato_viene_riassunto` (un turno precedente risposto da `nodo_rifiuto` finisce nella trascrizione e viene tolto);
    - `test_senza_istruzioni_nessun_nodo_riassunto` (`"nodo_riassunto" not in grafo.get_graph().nodes`).
  - Run: `.\.venv\Scripts\python.exe -m pytest tests/test_riassunto.py tests/test_grafo.py -q` → falliscono.
- [ ] **Step 2:** implementare. Nei test il router finto riceve le sue decisioni dallo stesso `ModelloFinto` usato per il riassunto (`decisioni=` e `risposte=` sono code separate).
- [ ] **Step 3:** `.\.venv\Scripts\python.exe -m pytest -q` verde. **Step 4: commit** `feat(grafo): aggiunge il riassunto della cronologia all'inizio del turno`.

### Task 3: CLI e avvio

**Files:** Modify `assistente/cli.py`, `assistente/__main__.py`; Test `tests/test_cli.py`, `tests/test_main.py`

**Interfaces:**
- Consumes: `esegui_turno_con_riassunto` (Task 2); `leggi_riassunto`, `riassunto_file`, `riassunto_soglia`, `riassunto_turni` (Task 1).
- Produces: `esegui_chat` conserva `cronologia` e `riassunto` (stringa, `""` all'inizio) e li aggiorna insieme solo se il turno riesce; `main` legge `riassunto.txt` con gli altri file (errore → codice 1) e chiama `costruisci_grafo(..., config.revisioni_max, riassunto_istruzioni=…, riassunto_soglia=…, riassunto_turni=…)`.

- [ ] **Step 1: test che falliscono.**
  - `tests/test_cli.py`: `test_chat_passa_il_riassunto_al_turno_successivo` (grafo con riassunto, soglia 2, turni 1: dopo la compressione al terzo turno, il `SystemMessage` dell'agente al quarto turno contiene il testo del riassunto finto); `test_turno_fallito_conserva_cronologia_e_riassunto` (compressione riuscita e poi l'agente solleva: stampato l'errore; al turno dopo, la nuova chiamata al riassunto finto ha come precedente «nessuno» e trascrive di nuovo i messaggi che la compressione scartata aveva tolto).
  - `tests/test_main.py`: `test_main_passa_al_grafo_l_ambito_e_il_modello_del_router` accetta i nuovi argomenti con nome e verifica `"nome" in riassunto_istruzioni`, soglia 20, turni 2; `test_main_riassunto_mancante_uscita_1`; `test_main_riassunto_soglia_non_valida_uscita_1`; il fixture d'ambiente imposta `RIASSUNTO_FILE` al file del progetto come fa con `REVISORE_FILE`.
  - Run: `.\.venv\Scripts\python.exe -m pytest tests/test_cli.py tests/test_main.py -q` → falliscono.
- [ ] **Step 2:** implementare.
- [ ] **Step 3:** `.\.venv\Scripts\python.exe -m pytest -q` verde. **Step 4: commit** `feat(cli): conserva il riassunto tra un turno e l'altro`.

### Task 4: prove reali, pipe, Docker, documentazione

**Files:** Modify `tests/test_reale.py`, `README.md`, `CLAUDE.md`

- [ ] **Step 1:** `tests/test_reale.py`: la fixture `grafo` passa anche `riassunto_istruzioni` (file del progetto) e soglia e turni di `config` (le prove esistenti non arrivano alla soglia). Nuove prove:
  - `test_reale_riassunto_conserva_il_nome(config)`: modello del riassunto reale (`crea_modello_router`) chiamato direttamente su una trascrizione scritta dal test («Utente: Ciao, mi chiamo Ottavio e lavoro nel laboratorio di chimica.» / «Assistente: Piacere, Ottavio! …» / un turno sull'ora) → il testo contiene «Ottavio» e non contiene un orario `\d{1,2}:\d{2}`.
  - `test_reale_nome_dopo_la_compressione(config, servizio_note, caplog)`: grafo come la fixture ma con soglia 4 e turni 1; turni «Ciao, mi chiamo Ottavio.», «Quanto fa 12 per 7?», «Quanti centimetri sono 3 pollici?», «Come mi chiamo?» con `esegui_turno_con_riassunto`; il log contiene almeno un `riassunto: N messaggi -> M`, al quarto turno la cronologia non contiene più il primo `HumanMessage` e la risposta finale contiene «Ottavio».
  - Run: `.\.venv\Scripts\python.exe -m pytest -m reale -v` con LM Studio acceso → tutte passano; se il riassunto perde il nome, ritoccare `riassunto.txt`, non le asserzioni.
- [ ] **Step 2: pipe** in una PowerShell pulita, senza `PYTHONIOENCODING`, con `RIASSUNTO_SOGLIA=4` e `RIASSUNTO_TURNI=1` impostate solo per il comando: quattro righe come nella prova reale più `/esci`; nel log `riassunto: … -> …` e il nome nell'ultima risposta. Poi lo stesso con `docker compose run --rm assistente` (variabili passate con `-e`).
- [ ] **Step 3:** README: nella panoramica una riga sul riassunto; tabella di configurazione con le tre variabili; sezione «Riassunto della cronologia» (grafo, soglia e turni, che cosa conserva, log di esempio copiato dalla prova reale, cosa succede se fallisce); prove reali aggiornate con data; diagnosi (`riassunto: errore`, il nome si perde → ritoccare `riassunto.txt` o alzare `RIASSUNTO_TURNI`). `CLAUDE.md`: elenco delle variabili d'ambiente con `RIASSUNTO_FILE`, `RIASSUNTO_SOGLIA`, `RIASSUNTO_TURNI`.
- [ ] **Step 4:** `.\.venv\Scripts\python.exe -m pytest -q` verde; commit `test(reale): aggiunge le prove reali del riassunto` e `docs: documenta il riassunto nel README e nel CLAUDE.md`.
