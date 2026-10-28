# Assistente del laboratorio — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** chat da terminale con grafo LangGraph esplicito, modello locale in LM Studio, cronologia di
sessione, strumento orologio richiesto via tool calling e avvio con Docker Compose.

**Architecture:** pacchetto `assistente/` con moduli separati per configurazione, collegamento al modello,
strumenti, grafo e terminale. Il grafo riceve il modello dall'esterno (nei test un modello finto). La CLI
conserva la cronologia e la ripassa al grafo a ogni turno; nessun checkpointer.

**Tech Stack:** Python 3.14.7, LangGraph, langchain-openai (`ChatOpenAI` verso l'API compatibile OpenAI di
LM Studio), pytest, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-26-assistente-laboratorio-design.md`

## Global Constraints

- Tutti i percorsi sono relativi a `assistente-laboratorio/`; i comandi si eseguono da lì, in PowerShell.
- Python 3.14.7: ambiente con `py -3.14 -m venv .venv`; si usa `.\.venv\Scripts\python.exe` direttamente
  (niente `Activate.ps1`, che la policy di esecuzione può bloccare). Immagine Docker `python:3.14.7-slim`.
- `requirements.txt` contiene **solo** le dipendenze concordate: `langgraph==1.2.17`, `langchain-openai==1.7.2`,
  `tzdata==2026.5`, `python-dotenv==1.2.4`. `requirements-dev.txt`: `-r requirements.txt`, `pytest==9.1.1`.
  Nessun'altra libreria viene aggiunta o importata direttamente: in particolare **non** si importano
  `openai`, `httpx` né `pydantic`. Unica eccezione obbligata: i tipi dei messaggi e degli strumenti (`AIMessage`,
  `HumanMessage`, `SystemMessage`, `ToolMessage`, `StructuredTool`) si importano da `langchain_core`, il
  pacchetto base che langgraph e langchain-openai installano da sé e che usano come formato dei messaggi;
  non va in `requirements.txt` e la sua versione la decide langchain-openai.
- Variabili: `LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL`, `APP_TIMEZONE` obbligatorie; `LOG_LEVEL` facoltativa
  (default `INFO`). Nessuna credenziale; chiave API segnaposto `lm-studio` nel codice.
- Codice sincrono; messaggi, log e testi in italiano.
- Formato log: `[%(levelname)s] %(message)s` su stderr; dialogo su stdout con `Tu> ` e `Assistente> `.
- `LIMITE_PASSAGGI = 10` (`recursion_limit`); temperatura 0; timeout del modello `180.0` s (un solo valore:
  un server spento rifiuta subito la connessione, e all'avvio lo rileva già il controllo con timeout 5 s),
  `max_retries=1`.
- Git: solo branch `main`, nessun worktree; prima di ogni commit `git status`, `git diff --cached`, staging
  dei soli file del task; Conventional Commits in italiano con riga `Co-Authored-By`; nessun push.
  `LLM_Lez_3.pdf` e `.env` mai in staging.
- README aggiornato nel task che introduce un comando, con soli comandi eseguiti in quel task.
- Test reali: marcatore `reale`, esclusi di default; un fallimento reale si riporta, non si simula.

## Review Focus

1. Riga di soli spazi o tabulazioni → ignorata, nessuna chiamata al modello (test nel Task 4).
2. Ctrl+C mentre si attende il modello → saluto e uscita pulita, nessun traceback (test nel Task 4).
3. `.env` assente in un clone nuovo → errore che nomina le variabili mancanti e `.env.example`, non un
   traceback (test nel Task 2).
4. URL con barra finale (`http://localhost:1234/v1/`) → normalizzato, l'elenco modelli si legge da
   `.../v1/models` senza doppia barra (test nel Task 2).
5. `LOG_LEVEL=info` in minuscolo → accettato come `INFO` (test nel Task 2).

---

### Task 1: Struttura del progetto e grafo con risposta fissa

**Files:**
- Create: `.gitignore`, `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, `README.md`
- Create: `assistente/__init__.py`, `assistente/grafo.py`, `assistente/cli.py`, `assistente/__main__.py`
- Test: `tests/test_grafo.py`

**Interfaces:**
- Produces: `grafo.Stato` (TypedDict con `messages: Annotated[list[AnyMessage], add_messages]`);
  `grafo.RISPOSTA_FISSA = "Il grafo è in esecuzione."`; `grafo.costruisci_grafo_fisso() -> CompiledStateGraph`
  con un nodo `nodo_risposta` (START → nodo_risposta → END) che aggiunge `AIMessage(RISPOSTA_FISSA)`;
  `cli.esegui_chat(grafo, leggi=input, scrivi=print) -> None` (versione minima: ciclo, `/esci`, fine input).

- [ ] **Step 1: Preparare ambiente e file di progetto**
  `.gitignore` con `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`. `pyproject.toml` contiene solo
  `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `pythonpath = ["."]`,
  `markers = ["reale: prove con LM Studio attivo"]`, `addopts = "-m 'not reale'"`.
  Run: `py -3.14 -m venv .venv` poi `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`
  poi `.\.venv\Scripts\python.exe -m pip check`. Expected: `No broken requirements found.`
  Se le versioni fissate sono incompatibili: fermarsi e proporre all'utente le versioni corrette.
- [ ] **Step 2: Scrivere il test che fallisce**

```python
def test_grafo_fisso_restituisce_la_risposta_prevista():
    grafo = costruisci_grafo_fisso()
    risultato = grafo.invoke({"messages": [HumanMessage("ciao")]})
    assert [m.type for m in risultato["messages"]] == ["human", "ai"]
    assert risultato["messages"][-1].content == RISPOSTA_FISSA
```

- [ ] **Step 3:** `.\.venv\Scripts\python.exe -m pytest tests/test_grafo.py -v` → FAIL (import).
- [ ] **Step 4: Implementare** `Stato`, `RISPOSTA_FISSA`, `costruisci_grafo_fisso()` e `esegui_chat` minima;
  `__main__.py` chiama `esegui_chat(costruisci_grafo_fisso())`. `esegui_chat` stampa
  `Assistente> <contenuto>` e alla fine `Alla prossima!`.
- [ ] **Step 5:** pytest → PASS. Prova: `"ciao`n/esci" | .\.venv\Scripts\python.exe -m assistente`
  → stampa `Assistente> Il grafo è in esecuzione.` e `Alla prossima!`.
- [ ] **Step 6: README** — requisiti (Python 3.14.7), creazione venv, installazione, `python -m pytest`,
  avvio: solo i comandi eseguiti negli step 1 e 5.
- [ ] **Step 7: Commit** `feat(grafo): aggiunge il grafo con risposta fissa e la chat minima`
  (file del task, nessun `.venv`).

### Task 2: Configurazione e log

**Files:**
- Create: `assistente/config.py`, `.env.example`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `config.ErroreConfigurazione(ValueError)`;
  `@dataclass(frozen=True) config.Configurazione(base_url: str, modello: str, fuso: ZoneInfo, livello_log: str)`;
  `config.leggi_file_env(percorso: Path) -> dict[str, str]` (`dotenv_values` con `encoding="utf-8-sig"`,
  `{}` se il file non esiste, valori `None` scartati);
  `config.carica_configurazione(ambiente: Mapping[str, str]) -> Configurazione`
  (spazi tolti, valore vuoto = mancante, URL senza barra finale, `livello_log` in maiuscolo tra
  `DEBUG/INFO/WARNING/ERROR`, default `INFO`);
  `config.configura_log(livello: str) -> None` (`logging.basicConfig(level=WARNING, format=..., stream=sys.stderr, force=True)`
  e `logging.getLogger("assistente").setLevel(livello)`). I moduli loggano con `logging.getLogger(__name__)`.

- [ ] **Step 1: Scrivere i test che falliscono**

```python
VALIDO = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "google/gemma-4-e4b",
          "APP_TIMEZONE": "Europe/Rome"}

def test_configurazione_valida():
    c = carica_configurazione(VALIDO)
    assert (c.base_url, c.modello, c.fuso.key, c.livello_log) == (
        "http://localhost:1234/v1", "google/gemma-4-e4b", "Europe/Rome", "INFO")

def test_ambiente_vuoto_nomina_variabili_e_file_di_esempio():          # Review Focus 3
    with pytest.raises(ErroreConfigurazione) as e:
        carica_configurazione({})
    for atteso in ("LMSTUDIO_BASE_URL", "LMSTUDIO_MODEL", "APP_TIMEZONE", ".env.example"):
        assert atteso in str(e.value)

def test_modello_vuoto_e_mancante():
    with pytest.raises(ErroreConfigurazione, match="LMSTUDIO_MODEL"):
        carica_configurazione({**VALIDO, "LMSTUDIO_MODEL": "  "})

def test_url_senza_schema_rifiutato():
    with pytest.raises(ErroreConfigurazione, match="LMSTUDIO_BASE_URL"):
        carica_configurazione({**VALIDO, "LMSTUDIO_BASE_URL": "localhost:1234/v1"})

def test_url_con_barra_finale_normalizzato():                          # Review Focus 4
    assert carica_configurazione({**VALIDO, "LMSTUDIO_BASE_URL": "http://localhost:1234/v1/"}).base_url \
        == "http://localhost:1234/v1"

def test_fuso_non_valido():
    with pytest.raises(ErroreConfigurazione, match="APP_TIMEZONE"):
        carica_configurazione({**VALIDO, "APP_TIMEZONE": "Roma"})

def test_livello_log_minuscolo_accettato():                            # Review Focus 5
    assert carica_configurazione({**VALIDO, "LOG_LEVEL": "info"}).livello_log == "INFO"

def test_livello_log_non_valido():
    with pytest.raises(ErroreConfigurazione, match="LOG_LEVEL"):
        carica_configurazione({**VALIDO, "LOG_LEVEL": "TANTO"})

def test_file_env_con_bom_e_crlf(tmp_path):
    f = tmp_path / ".env"
    f.write_bytes("\ufeffLMSTUDIO_MODEL=google/gemma-4-e4b\r\nAPP_TIMEZONE=Europe/Rome\r\n".encode("utf-8"))
    assert leggi_file_env(f) == {"LMSTUDIO_MODEL": "google/gemma-4-e4b", "APP_TIMEZONE": "Europe/Rome"}

def test_file_env_assente(tmp_path):
    assert leggi_file_env(tmp_path / "manca.env") == {}

def test_log_esterni_restano_a_warning():
    configura_log("INFO")
    assert logging.getLogger("assistente.grafo").isEnabledFor(logging.INFO)
    assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)

def test_modalita_silenziosa():
    configura_log("WARNING")
    assert not logging.getLogger("assistente.grafo").isEnabledFor(logging.INFO)
```

  I due test su `configura_log` usano una fixture che salva e ripristina handler e livelli della radice e
  del logger `assistente`, così non influenzano gli altri test (né `caplog`).
- [ ] **Step 2:** pytest `tests/test_config.py` → FAIL.
- [ ] **Step 3: Implementare** `config.py` come da Interfaces. `.env.example` con i valori d'esempio della
  specifica (`http://localhost:1234/v1`, `google/gemma-4-e4b`, `Europe/Rome`, `INFO`) e un commento che
  rimanda a `GET /v1/models`.
- [ ] **Step 4:** pytest completo → PASS.
- [ ] **Step 5: README** — sezione Configurazione: `Copy-Item .env.example .env`, significato delle variabili,
  le due modalità di log, verifica del modello con `Invoke-RestMethod http://localhost:1234/v1/models`
  (eseguire il comando prima di documentarlo).
- [ ] **Step 6: Commit** `feat(config): legge e valida la configurazione e i livelli di log`.

### Task 3: Collegamento a LM Studio e controllo all'avvio

**Files:**
- Create: `assistente/modello.py`
- Test: `tests/test_modello.py`

**Interfaces:**
- Consumes: `Configurazione`, `ErroreConfigurazione` (Task 2).
- Produces: `modello.ErroreServer(RuntimeError)`;
  `modello.estrai_identificativi(corpo: bytes) -> list[str]` (campo `data[].id` della risposta JSON);
  `modello.leggi_modelli_disponibili(base_url: str, timeout: float = 5.0) -> list[str]`
  (`urllib.request` su `f"{base_url}/models"`; `URLError`, timeout o JSON non valido → `ErroreServer` con l'URL);
  `modello.verifica_modello(modello: str, disponibili: list[str]) -> None`
  (assente → `ErroreConfigurazione` che elenca i disponibili);
  `modello.crea_modello(config: Configurazione) -> ChatOpenAI`
  (`model`, `base_url`, `api_key="lm-studio"`, `temperature=0`, `timeout=180.0`, `max_retries=1`).

- [ ] **Step 1: Scrivere i test che falliscono**

```python
def test_estrai_identificativi():
    corpo = b'{"data": [{"id": "google/gemma-4-e4b"}, {"id": "google/gemma-4-e2b"}], "object": "list"}'
    assert estrai_identificativi(corpo) == ["google/gemma-4-e4b", "google/gemma-4-e2b"]

def test_estrai_identificativi_json_non_valido():
    with pytest.raises(ErroreServer):
        estrai_identificativi(b"<html>")

def test_modello_presente():
    verifica_modello("google/gemma-4-e4b", ["google/gemma-4-e4b"])

def test_modello_assente_elenca_i_disponibili():
    with pytest.raises(ErroreConfigurazione) as e:
        verifica_modello("gemma", ["google/gemma-4-e4b", "google/gemma-4-e2b"])
    assert "google/gemma-4-e4b" in str(e.value) and "google/gemma-4-e2b" in str(e.value)

def test_server_irraggiungibile():
    with pytest.raises(ErroreServer, match="127.0.0.1:9"):
        leggi_modelli_disponibili("http://127.0.0.1:9/v1", timeout=1.0)

def test_crea_modello_usa_la_configurazione():
    m = crea_modello(carica_configurazione(VALIDO))
    assert (m.model_name, m.temperature, m.max_retries) == ("google/gemma-4-e4b", 0, 1)
    assert str(m.openai_api_base).rstrip("/") == "http://localhost:1234/v1"
```
  (`127.0.0.1:9` è una porta locale chiusa: il test non esce dal PC. `VALIDO` come nel Task 2,
  spostato in `tests/conftest.py`.)

- [ ] **Step 2:** pytest `tests/test_modello.py` → FAIL.
- [ ] **Step 3: Implementare** `modello.py` come da Interfaces.
- [ ] **Step 4:** pytest completo → PASS.
- [ ] **Step 5: Commit** `feat(modello): collega LM Studio e verifica il modello all'avvio`.

### Task 4: Nodo LLM, cronologia e gestione degli errori nella chat

**Files:**
- Modify: `assistente/grafo.py` (il nodo fisso viene sostituito), `assistente/cli.py`, `assistente/__main__.py`
- Modify: `tests/test_grafo.py`; Create: `tests/conftest.py` (modello finto, `VALIDO`), `tests/test_cli.py`,
  `tests/test_reale.py`

**Interfaces:**
- Consumes: Task 2 e 3.
- Produces in `grafo.py`: `PROMPT_DI_SISTEMA: str`; `LIMITE_PASSAGGI = 10`; `RispostaNonValida(Exception)`;
  `costruisci_grafo(modello, strumenti: list[BaseTool]) -> CompiledStateGraph` (chiama
  `modello.bind_tools(strumenti)` una volta, **solo se la lista non è vuota**: un elenco `tools` vuoto può
  essere rifiutato dall'API; in questo task `strumenti=[]` e il grafo è START → nodo_llm → END);
  `esegui_turno(grafo, cronologia: list[AnyMessage], testo: str) -> list[AnyMessage]` (invoca con
  `{"recursion_limit": LIMITE_PASSAGGI}` e restituisce la nuova cronologia; in caso di eccezione la
  cronologia passata non viene toccata).
  `nodo_llm` antepone `SystemMessage(PROMPT_DI_SISTEMA)` solo alla chiamata; logga
  `nodo_llm: chiamata al modello (%d messaggi)` (sistema incluso) e `nodo_llm: risposta ricevuta in %.1f s`;
  se la risposta ha `invalid_tool_calls`, oppure non ha `tool_calls` e ha contenuto vuoto o di soli spazi →
  log WARNING e `RispostaNonValida`.
- Produces in `cli.py`: `esegui_chat(grafo, server: str, leggi=input, scrivi=print) -> None`:
  ignora righe vuote o di soli spazi; normalizza i comandi (`strip().lower()`); `/esci` termina; ogni altra riga
  che inizia con `/` → `Comando sconosciuto. Comandi disponibili: /esci` senza chiamare il modello;
  `GraphRecursionError` → `Errore: limite di 10 passaggi raggiunto. Turno annullato.`;
  `RispostaNonValida` → `Errore: il modello non ha prodotto una risposta valida. Turno annullato.`;
  qualsiasi altra `Exception` del turno (connessione, timeout, modello assente, contesto esaurito: arrivano
  dal client di langchain-openai) → `Errore: nessuna risposta valida da LM Studio ({server}): {NomeClasse}: {dettaglio}. Turno annullato.`
  e traceback nel log a livello DEBUG;
  `EOFError`/`KeyboardInterrupt` (anche durante il turno) → `Alla prossima!` e ritorno.
- Produces in `__main__.py`: `main() -> int`: ambiente = `{**leggi_file_env(Path(".env")), **os.environ}`;
  `ErroreConfigurazione`/`ErroreServer` → messaggio su stderr e codice 1; poi `configura_log`,
  `leggi_modelli_disponibili` + `verifica_modello`, `crea_modello`, `costruisci_grafo`, `esegui_chat`.
- Prompt di sistema (testo fissato qui, gli strumenti arrivano nel Task 6):
  «Sei l'assistente del laboratorio e rispondi sempre in italiano. Per l'ora, la data o il giorno attuali
  chiama sempre lo strumento ora_corrente, anche se nella conversazione c'è già un risultato precedente:
  quel risultato è superato. Non dedurre informazioni temporali che il risultato non contiene. Per l'ora di
  un'altra città chiama ora_corrente, converti dall'ora locale e indica nella risposta anche l'ora locale
  da cui sei partito.»
- Modello finto (`conftest.py`): `ModelloFinto(risposte: list[AIMessage | BaseException])` con
  `bind_tools(strumenti) -> self` (registra gli strumenti), `invoke(messaggi) -> AIMessage` (registra i
  messaggi ricevuti in `self.chiamate`, restituisce o solleva la prossima voce).

- [ ] **Step 1: Scrivere i test che falliscono** (in `tests/test_grafo.py`, il test del grafo fisso viene
  sostituito):

```python
def test_turno_senza_strumenti_chiama_il_modello_una_volta():
    finto = ModelloFinto([AIMessage("Ciao!")])
    nuova = esegui_turno(costruisci_grafo(finto, []), [], "ciao")
    assert [m.type for m in nuova] == ["human", "ai"] and nuova[-1].content == "Ciao!"
    assert len(finto.chiamate) == 1
    assert finto.chiamate[0][0].type == "system" and finto.chiamate[0][0].content == PROMPT_DI_SISTEMA

def test_due_turni_conservano_la_cronologia_senza_duplicati():
    finto = ModelloFinto([AIMessage("R1"), AIMessage("R2")])
    grafo = costruisci_grafo(finto, [])
    cronologia = esegui_turno(grafo, esegui_turno(grafo, [], "D1"), "D2")
    assert [(m.type, m.content) for m in cronologia] == [
        ("human", "D1"), ("ai", "R1"), ("human", "D2"), ("ai", "R2")]
    assert [m.type for m in finto.chiamate[1]] == ["system", "human", "ai", "human"]

def test_errore_del_modello_lascia_la_cronologia_invariata():
    grafo = costruisci_grafo(ModelloFinto([AIMessage("R1"), RuntimeError("giù")]), [])
    cronologia = esegui_turno(grafo, [], "D1")
    copia = list(cronologia)
    with pytest.raises(RuntimeError):
        esegui_turno(grafo, cronologia, "D2")
    assert cronologia == copia

@pytest.mark.parametrize("risposta", [AIMessage(""), AIMessage("   "),
    AIMessage("", invalid_tool_calls=[{"name": "ora_corrente", "args": "{", "id": "x", "error": "json"}])])
def test_risposta_non_valida(risposta):
    with pytest.raises(RispostaNonValida):
        esegui_turno(costruisci_grafo(ModelloFinto([risposta]), []), [], "ciao")
```

  In `tests/test_cli.py` (con `leggi` da una lista di righe e `scrivi` che accumula l'output):
```python
def test_righe_vuote_e_spazi_ignorati():                              # Review Focus 1
    finto = ModelloFinto([])
    uscita = chat(costruisci_grafo(finto, []), ["", "   ", "\t", "/esci"])
    assert finto.chiamate == [] and uscita[-1] == "Alla prossima!"

def test_comandi_normalizzati_e_sconosciuti():
    finto = ModelloFinto([])
    uscita = chat(costruisci_grafo(finto, []), ["/aiuto", "  /ESCI  "])
    assert "Comando sconosciuto. Comandi disponibili: /esci" in uscita and finto.chiamate == []

def test_errore_di_connessione_turno_annullato_e_chat_prosegue():
    finto = ModelloFinto([ConnectionError("Connection refused"), AIMessage("Eccomi")])
    uscita = chat(costruisci_grafo(finto, []), ["D1", "D2", "/esci"])
    assert any(r.startswith("Errore: nessuna risposta valida da LM Studio (http://server/v1)") for r in uscita)
    assert "Assistente> Eccomi" in uscita
    assert [m.type for m in finto.chiamate[1]] == ["system", "human"]   # D1 non è rimasta in cronologia

def test_ctrl_c_durante_il_turno():                                    # Review Focus 2
    uscita = chat(costruisci_grafo(ModelloFinto([KeyboardInterrupt()]), []), ["D1"])
    assert uscita[-1] == "Alla prossima!"

def test_fine_input():
    assert chat(costruisci_grafo(ModelloFinto([]), []), [])[-1] == "Alla prossima!"
```
  (`chat(grafo, righe) -> list[str]` è un aiuto in `tests/conftest.py`: `leggi` restituisce le righe e poi
  solleva `EOFError`, `scrivi` accumula le stringhe stampate, `server="http://server/v1"`.)

- [ ] **Step 2:** pytest → FAIL.
- [ ] **Step 3: Implementare** `grafo.py`, `cli.py`, `__main__.py` come da Interfaces; eliminare
  `costruisci_grafo_fisso` e `RISPOSTA_FISSA`.
- [ ] **Step 4:** pytest completo → PASS.
- [ ] **Step 5: Test reali** in `tests/test_reale.py` (`pytestmark = pytest.mark.reale`; configurazione da
  `.env` + ambiente come in `main`):
  `test_reale_risposta_ordinaria` («Spiegami in una frase cos'è un grafo.» → ultimo messaggio `ai` non vuoto,
  nessun `ToolMessage`); `test_reale_cronologia` («Il mio colore preferito è il verde.» poi «Qual è il mio
  colore preferito?» → la seconda risposta contiene «verde»).
  Run (LM Studio attivo, `.env` creato): `.\.venv\Scripts\python.exe -m pytest -m reale -v` → 2 passed.
- [ ] **Step 6: Prove manuali eseguite da Claude**
  `"Il mio colore preferito è il verde.`nQual è il mio colore preferito?`n/esci" | .\.venv\Scripts\python.exe -m assistente`
  → due risposte, log `nodo_llm` visibili. Con `$env:LMSTUDIO_MODEL="inesistente"` → l'app non parte e
  elenca i modelli disponibili (codice di uscita 1); poi `Remove-Item Env:LMSTUDIO_MODEL`.
- [ ] **Step 7: README** — avvio locale, test reali, diagnosi «server non disponibile / modello assente» e
  «contesto esaurito» (aumentare la lunghezza di contesto in LM Studio; la sua politica di overflow può
  tagliare messaggi in silenzio).
- [ ] **Step 8: Commit** `feat(grafo): collega il nodo LLM e conserva la cronologia della sessione`.

### Task 5: Strumento orologio

**Files:**
- Create: `assistente/strumenti.py`
- Test: `tests/test_strumenti.py`

**Interfaces:**
- Produces: `strumenti.GIORNI = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")`;
  `strumenti.formatta_ora(istante: datetime, fuso: ZoneInfo) -> str` →
  `f"{GIORNI[d.weekday()]} {d.isoformat(timespec='seconds')} ({fuso.key})"` con `d = istante.astimezone(fuso)`;
  `strumenti.crea_strumento_orologio(fuso: ZoneInfo, adesso: Callable[[], datetime] = lambda: datetime.now(UTC)) -> BaseTool`
  (`StructuredTool.from_function`, nome `ora_corrente`, nessun parametro, descrizione della specifica).

- [ ] **Step 1: Scrivere i test che falliscono**

```python
ROMA = ZoneInfo("Europe/Rome")

def test_formato_con_giorno_e_offset():
    assert formatta_ora(datetime(2026, 10, 26, 15, 42, 10, tzinfo=UTC), ROMA) == \
        "lunedì 2026-10-26T16:42:10+01:00 (Europe/Rome)"

@pytest.mark.parametrize("utc, atteso", [
    (datetime(2026, 10, 24, 22, 0, tzinfo=UTC), "domenica 2026-10-25T00:00:00+02:00 (Europe/Rome)"),
    (datetime(2026, 10, 25, 2, 0, tzinfo=UTC), "domenica 2026-10-25T03:00:00+01:00 (Europe/Rome)")])
def test_cambio_ora_legale(utc, atteso):
    assert formatta_ora(utc, ROMA) == atteso

def test_altro_fuso():
    assert formatta_ora(datetime(2026, 10, 26, 15, 42, 10, tzinfo=UTC), ZoneInfo("America/New_York")) == \
        "lunedì 2026-10-26T11:42:10-04:00 (America/New_York)"

def test_strumento_usa_l_istante_fornito():
    s = crea_strumento_orologio(ROMA, adesso=lambda: datetime(2026, 10, 26, 15, 42, 10, tzinfo=UTC))
    assert s.name == "ora_corrente" and s.args == {}
    assert s.invoke({}) == "lunedì 2026-10-26T16:42:10+01:00 (Europe/Rome)"
```

- [ ] **Step 2:** pytest → FAIL. **Step 3:** implementare. **Step 4:** pytest completo → PASS.
- [ ] **Step 5: Prova diretta (slide 10)**:
  `.\.venv\Scripts\python.exe -c "from zoneinfo import ZoneInfo; from assistente.strumenti import crea_strumento_orologio as c; print(c(ZoneInfo('Europe/Rome')).invoke({}))"`
  → ora attuale di Roma, confrontata con l'orologio di Windows.
- [ ] **Step 6: Commit** `feat(strumenti): aggiunge lo strumento orologio con fuso esplicito`.

### Task 6: Instradamento, nodo strumenti e limite di passaggi

**Files:**
- Modify: `assistente/grafo.py`, `assistente/__main__.py` (passa `[crea_strumento_orologio(config.fuso)]`)
- Modify: `tests/test_grafo.py`, `tests/test_reale.py`

**Interfaces:**
- Consumes: `crea_strumento_orologio` (Task 5), `costruisci_grafo`/`esegui_turno` (Task 4).
- Produces: `grafo.instrada(stato: Stato) -> str` (`"nodo_strumenti"` o `END`; log
  `instradamento: richiesta strumento %s %s` con `json.dumps(args, ensure_ascii=False)` per ogni richiesta,
  oppure `instradamento: nessuno strumento -> fine`); `nodo_strumenti` esegue ogni `tool_call` e aggiunge
  `ToolMessage(content=risultato, tool_call_id=..., name=...)`; log `nodo_strumenti: %s -> %s`;
  argomenti non presenti in `strumento.args` → scartati con WARNING
  `nodo_strumenti: argomenti ignorati per %s: %s`; nome sconosciuto → `ToolMessage` con
  `Errore: strumento sconosciuto <nome>` e WARNING. Archi: START → nodo_llm →(instrada)→ nodo_strumenti | END;
  nodo_strumenti → nodo_llm.

- [ ] **Step 1: Scrivere i test che falliscono** (`chiamata(id, args={})` costruisce un `AIMessage("",
  tool_calls=[{"name": "ora_corrente", "args": args, "id": id}])`; `orologio` è lo strumento con l'istante
  fisso del Task 5):

```python
def test_percorso_con_strumento(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    finto = ModelloFinto([chiamata("c1"), AIMessage("Sono le 16:42.")])
    nuova = esegui_turno(costruisci_grafo(finto, [orologio]), [], "Che ore sono?")
    assert [m.type for m in nuova] == ["human", "ai", "tool", "ai"]
    assert nuova[2].tool_call_id == "c1"
    assert nuova[2].content == "lunedì 2026-10-26T16:42:10+01:00 (Europe/Rome)"
    assert [m.type for m in finto.chiamate[1]] == ["system", "human", "ai", "tool"]
    assert "instradamento: richiesta strumento ora_corrente {}" in caplog.messages
    assert "nodo_strumenti: ora_corrente -> lunedì 2026-10-26T16:42:10+01:00 (Europe/Rome)" in caplog.messages

def test_argomenti_inattesi_ignorati(caplog):
    finto = ModelloFinto([chiamata("c1", {"timezone": "Asia/Tokyo"}), AIMessage("ok")])
    nuova = esegui_turno(costruisci_grafo(finto, [orologio]), [], "Ora a Tokyo?")
    assert nuova[2].content.endswith("(Europe/Rome)")
    assert any("argomenti ignorati" in r.message and r.levelname == "WARNING" for r in caplog.records)

def test_piu_richieste_nella_stessa_risposta():
    doppia = AIMessage("", tool_calls=[{"name": "ora_corrente", "args": {}, "id": "a"},
                                       {"name": "ora_corrente", "args": {}, "id": "b"}])
    nuova = esegui_turno(costruisci_grafo(ModelloFinto([doppia, AIMessage("ok")]), [orologio]), [], "?")
    assert [m.tool_call_id for m in nuova if m.type == "tool"] == ["a", "b"]

def test_strumento_sconosciuto():
    sconosciuta = AIMessage("", tool_calls=[{"name": "meteo", "args": {}, "id": "m"}])
    nuova = esegui_turno(costruisci_grafo(ModelloFinto([sconosciuta, AIMessage("ok")]), [orologio]), [], "?")
    assert nuova[2].content == "Errore: strumento sconosciuto meteo"

def test_limite_di_passaggi():
    finto = ModelloFinto([chiamata(f"c{i}") for i in range(20)])
    with pytest.raises(GraphRecursionError):
        esegui_turno(costruisci_grafo(finto, [orologio]), [], "?")

def test_limite_di_passaggi_in_chat():
    finto = ModelloFinto([chiamata(f"c{i}") for i in range(20)] + [AIMessage("Eccomi")])
    uscita = chat(costruisci_grafo(finto, [orologio]), ["D1", "/esci"])
    assert "Errore: limite di 10 passaggi raggiunto. Turno annullato." in uscita

def test_risposta_con_testo_e_richiesta_va_agli_strumenti():
    mista = AIMessage("Controllo l'orologio.", tool_calls=[{"name": "ora_corrente", "args": {}, "id": "x"}])
    nuova = esegui_turno(costruisci_grafo(ModelloFinto([mista, AIMessage("ok")]), [orologio]), [], "?")
    assert nuova[2].type == "tool"
```

- [ ] **Step 2:** pytest → FAIL. **Step 3:** implementare. **Step 4:** pytest completo → PASS.
- [ ] **Step 5: Test reali** in `tests/test_reale.py`: `test_reale_due_domande_sull_ora` («Che ore sono?»
  poi «E adesso che ore sono?» → due `ToolMessage` di nome `ora_corrente`, uno per turno);
  `test_reale_domanda_ordinaria_senza_strumento` rimane quello del Task 4.
  Run: `.\.venv\Scripts\python.exe -m pytest -m reale -v` → 3 passed. Un fallimento si riporta all'utente.
- [ ] **Step 6: Prova manuale eseguita da Claude**:
  `"Che ore sono?`nChe giorno della settimana è oggi?`nChe ore sono a Tokyo?`n/esci" | .\.venv\Scripts\python.exe -m assistente`
  → nei log richiesta e risultato di `ora_corrente` a ogni domanda; giorno corretto; per Tokyo l'ora locale
  di partenza è riportata (conversione controllata a mano e riportata nel resoconto).
  Con `$env:LOG_LEVEL="WARNING"` la stessa prova mostra solo il dialogo.
- [ ] **Step 7: README** — come riconoscere nei log la chiamata allo strumento; modalità silenziosa.
- [ ] **Step 8: Commit** `feat(grafo): instrada le richieste allo strumento orologio con limite di passaggi`.

### Task 6A: Orologio con fuso facoltativo

Aggiunto il 28/10/2026 con la proposta approvata dall'utente: il modello sbagliava l'ora di New York
convertendo da sé (4:00 invece di 5:00). Ora passa il fuso IANA e l'ora la calcola il programma
(specifica: contratto di `ora_corrente`, requisiti del prompt, casi limite).

**Files:**
- Modify: `assistente/strumenti.py`, `assistente/grafo.py` (solo `PROMPT_DI_SISTEMA`)
- Modify: `tests/test_strumenti.py`, `tests/test_grafo.py`, `tests/test_reale.py`, `README.md`

**Interfaces:**
- Consumes: `formatta_ora`, `crea_strumento_orologio` (Task 5); `nodo_strumenti` (Task 6), che passa allo
  strumento solo gli argomenti presenti in `strumento.args` e non cambia: `fuso` diventa ammesso, argomenti
  diversi (es. `timezone`) restano scartati con WARNING.
- Produces in `strumenti.py` (firma di `crea_strumento_orologio` invariata):
  - `DESCRIZIONE = "Restituisce data, giorno della settimana e ora correnti: senza argomenti nel fuso orario configurato, con fuso nel fuso orario di un'altra località; da usare per ogni domanda su ora, data o giorno attuali"`;
  - `DESCRIZIONE_FUSO = "Nome IANA del fuso orario della località richiesta, per esempio America/New_York o Asia/Tokyo; omettere per il fuso orario configurato"`;
  - `ERRORE_FUSO = "Errore: fuso orario sconosciuto «{}»: serve un nome IANA, per esempio America/New_York"`;
  - `ERRORE_FUSO_NON_TESTO = "Errore: il fuso orario deve essere un nome IANA, per esempio America/New_York"`;
  - funzione interna `ora_corrente(fuso: Annotated[str | None, DESCRIZIONE_FUSO] = None) -> str`
    (`Annotated` da `typing`; nessun import di `pydantic`):
    `None`, vuoto o di soli spazi → `formatta_ora(adesso(), <fuso configurato>)`; altrimenti
    `ZoneInfo(fuso.strip())` e `formatta_ora` in quel fuso; se `ZoneInfo` solleva `ZoneInfoNotFoundError`,
    `ValueError` o `OSError` (le stesse eccezioni di `config.py`) restituisce `ERRORE_FUSO.format(fuso)`,
    senza sollevare;
  - `StructuredTool.from_function(func=ora_corrente, name="ora_corrente", description=DESCRIZIONE,
    handle_validation_error=ERRORE_FUSO_NON_TESTO)`: un `fuso` che non è un testo (es. `5`) restituisce
    quel messaggio invece di sollevare `ValidationError`.
- Produces in `grafo.py`: in `PROMPT_DI_SISTEMA` l'ultima frase («Per l'ora di un'altra città chiama
  ora_corrente, converti dall'ora locale e indica nella risposta anche l'ora locale da cui sei partito.»)
  diventa: `"Per l'ora di un'altra città chiama ora_corrente con il fuso IANA di quella città "
  "(per esempio America/New_York) e usa il risultato così com'è, senza convertire da te."`.
  Il resto del prompt non cambia.

- [ ] **Step 1: Scrivere i test che falliscono** in `tests/test_strumenti.py` (istante fisso
  `2026-10-28 08:56 UTC`: mercoledì, settimana in cui Roma è UTC+1 e New York UTC−4):

```python
ISTANTE = datetime(2026, 10, 28, 8, 56, tzinfo=UTC)
orologio = crea_strumento_orologio(ROMA, adesso=lambda: ISTANTE)


def test_strumento_usa_l_istante_fornito():        # aggiornato: prima controllava s.args == {}
    s = crea_strumento_orologio(ROMA, adesso=lambda: datetime(2026, 10, 26, 15, 42, 10, tzinfo=UTC))
    assert s.name == "ora_corrente" and set(s.args) == {"fuso"}
    assert s.invoke({}) == "lunedì 2026-10-26T16:42:10+01:00 (Europe/Rome)"


def test_parametro_fuso_facoltativo_e_descritto():
    assert "IANA" in orologio.args["fuso"]["description"]
    assert "fuso" not in orologio.tool_call_schema.model_json_schema().get("required", [])


@pytest.mark.parametrize("argomenti, atteso", [
    ({}, "mercoledì 2026-10-28T09:56:00+01:00 (Europe/Rome)"),
    ({"fuso": None}, "mercoledì 2026-10-28T09:56:00+01:00 (Europe/Rome)"),
    ({"fuso": ""}, "mercoledì 2026-10-28T09:56:00+01:00 (Europe/Rome)"),
    ({"fuso": "  "}, "mercoledì 2026-10-28T09:56:00+01:00 (Europe/Rome)"),
    ({"fuso": "America/New_York"}, "mercoledì 2026-10-28T04:56:00-04:00 (America/New_York)"),
    ({"fuso": "Asia/Tokyo"}, "mercoledì 2026-10-28T17:56:00+09:00 (Asia/Tokyo)"),
])
def test_ora_nel_fuso_richiesto(argomenti, atteso):
    assert orologio.invoke(argomenti) == atteso


@pytest.mark.parametrize("fuso", ["New York", "Europa/Roma", "../Europe/Rome"])
def test_fuso_non_valido_restituisce_un_errore(fuso):
    assert orologio.invoke({"fuso": fuso}) == \
        f"Errore: fuso orario sconosciuto «{fuso}»: serve un nome IANA, per esempio America/New_York"


def test_fuso_non_testuale_restituisce_un_errore():
    assert orologio.invoke({"fuso": 5}) == \
        "Errore: il fuso orario deve essere un nome IANA, per esempio America/New_York"
```

  e in `tests/test_grafo.py` (con l'`orologio` già definito lì, istante `2026-10-26 15:42:10 UTC`):

```python
def test_richiesta_con_fuso_arriva_allo_strumento(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    finto = ModelloFinto([chiamata("c1", {"fuso": "America/New_York"}), AIMessage("ok")])
    nuova = esegui_turno(costruisci_grafo(finto, [orologio]), [], "Che ore sono a New York?")
    assert nuova[2].content == "lunedì 2026-10-26T11:42:10-04:00 (America/New_York)"
    assert 'instradamento: richiesta strumento ora_corrente {"fuso": "America/New_York"}' in caplog.messages
    assert [r for r in caplog.records if r.levelname == "WARNING"] == []
```

- [ ] **Step 2:** pytest → FAIL. **Step 3:** implementare. **Step 4:** pytest completo → PASS
  (`test_argomenti_inattesi_ignorati` resta valido senza modifiche).
- [ ] **Step 5: Test reale** in `tests/test_reale.py`:

```python
def test_reale_ora_di_un_altra_citta(grafo):
    cronologia = esegui_turno(grafo, [], "Che ore sono a New York?")
    risultati = [m.content for m in cronologia if m.type == "tool" and m.name == "ora_corrente"]
    assert any(r.endswith("(America/New_York)") for r in risultati)
```

  Run: `.\.venv\Scripts\python.exe -m pytest -m reale -v` → 4 passed. Un fallimento si riporta all'utente.
- [ ] **Step 6: Prova manuale eseguita da Claude**:
  `"Che ore sono a New York?`nChe ore sono a Tokyo?`n/esci" | .\.venv\Scripts\python.exe -m assistente`
  → nei log `instradamento: richiesta strumento ora_corrente {"fuso": "America/New_York"}` e il risultato con
  `-04:00` (poi lo stesso per `Asia/Tokyo` con `+09:00`); l'ora di New York nella risposta coincide con
  `[TimeZoneInfo]::ConvertTimeBySystemTimeZoneId((Get-Date), 'Eastern Standard Time')`.
- [ ] **Step 7: README**, sezione «Strumento orologio»:
  - `ora_corrente` senza argomenti dà l'ora del fuso `APP_TIMEZONE`; con `fuso` (nome IANA) l'ora di un'altra
    località, calcolata dal programma; un fuso non valido produce un testo d'errore che il modello può correggere;
  - nei due comandi di prova la terza domanda diventa `Che ore sono a New York?`; i comandi si rieseguono
    alla lettera (modalità normale e silenziosa) e gli esempi di log e di dialogo si sostituiscono con l'output
    di queste esecuzioni, compresa la coppia di righe con `{"fuso": "America/New_York"}`;
  - si toglie il paragrafo sulla conversione fatta dal modello (l'aneddoto di Tokyo);
  - sezione «Test»: le prove reali diventano quattro, con l'ora di New York; la durata indicata è quella
    misurata in questo task.
- [ ] **Step 8: Commit** `feat(strumenti): aggiunge il fuso facoltativo all'orologio`.

### Task 6B: «Ragionando...» in modalità silenziosa

Aggiunto il 28/10/2026 con la proposta approvata dall'utente (specifica: decisioni, sezione Terminale, casi
limite e limite estetico accettato).

**Files:**
- Modify: `assistente/cli.py`, `assistente/__main__.py`
- Modify: `tests/conftest.py`, `tests/test_cli.py`, `README.md`

**Interfaces:**
- Consumes: `esegui_chat` (Task 4), `Configurazione.livello_log` (Task 2: già in maiuscolo, uno di
  `DEBUG`, `INFO`, `WARNING`, `ERROR`).
- Produces in `cli.py`:
  - `TESTO_ATTESA = "Ragionando..."`;
  - `class IndicatoreAttesa` con `__init__(self, uscita)` (uno stream di testo), `mostra()` che scrive
    `TESTO_ATTESA` senza andare a capo e chiama `uscita.flush()`, `nascondi()` che, **solo se la scritta è
    visibile**, scrive `"\b" * n + " " * n + "\b" * n` con `n = len(TESTO_ATTESA)` e chiama `flush()`;
  - `crea_indicatore_attesa(livello_log: str, ingresso, uscita) -> IndicatoreAttesa | None`: restituisce
    `IndicatoreAttesa(uscita)` solo se `livello_log` è `WARNING` o `ERROR` **e** `ingresso.isatty()` **e**
    `uscita.isatty()`; altrimenti `None`;
  - `esegui_chat(grafo, server: str, leggi=input, scrivi=print, attesa=None)`: con un indicatore, il turno
    diventa

```python
            try:
                if attesa is not None:
                    attesa.mostra()
                try:
                    cronologia = esegui_turno(grafo, cronologia, riga)
                finally:
                    if attesa is not None:
                        attesa.nascondi()
            except GraphRecursionError:
                ...                      # gestori esistenti invariati
```

    così la scritta sparisce prima della risposta, dell'errore o (dopo Ctrl+C) di «Alla prossima!»; righe
    vuote e comandi non la mostrano. Con `attesa=None` il comportamento è identico a prima.
- Produces in `__main__.py`: `esegui_chat(grafo, config.base_url,
  attesa=crea_indicatore_attesa(config.livello_log, sys.stdin, sys.stdout))`.
- Produces in `tests/conftest.py`: `AttesaFinta(stampato)`, che con `mostra()`/`nascondi()` aggiunge
  `"[mostra]"`/`"[nascondi]"` alla stessa lista delle righe stampate; `chat(grafo, righe, con_attesa=False)`
  passa `attesa=AttesaFinta(stampato)` solo con `con_attesa=True` (i test esistenti non cambiano).

- [ ] **Step 1: Scrivere i test che falliscono** in `tests/test_cli.py`:

```python
class TerminaleFinto(io.StringIO):
    """Stream di testo che si dichiara un terminale."""

    def isatty(self):
        return True


def test_attesa_mostrata_e_nascosta_prima_della_risposta():
    uscita = chat(costruisci_grafo(ModelloFinto([AIMessage("R1")]), []), ["D1", "/esci"], con_attesa=True)
    assert uscita == ["[mostra]", "[nascondi]", "Assistente> R1", "Alla prossima!"]


def test_attesa_nascosta_prima_dell_errore():
    finto = ModelloFinto([ConnectionError("Connection refused")])
    uscita = chat(costruisci_grafo(finto, []), ["D1"], con_attesa=True)
    assert uscita[:2] == ["[mostra]", "[nascondi]"] and uscita[2].startswith("Errore: ")


def test_attesa_nascosta_prima_del_saluto_dopo_ctrl_c():
    uscita = chat(costruisci_grafo(ModelloFinto([KeyboardInterrupt()]), []), ["D1"], con_attesa=True)
    assert uscita == ["[mostra]", "[nascondi]", "Alla prossima!"]


def test_righe_vuote_e_comandi_senza_attesa():
    uscita = chat(costruisci_grafo(ModelloFinto([]), []), ["", "   ", "/aiuto", "/esci"], con_attesa=True)
    assert uscita == ["Comando sconosciuto. Comandi disponibili: /esci", "Alla prossima!"]


def test_indicatore_scrive_e_cancella_esattamente():
    uscita = io.StringIO()
    indicatore = IndicatoreAttesa(uscita)
    indicatore.mostra()
    assert uscita.getvalue() == "Ragionando..."
    indicatore.nascondi()
    indicatore.nascondi()                     # già nascosta: non scrive altro
    assert uscita.getvalue() == "Ragionando..." + "\b" * 13 + " " * 13 + "\b" * 13


def test_indicatore_non_mostrato_non_cancella_nulla():
    uscita = io.StringIO()
    IndicatoreAttesa(uscita).nascondi()
    assert uscita.getvalue() == ""


@pytest.mark.parametrize("livello, ingresso, uscita, atteso", [
    ("INFO", TerminaleFinto(), TerminaleFinto(), False),
    ("DEBUG", TerminaleFinto(), TerminaleFinto(), False),
    ("WARNING", io.StringIO(), TerminaleFinto(), False),
    ("WARNING", TerminaleFinto(), io.StringIO(), False),
    ("WARNING", TerminaleFinto(), TerminaleFinto(), True),
    ("ERROR", TerminaleFinto(), TerminaleFinto(), True),
])
def test_scelta_dell_indicatore(livello, ingresso, uscita, atteso):
    assert isinstance(crea_indicatore_attesa(livello, ingresso, uscita), IndicatoreAttesa) is atteso
```

- [ ] **Step 2:** pytest → FAIL. **Step 3:** implementare. **Step 4:** pytest completo → PASS (i test
  esistenti di `test_cli.py` restano invariati).
- [ ] **Step 5: Prova manuale eseguita da Claude**, con l'input da pipe in modalità silenziosa:

```powershell
$env:LOG_LEVEL = "WARNING"
"Che ore sono?`n/esci" | .\.venv\Scripts\python.exe -m assistente
Remove-Item Env:LOG_LEVEL
```

  → solo `Tu> Assistente> ...` e `Tu> Alla prossima!`, nessun `Ragionando...`: output identico a prima del
  task. L'aspetto nella chat da tastiera (scritta che compare e sparisce, anche con Ctrl+C durante l'attesa)
  Claude non può vederlo: va indicato all'utente come prova manuale.
- [ ] **Step 6: README** — nelle due modalità di log: con `WARNING`, solo nella chat interattiva da tastiera,
  durante l'attesa compare `Ragionando...`, che sparisce all'arrivo della risposta; con l'input da pipe non
  compare.
- [ ] **Step 7: Commit** `feat(cli): mostra «Ragionando...» durante l'attesa in modalità silenziosa`.

### Task 6C: Comando `/log` in chat

Aggiunto il 28/10/2026 su richiesta dell'utente (specifica: decisioni, sezione Terminale, casi limite, test).
Sostituisce la scelta del 26/10 di cambiare modalità di log solo all'avvio.

**Files:**
- Modify: `assistente/config.py`, `assistente/cli.py`, `assistente/__main__.py`
- Modify: `tests/conftest.py`, `tests/test_config.py`, `tests/test_cli.py`, `README.md`

**Interfaces:**
- Consumes: `configura_log`, `LIVELLO_LOG_PREDEFINITO` (Task 2); `esegui_chat`, `IndicatoreAttesa`,
  `crea_indicatore_attesa` (Task 6B).
- Produces in `config.py`: `class ModalitaLog` con
  - `__init__(self, livello_iniziale: str)` (uno di `LIVELLI_LOG`, già in maiuscolo); imposta
    `visibili: bool` (`False` per `WARNING` ed `ERROR`, `True` per `DEBUG` e `INFO`) e **non** tocca i logger;
  - `alterna(self) -> bool`: inverte `visibili`, imposta il livello del solo logger `assistente` e restituisce
    il nuovo `visibili`. Livelli: con log visibili `livello_iniziale` se era `DEBUG`/`INFO`, altrimenti `INFO`;
    con log nascosti `livello_iniziale` se era `WARNING`/`ERROR`, altrimenti `WARNING`.
- Produces in `cli.py`:
  - `COMANDO_LOG = "/log"`;
  - `MESSAGGIO_LOG_VISIBILI = "Log visibili. Scrivi /log per nasconderli."`;
  - `MESSAGGIO_LOG_NASCOSTI = "Log nascosti: solo dialogo. Scrivi /log per mostrarli."`;
  - messaggio dei comandi sconosciuti: `Comando sconosciuto. Comandi disponibili: /esci, /log`;
  - `crea_indicatore_attesa(ingresso, uscita) -> IndicatoreAttesa | None`: **senza più il livello di log**,
    restituisce l'indicatore se `ingresso.isatty()` e `uscita.isatty()`, altrimenti `None`;
  - `esegui_chat(grafo, server: str, leggi=input, scrivi=print, attesa=None,
    livello_log: str = LIVELLO_LOG_PREDEFINITO)`: crea `ModalitaLog(livello_log)`. `/log`, normalizzato come
    `/esci`, chiama `alterna()` e stampa `MESSAGGIO_LOG_VISIBILI` o `MESSAGGIO_LOG_NASCOSTI`, senza turno né
    cronologia. A ogni turno la scritta di attesa si usa solo se `attesa is not None` **e** i log sono nascosti
    in quel momento; il resto del turno (gestori d'errore, `finally` di `nascondi`) resta invariato.
- Produces in `__main__.py`: `esegui_chat(grafo, config.base_url,
  attesa=crea_indicatore_attesa(sys.stdin, sys.stdout), livello_log=config.livello_log)`.
- Produces in `tests/conftest.py`:
  - `chat(grafo, righe, con_attesa=False, livello_log="INFO")`, che passa `livello_log` a `esegui_chat`;
  - una fixture `autouse` che salva il livello del logger `assistente` prima di ogni test e lo rimette dopo,
    perché `/log` lo cambia davvero.

- [ ] **Step 1: Scrivere i test che falliscono**

  In `tests/test_config.py`:

```python
@pytest.mark.parametrize("iniziale, visibili, dopo_uno, dopo_due", [
    ("DEBUG", True, "WARNING", "DEBUG"),
    ("INFO", True, "WARNING", "INFO"),
    ("WARNING", False, "INFO", "WARNING"),
    ("ERROR", False, "INFO", "ERROR"),
])
def test_modalita_log_alterna_e_torna_al_livello_d_avvio(log_isolati, iniziale, visibili, dopo_uno, dopo_due):
    configura_log(iniziale)
    modalita = ModalitaLog(iniziale)
    assert modalita.visibili is visibili
    assert modalita.alterna() is (not visibili)
    assert logging.getLevelName(logging.getLogger("assistente").level) == dopo_uno
    assert modalita.alterna() is visibili
    assert logging.getLevelName(logging.getLogger("assistente").level) == dopo_due


def test_modalita_log_non_tocca_i_logger_alla_creazione(log_isolati):
    configura_log("DEBUG")
    ModalitaLog("INFO")
    assert logging.getLogger("assistente").level == logging.DEBUG


def test_modalita_log_tocca_solo_i_log_dell_applicazione(log_isolati):
    configura_log("WARNING")
    ModalitaLog("WARNING").alterna()
    assert logging.getLogger("assistente.grafo").isEnabledFor(logging.INFO)
    assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)
```

  In `tests/test_cli.py`:
  - nei test esistenti il messaggio dei comandi sconosciuti diventa
    `"Comando sconosciuto. Comandi disponibili: /esci, /log"`;
  - i quattro test con `con_attesa=True` del Task 6B passano anche `livello_log="WARNING"`;
  - `test_scelta_dell_indicatore` perde il livello:

```python
@pytest.mark.parametrize("ingresso, uscita, atteso", [
    (io.StringIO(), TerminaleFinto(), False),
    (TerminaleFinto(), io.StringIO(), False),
    (TerminaleFinto(), TerminaleFinto(), True),
])
def test_scelta_dell_indicatore(ingresso, uscita, atteso):
    assert isinstance(crea_indicatore_attesa(ingresso, uscita), IndicatoreAttesa) is atteso
```

  - nuovi test:

```python
NASCOSTI = "Log nascosti: solo dialogo. Scrivi /log per mostrarli."
VISIBILI = "Log visibili. Scrivi /log per nasconderli."


def test_log_alterna_con_messaggi_e_senza_chiamare_il_modello():
    finto = ModelloFinto([])
    uscita = chat(costruisci_grafo(finto, []), ["/log", "  /LOG  ", "/log on", "/esci"])
    assert uscita == [NASCOSTI, VISIBILI, "Comando sconosciuto. Comandi disponibili: /esci, /log",
                      "Alla prossima!"]
    assert finto.chiamate == []


def test_log_partendo_dalla_modalita_silenziosa():
    uscita = chat(costruisci_grafo(ModelloFinto([]), []), ["/log"], livello_log="WARNING")
    assert uscita == [VISIBILI, "Alla prossima!"]


def test_log_nasconde_e_rimostra_i_passaggi_nella_stessa_chat(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    finto = ModelloFinto([AIMessage("R1"), AIMessage("R2"), AIMessage("R3")])
    chat(costruisci_grafo(finto, []), ["D1", "/log", "D2", "/log", "D3"])
    chiamate = [r.getMessage() for r in caplog.records if r.getMessage().startswith("nodo_llm: chiamata")]
    # D2 non lascia log; D3 riceve 6 messaggi: il comando /log non è entrato nella cronologia
    assert chiamate == ["nodo_llm: chiamata al modello (2 messaggi)",
                        "nodo_llm: chiamata al modello (6 messaggi)"]


def test_attesa_compare_dopo_log_che_nasconde():
    finto = ModelloFinto([AIMessage("R1"), AIMessage("R2")])
    uscita = chat(costruisci_grafo(finto, []), ["D1", "/log", "D2"], con_attesa=True)
    assert uscita == ["Assistente> R1", NASCOSTI, "[mostra]", "[nascondi]", "Assistente> R2",
                      "Alla prossima!"]


def test_attesa_sparisce_dopo_log_che_mostra():
    finto = ModelloFinto([AIMessage("R1"), AIMessage("R2")])
    uscita = chat(costruisci_grafo(finto, []), ["D1", "/log", "D2"], con_attesa=True, livello_log="WARNING")
    assert uscita == ["[mostra]", "[nascondi]", "Assistente> R1", VISIBILI, "Assistente> R2",
                      "Alla prossima!"]
```

- [ ] **Step 2:** pytest → FAIL (import di `ModalitaLog`). **Step 3:** implementare. **Step 4:** pytest completo
  → PASS, nessun test `reale` eseguito.
- [ ] **Step 5: Prova eseguita da Claude con il modello vero**, input da pipe e livello predefinito:

```powershell
"Che ore sono?`n/log`nChe ore sono a New York?`n/log`nChe giorno è oggi?`n/esci" | .\.venv\Scripts\python.exe -m assistente
```

  → primo turno con le righe `[INFO]` (richiesta `ora_corrente`); poi `Tu> Log nascosti: solo dialogo. Scrivi
  /log per mostrarli.`; secondo turno senza righe `[INFO]`, solo `Tu> Assistente> ...`; poi `Tu> Log visibili.
  Scrivi /log per nasconderli.`; terzo turno di nuovo con le righe `[INFO]`; da nessuna parte `Ragionando...`.
  L'aspetto nella chat da tastiera Claude non può vederlo: va dato all'utente come prova manuale (domanda con
  log visibili senza scritta; `/log`; domanda con «Ragionando...» che compare e sparisce; Ctrl+C durante
  l'attesa; `/aiuto` che elenca `/esci, /log`).
- [ ] **Step 6: README**:
  - modalità di log: `LOG_LEVEL` sceglie quella iniziale, `/log` passa dall'una all'altra per la sessione
    senza modificare `.env`; «Ragionando...» compare con i log nascosti, solo da tastiera;
  - comandi della chat: `/log` e il nuovo messaggio dei comandi sconosciuti;
  - l'esempio da pipe dello Step 5, con l'output osservato abbreviato come negli altri esempi.
- [ ] **Step 7: Commit** `feat(cli): aggiunge il comando /log per mostrare o nascondere i log`.

### Task 7: Docker Compose

**Files:**
- Create: `Dockerfile`, `compose.yaml`, `.dockerignore`

**Interfaces:**
- Consumes: `python -m assistente` (Task 4) e `.env` (Task 2).
- `Dockerfile`: `FROM python:3.14.7-slim`, `ENV PYTHONUNBUFFERED=1`, `WORKDIR /app`, copia e installa
  `requirements.txt` prima del codice (cache dei layer), copia `assistente/`, `CMD ["python", "-m", "assistente"]`.
- `compose.yaml`: servizio `assistente` con `build: .`, `env_file: .env`,
  `environment: LMSTUDIO_BASE_URL: http://host.docker.internal:1234/v1`, `stdin_open: true`, `tty: true`,
  `extra_hosts: ["host.docker.internal:host-gateway"]`, nessuna porta.
- `.dockerignore`: `.env`, `.venv`, `__pycache__`, `.pytest_cache`, `.git`, `tests`, `docs`.

- [ ] **Step 1:** avviare Docker Desktop (`Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"`)
  e attendere che `docker info` risponda.
- [ ] **Step 2:** scrivere i tre file. Run: `docker compose build` → immagine costruita;
  `docker compose run --rm assistente python -c "import assistente, langgraph; print('ok')"` → `ok`.
- [ ] **Step 3: Prova automatizzabile (Claude)**:
  `"Che ore sono?`n/esci" | docker compose run --rm -T assistente` → log `ora_corrente` e risposta.
  Se il container non raggiunge LM Studio: controllare «Serve on Local Network» in LM Studio e il firewall,
  annotare l'esito per il README.
- [ ] **Step 4: Confronto orologi**: `Get-Date` sull'host e `docker run --rm python:3.14.7-slim date`
  → stessa ora (in UTC).
- [ ] **Step 5: Consegna all'utente — demo interattiva**: l'utente esegue
  `docker compose run --rm --name assistente-demo assistente` (due turni, due domande sull'ora, una su un'altra
  città) e da un secondo terminale `docker logs -f assistente-demo`, e riporta l'esito. Nella stessa demo prova
  anche `/log` e la scritta «Ragionando...» con i log nascosti (Task 6B e 6C), senza variabili in più.
  Il commit aspetta l'esito.
- [ ] **Step 6: README** — avvio con Compose, `run` invece di `up`, diagnosi (slide 17, indirizzo di ascolto,
  firewall, orologio della VM).
- [ ] **Step 7: Commit** `feat(docker): avvia l'assistente con Docker Compose verso LM Studio sull'host`.

### Task 8: Verifica completa e documentazione finale

**Files:**
- Modify: `README.md`, `CLAUDE.md`

- [ ] **Step 1:** `.\.venv\Scripts\python.exe -m pytest -v` → tutti verdi, nessun test `reale` eseguito.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest -m reale -v` → 4 passed (LM Studio attivo).
- [ ] **Step 3:** confronto requisito per requisito con la specifica (obiettivi 1–5, tabella dei casi limite);
  ogni scostamento va all'utente.
- [ ] **Step 4:** README rivisto: ogni comando presente è stato eseguito in questo piano; aggiunta la checklist
  della prova Docker manuale.
- [ ] **Step 5:** CLAUDE.md: struttura del progetto, Python 3.14.7, comandi di test e test reali (solo
  convenzioni stabili).
- [ ] **Step 6:** `git status` e `git log --oneline` mostrati all'utente; resoconto: eseguito, esito, cosa resta.
- [ ] **Step 7: Commit** `docs: completa README e CLAUDE.md con comandi verificati`. Nessun push.
