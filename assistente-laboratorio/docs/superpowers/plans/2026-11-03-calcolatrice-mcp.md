# Calcolatrice sicura via MCP — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** aggiungere all'assistente una calcolatrice sicura servita da un server MCP locale (stdio), scoperta
all'avvio e usata dal grafo esistente, con errori restituiti al modello come `ToolMessage` d'errore.

**Architecture:** pacchetto server `calcolatrice_mcp/` (logica pura con `ast` + server FastMCP dell'SDK `mcp`),
indipendente dall'agente. Nell'agente un solo modulo nuovo, `assistente/client_mcp.py`, che fa la discovery con
`langchain-mcp-adapters` e trasforma gli strumenti asincroni in strumenti sincroni; il grafo cambia solo in
`nodo_strumenti` (gestione di `ToolException`) e nel prompt.

**Tech Stack:** Python 3.14.7, `mcp==1.30.0` (`mcp.server.fastmcp.FastMCP`, `mcp.client.stdio`),
`langchain-mcp-adapters==0.3.2`, LangGraph, `langchain_core`, pytest, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-11-03-calcolatrice-mcp-design.md` (e, per tutto ciò che non cambia,
`docs/superpowers/specs/2026-10-26-assistente-laboratorio-design.md`).

## Global Constraints

- Percorsi relativi a `assistente-laboratorio/`; comandi da lì, in PowerShell 5.1 (niente `&&`), sempre con
  `.\.venv\Scripts\python.exe`, mai il `python` di sistema né `Activate.ps1`.
- Branch `feature/calcolatrice`; nessun worktree, nessun merge, nessun push.
- `requirements.txt`: si aggiungono **solo** `langchain-mcp-adapters==0.3.2` e `mcp==1.30.0`; le transitive non si
  fissano; `requirements-dev.txt` non cambia. Nessun'altra libreria.
- Nel pacchetto `assistente/` non si importano direttamente `openai`, `httpx` né `pydantic` (eccezione: i tipi di
  `langchain_core`). `asyncio` e `langchain_mcp_adapters` si importano **solo** in `assistente/client_mcp.py`.
- `calcolatrice_mcp/` non importa nulla da `assistente/`; `assistente/` non importa nulla da `calcolatrice_mcp/`.
- Mai `eval`, `exec` o `compile` sull'espressione.
- Server: log solo su stderr, `FastMCP(..., log_level="WARNING")`, nessun `print`.
- Limiti: al massimo 200 caratteri (dopo `strip`); esponente con valore assoluto ≤ 100, controllato prima della
  potenza; costanti, intermedi e risultato con valore assoluto ≤ 10**100; float non finiti rifiutati. Formato:
  interi esatti, decimali `format(valore, ".15g")`, `-0` → `0`.
- Log `[%(levelname)s] %(message)s` su stderr; ogni riga dell'agente comincia con il nome del modulo o del nodo
  (`client_mcp: `, `nodo_strumenti: `). Messaggi, log e testi in italiano.
- Invariati: `LIMITE_PASSAGGI = 10`, timeout del modello 180 s e controllo all'avvio 5 s (nessun timeout nuovo per
  MCP), orologio, CLI, `/log`, `compose.yaml`, `.dockerignore`, `.env.example`; nessuna variabile d'ambiente nuova.
- Test senza modello nella suite di default; prove con LM Studio solo con il marcatore `reale`, una sola
  esecuzione sul modello alla volta; un fallimento reale si riporta, non si simula.
- Prove da pipe senza `PYTHONIOENCODING`, in un figlio pulito:
  `Remove-Item Env:PYTHONIOENCODING; powershell.exe -NoProfile -File <script>.ps1` (script in UTF-8 con BOM).
- Git: prima di ogni commit `git status` e `git diff --cached`, staging per percorso dei soli file del task;
  Conventional Commits in italiano con la riga `Co-Authored-By: Claude <modello> <noreply@anthropic.com>` del
  modello che scrive il commit. Mai in staging: `.env`, `.superpowers/`, file della radice di `Esercizi/`, PDF,
  `SlideLezioni/`, documenti di studio privati.

## Review Focus

1. Ctrl+C mentre `calcola` è in esecuzione → `KeyboardInterrupt` risale intatto (la CLI saluta ed esce), non
   diventa un `ErroreTrasportoMCP` né un `ToolMessage` (test nel Task 3).
2. `ToolException` del server arrivata dentro un `ExceptionGroup` (task group di `anyio`) → resta un errore di
   validazione con il messaggio italiano, non un errore di trasporto (test nel Task 3).
3. App avviata da un'altra cartella → il server si trova lo stesso grazie a `cwd` (test nel Task 3).
4. Numeri scritti all'italiana (`2,5`, `1.000,50`) → errore con il suggerimento del punto, mai un numero (test nel
   Task 1).
5. Annidamento profondo entro i 200 caratteri (`(((…1…)))`, `----…1`) → risultato corretto, nessun
   `RecursionError` (test nel Task 1).

---

### Task 1: Logica pura della calcolatrice

**Files:**
- Create: `calcolatrice_mcp/__init__.py` (solo una docstring), `calcolatrice_mcp/calcolo.py`
- Test: `tests/test_calcolo.py`

**Interfaces:**
- Produces: `calcolo.ErroreCalcolo(ValueError)`; `calcolo.calcola(espressione: str) -> str`; costanti
  `LUNGHEZZA_MASSIMA = 200`, `ESPONENTE_MASSIMO = 100`, `VALORE_MASSIMO = 10**100`. Messaggi esatti di
  `ErroreCalcolo` (usati anche dai task successivi):
  - `espressione vuota`
  - `espressione troppo lunga (massimo 200 caratteri)`
  - `sintassi non valida`
  - `elemento non ammesso: sono permessi solo numeri, + - * / // % ** e parentesi`
  - `la virgola non è ammessa: per i decimali usa il punto, per esempio 2.5`
  - `il simbolo ^ non è ammesso: per le potenze usa **, per esempio 2**3`
  - `divisione per zero`
  - `esponente troppo grande (massimo 100 in valore assoluto)`
  - `numero troppo grande (massimo 10**100 in valore assoluto)`
  - `il risultato non è un numero reale`

- [ ] **Step 1: Scrivere i test che falliscono** in `tests/test_calcolo.py`

```python
SINTASSI = "sintassi non valida"
NON_AMMESSO = "elemento non ammesso: sono permessi solo numeri, + - * / // % ** e parentesi"
VIRGOLA = "la virgola non è ammessa: per i decimali usa il punto, per esempio 2.5"
POTENZA = "il simbolo ^ non è ammesso: per le potenze usa **, per esempio 2**3"
ZERO = "divisione per zero"
ESPONENTE = "esponente troppo grande (massimo 100 in valore assoluto)"
GRANDE = "numero troppo grande (massimo 10**100 in valore assoluto)"

@pytest.mark.parametrize("espressione, atteso", [
    ("2+3*4", "14"), ("(2+3)*4", "20"), ("-2**2", "-4"), ("2**-1", "0.5"), ("--3", "3"),
    ("0.1+0.2", "0.3"), ("1/3", "0.333333333333333"), ("7/2", "3.5"), ("4/2", "2"), ("1e3", "1000"),
    ("-7//2", "-4"), ("-7%3", "2"), ("7.5%2", "1.5"), ("2**10", "1024"), ("12.5*8-3", "97"),
    ("-0.0", "0"), ("10**100", "1" + "0" * 100), ("  2+2\n", "4"),
    ("(" * 99 + "1" + ")" * 99, "1"), ("-" * 199 + "1", "-1"),
])
def test_calcoli_validi(espressione, atteso):
    assert calcola(espressione) == atteso

@pytest.mark.parametrize("espressione, messaggio", [
    ("", "espressione vuota"), ("   ", "espressione vuota"),
    ("1" * 201, "espressione troppo lunga (massimo 200 caratteri)"),
    ("2+", SINTASSI), ("(2", SINTASSI), ("2 3", SINTASSI), ("2×3", SINTASSI),
    ("__import__('os')", NON_AMMESSO), ("().__class__", NON_AMMESSO), ("x", NON_AMMESSO),
    ("abs(-1)", NON_AMMESSO), ("[1, 2]", NON_AMMESSO), ("'a'*3", NON_AMMESSO), ("1<2", NON_AMMESSO),
    ("True+1", NON_AMMESSO), ("2j", NON_AMMESSO),
    ("2,5", VIRGOLA), ("1.000,50", VIRGOLA), ("2^3", POTENZA),
    ("1/0", ZERO), ("1//0", ZERO), ("1%0", ZERO), ("0**-1", ZERO),
    ("9**9**9", ESPONENTE), ("2**101", ESPONENTE),
    ("10**100*10", GRANDE), ("1e308*10", GRANDE), ("1" + "0" * 101, GRANDE),
    ("(-8)**0.5", "il risultato non è un numero reale"),
])
def test_errori(espressione, messaggio):
    with pytest.raises(ErroreCalcolo) as errore:
        calcola(espressione)
    assert str(errore.value) == messaggio

def test_il_modulo_non_esegue_codice():
    sorgente = Path(calcolo.__file__).read_text(encoding="utf-8")
    assert not re.search(r"\b(eval|exec|compile)\s*\(", sorgente)
```

- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_calcolo.py -v` → FAIL (import).
- [ ] **Step 3: Implementare `calcola` in `calcolatrice_mcp/calcolo.py`**
  - `strip`, poi i controlli di vuoto e di lunghezza;
  - `ast.parse(testo, mode="eval")`, con `SyntaxError` e `ValueError` → sintassi non valida;
  - visita ricorsiva del corpo, con le regole della specifica:
    - `Constant` ammessa solo se `type(valore) in (int, float)`;
    - `Tuple` → virgola;
    - `BinOp` con `BitXor` → `^`;
    - ogni altro nodo o operatore → elemento non ammesso;
    - operazioni con il modulo `operator`;
  - `Pow`: controllo dell'esponente prima di calcolare;
  - `ZeroDivisionError` → divisione per zero; `OverflowError` → numero troppo grande; un risultato `complex` → non
    reale;
  - controllo di finitezza e di `VALORE_MASSIMO` su ogni costante e su ogni risultato intermedio;
  - formattazione finale come nei Global Constraints.
- [ ] **Step 4:** stesso comando → PASS (50 test). Poi `.\.venv\Scripts\python.exe -m pytest` → tutti verdi.
- [ ] **Step 5: Commit** `feat(calcolatrice): aggiunge la logica della calcolatrice sicura con ast`.

### Task 2: Server FastMCP e dipendenze MCP

**Files:**
- Modify: `requirements.txt`
- Create: `calcolatrice_mcp/server.py`, `calcolatrice_mcp/__main__.py`
- Test: `tests/test_server_mcp.py`

**Interfaces:**
- Consumes: `calcolo.calcola`, `calcolo.ErroreCalcolo` (Task 1).
- Produces:
  - `python -m calcolatrice_mcp` serve su stdio un solo strumento, `calcola(espressione: str) -> str`;
  - `server.server = FastMCP("calcolatrice", log_level="WARNING")`;
  - `server.main() -> None` esegue `server.run(transport="stdio")`;
  - la docstring di `calcola` è la descrizione vista dal modello, testo esatto: `Calcola un'espressione aritmetica
    e restituisce il risultato esatto; da usare per ogni calcolo. Ammessi numeri (punto per i decimali),
    + - * / // % ** e parentesi; % è il resto della divisione, non la percentuale; ** è la potenza. Esempi:
    2*(3+4), 12.5*8-3.`;
  - `ErroreCalcolo` non si intercetta: FastMCP lo trasforma in un risultato `isError=True` con il testo
    `Error executing tool calcola: <messaggio>`.

- [ ] **Step 1: Dipendenze.** Aggiungere a `requirements.txt` le righe `langchain-mcp-adapters==0.3.2` e
  `mcp==1.30.0`. Poi:
  - `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`;
  - `.\.venv\Scripts\python.exe -m pip check` → `No broken requirements found.`;
  - `.\.venv\Scripts\python.exe -m pip freeze` deve mostrare le due versioni e lasciare invariate
    `langgraph==1.2.17` e `langchain-openai==1.7.2`;
  - `.\.venv\Scripts\python.exe -m pytest` → 161 passed (i 111 di prima più i 50 del Task 1).

  Se la risoluzione cambia una versione esistente: fermarsi e riportarlo.
- [ ] **Step 2: Scrivere i test che falliscono** in `tests/test_server_mcp.py` (codice di test: qui `asyncio` è
  ammesso)

```python
RADICE = Path(__file__).resolve().parent.parent

def col_server(operazione):
    """Avvia `python -m calcolatrice_mcp`, apre una sessione e restituisce `await operazione(sessione)`."""
    async def esegui():
        parametri = StdioServerParameters(command=sys.executable, args=["-m", "calcolatrice_mcp"], cwd=RADICE)
        async with stdio_client(parametri) as (lettura, scrittura):
            async with ClientSession(lettura, scrittura) as sessione:
                await sessione.initialize()
                return await operazione(sessione)
    return asyncio.run(esegui())

def test_catalogo_contiene_solo_calcola():
    strumenti = col_server(lambda s: s.list_tools()).tools
    assert [s.name for s in strumenti] == ["calcola"]
    assert "resto della divisione" in strumenti[0].description
    schema = strumenti[0].inputSchema
    assert schema["properties"]["espressione"]["type"] == "string" and schema["required"] == ["espressione"]

def test_invocazione_diretta():
    risultato = col_server(lambda s: s.call_tool("calcola", {"espressione": "2+3*4"}))
    assert not risultato.isError and risultato.content[0].text == "14"

def test_errore_controllato_senza_numero():
    risultato = col_server(lambda s: s.call_tool("calcola", {"espressione": "1/0"}))
    assert risultato.isError and risultato.content[0].text.endswith("divisione per zero")

def test_numero_invece_di_testo_e_un_errore():
    risultato = col_server(lambda s: s.call_tool("calcola", {"espressione": 5}))
    assert risultato.isError
```

- [ ] **Step 3:** `.\.venv\Scripts\python.exe -m pytest tests/test_server_mcp.py -v` → FAIL (`No module named
  calcolatrice_mcp.__main__` o equivalente).
- [ ] **Step 4: Implementare** `server.py` (istanza, strumento con la docstring esatta, `main`) e `__main__.py`
  (chiama `main()`).
- [ ] **Step 5:** stesso comando → PASS (4 test). Se `test_numero_invece_di_testo_e_un_errore` fallisce perché
  FastMCP converte il numero in testo, non cambiare il test: riportarlo. Poi la suite completa → tutti verdi.
- [ ] **Step 6: Commit** `feat(mcp): aggiunge il server FastMCP della calcolatrice e le dipendenze MCP`
  (`requirements.txt`, `calcolatrice_mcp/server.py`, `calcolatrice_mcp/__main__.py`, `tests/test_server_mcp.py`).

### Task 3: Client MCP con discovery e strumenti sincroni

**Files:**
- Create: `assistente/client_mcp.py`
- Test: `tests/test_client_mcp.py`

**Interfaces:**
- Consumes: il server del Task 2 (`python -m calcolatrice_mcp`).
- Produces:
  - `client_mcp.ErroreMCP(Exception)`, errore all'avvio;
  - `client_mcp.ErroreTrasportoMCP(ToolException)`, errore di trasporto durante una chiamata;
  - costanti `NOME_SERVER = "calcolatrice"`, `STRUMENTO_RICHIESTO = "calcola"`,
    `ARGOMENTI_SERVER = ("-m", "calcolatrice_mcp")`, `CARTELLA_PROGETTO = Path(__file__).resolve().parent.parent`;
  - `client_mcp.carica_strumenti_mcp(argomenti: Sequence[str] = ARGOMENTI_SERVER) -> list[BaseTool]`:
    - connessione `{"transport": "stdio", "command": sys.executable, "args": list(argomenti),
      "cwd": str(CARTELLA_PROGETTO)}`;
    - `MultiServerMCPClient({NOME_SERVER: connessione}, handle_tool_errors=False)`, poi
      `asyncio.run(client.get_tools())`;
    - restituisce `[rendi_sincrono(s) for s in strumenti]`;
    - log INFO `client_mcp: catalogo di calcolatrice letto in {s:.1f} s: {elenco}`, dove `elenco` è
      `"; ".join(f"{nome} ({descrizione})")`;
    - `ErroreMCP` con questi testi:
      - `server MCP calcolatrice non avviato ({comando}): {dettaglio}`, con
        `comando = " ".join([Path(sys.executable).name, *argomenti])`;
      - `il server MCP calcolatrice non espone strumenti`;
      - `il server MCP calcolatrice non espone lo strumento calcola`;
  - `client_mcp.rendi_sincrono(strumento_mcp: BaseTool) -> BaseTool`:
    - `StructuredTool` con lo stesso `name`, la stessa `description` e `args_schema=strumento_mcp.args_schema`
      (lo schema JSON);
    - la sua `func(**argomenti) -> str` esegue `asyncio.run(strumento_mcp.ainvoke(argomenti))`, converte in testo
      il contenuto (una stringa, oppure i blocchi `{"type": "text", "text": …}` uniti) e registra a INFO
      `client_mcp: {nome} eseguito in {s:.1f} s`;
  - regola degli errori in `func`: si intercetta solo `Exception`, mai `BaseException`. Si prende la prima foglia
    (dentro un `BaseExceptionGroup` si scende alla prima eccezione, ricorsivamente):
    - foglia `ToolException` → `ToolException` con il testo della foglia, tolto il prefisso
      `^Error executing tool \S+: `;
    - qualunque altra foglia → log WARNING `client_mcp: server MCP calcolatrice non raggiungibile: {dettaglio}` e
      `ErroreTrasportoMCP("server MCP calcolatrice non raggiungibile: {dettaglio}")`.

    `dettaglio` = `str(foglia)`, oppure il nome del tipo se il testo è vuoto. La stessa regola della foglia vale
    per il `dettaglio` di `ErroreMCP`.

- [ ] **Step 1: Scrivere il primo test e farlo girare da solo** (verifica del rischio sullo stderr del figlio
  sotto pytest su Windows):

```python
def test_discovery_restituisce_strumenti_sincroni(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    strumenti = carica_strumenti_mcp()
    assert [s.name for s in strumenti] == ["calcola"]
    assert "resto della divisione" in strumenti[0].description and "espressione" in strumenti[0].args
    riga = next(m for m in caplog.messages if m.startswith("client_mcp: catalogo di calcolatrice letto in "))
    assert "calcola (" in riga
```

  `.\.venv\Scripts\python.exe -m pytest tests/test_client_mcp.py -v` → FAIL (import). Dopo un'implementazione
  minima di `carica_strumenti_mcp`: PASS. Se fallisce per lo stderr del figlio (`fileno`, flusso non valido):
  fermarsi e riportarlo al controller.
- [ ] **Step 2: Scrivere gli altri test** (stesso file)

```python
SCHEMA = {"type": "object", "properties": {"espressione": {"type": "string"}}, "required": ["espressione"]}

@pytest.fixture(scope="module")
def calcola():
    return carica_strumenti_mcp()[0]

def strumento_che_solleva(errore):
    async def solleva(**argomenti):
        raise errore
    return StructuredTool(name="calcola", description="prova", args_schema=SCHEMA, coroutine=solleva)

def test_invocazione_sincrona(calcola, caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    assert calcola.invoke({"espressione": "2+2"}) == "4"
    assert any(m.startswith("client_mcp: calcola eseguito in ") for m in caplog.messages)

def test_errore_di_validazione_senza_prefisso_inglese(calcola):
    with pytest.raises(ToolException) as errore:
        calcola.invoke({"espressione": "1/0"})
    assert str(errore.value) == "divisione per zero" and not isinstance(errore.value, ErroreTrasportoMCP)

def test_argomento_mancante_e_un_errore_di_validazione(calcola):
    with pytest.raises(ToolException) as errore:
        calcola.invoke({})
    assert not isinstance(errore.value, ErroreTrasportoMCP)

@pytest.mark.parametrize("argomenti, inizio", [
    (["-m", "modulo_che_non_esiste"], "server MCP calcolatrice non avviato (python"),
    (["-c", "from mcp.server.fastmcp import FastMCP; FastMCP('vuoto').run()"],
     "il server MCP calcolatrice non espone strumenti"),
    (["-c", "from mcp.server.fastmcp import FastMCP; s = FastMCP('altro'); "
            "s.add_tool(lambda: 'ok', name='altro', description='altro'); s.run()"],
     "il server MCP calcolatrice non espone lo strumento calcola"),
])
def test_discovery_fallita(argomenti, inizio):
    with pytest.raises(ErroreMCP) as errore:
        carica_strumenti_mcp(argomenti)
    assert str(errore.value).startswith(inizio)

def test_errore_di_trasporto(caplog):
    with pytest.raises(ErroreTrasportoMCP) as errore:
        rendi_sincrono(strumento_che_solleva(OSError("pipe chiusa"))).invoke({"espressione": "1"})
    assert str(errore.value) == "server MCP calcolatrice non raggiungibile: pipe chiusa"
    assert any(r.levelname == "WARNING" and "non raggiungibile" in r.getMessage() for r in caplog.records)

def test_tool_exception_dentro_un_gruppo_resta_validazione():
    gruppo = ExceptionGroup("gruppo", [ToolException("Error executing tool calcola: divisione per zero")])
    with pytest.raises(ToolException) as errore:
        rendi_sincrono(strumento_che_solleva(gruppo)).invoke({"espressione": "1/0"})
    assert str(errore.value) == "divisione per zero" and not isinstance(errore.value, ErroreTrasportoMCP)

def test_ctrl_c_non_diventa_un_errore_di_trasporto():
    with pytest.raises(KeyboardInterrupt):
        rendi_sincrono(strumento_che_solleva(KeyboardInterrupt())).invoke({"espressione": "1"})

def test_discovery_da_un_altra_cartella(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert [s.name for s in carica_strumenti_mcp()] == ["calcola"]
```

- [ ] **Step 3:** stesso comando → FAIL sui test nuovi.
- [ ] **Step 4: Completare** `client_mcp.py` secondo le Interfaces.
- [ ] **Step 5:** stesso comando → PASS (11 test). Annotare nel report la durata della discovery e di una chiamata,
  lette dai log INFO (servono al README). Poi la suite completa → tutti verdi.
- [ ] **Step 6: Commit** `feat(mcp): aggiunge il client MCP con discovery e strumenti sincroni`.

### Task 4: Integrazione nel grafo e all'avvio

**Files:**
- Modify: `assistente/grafo.py` (`nodo_strumenti`, `PROMPT_DI_SISTEMA`), `assistente/__main__.py`
- Modify (test): `tests/test_grafo.py`, `tests/test_main.py` (fixture `ambiente_pulito` + due test)
- Create (test): `tests/test_integrazione_mcp.py`

**Interfaces:**
- Consumes: `client_mcp.carica_strumenti_mcp()`, `client_mcp.ErroreMCP` (Task 3); `ToolException` di
  `langchain_core.tools`.
- Produces:
  - in `nodo_strumenti`, `strumento.invoke(argomenti)` è protetto da `except ToolException as errore` →
    `ToolMessage(content=f"Errore: {errore}", tool_call_id=..., name=nome, status="error")` e log WARNING
    `nodo_strumenti: errore dello strumento {nome}: {errore}`. I risultati riusciti restano invariati (status di
    default `"success"`); le altre eccezioni non si intercettano;
  - `PROMPT_DI_SISTEMA` con, in coda, la frase esatta: ` Per qualsiasi calcolo aritmetico chiama lo strumento
    calcola con l'espressione (numeri con il punto decimale, ** per le potenze) invece di calcolare da te, e usa il
    risultato così com'è; se lo strumento restituisce un errore, dillo senza inventare un risultato.`;
  - `main()`:
    - dopo `verifica_modello`, dentro lo stesso `try`, esegue `strumenti_mcp = carica_strumenti_mcp()`;
    - `except (ErroreConfigurazione, ErroreServer, ErroreMCP)`;
    - poi `costruisci_grafo(crea_modello(config), [crea_strumento_orologio(config.fuso), *strumenti_mcp])`;
    - docstring aggiornata (codice 1 anche se il server MCP non parte).

- [ ] **Step 1: Scrivere i test che falliscono in `tests/test_grafo.py`** (aggiungere gli import
  `StructuredTool`, `ToolException`)

```python
def solleva_tool_exception(espressione: str) -> str:
    raise ToolException("divisione per zero")

calcola_finta = StructuredTool.from_function(func=solleva_tool_exception, name="calcola", description="prova")

def richiesta_calcolo(id, espressione="1/0"):
    return AIMessage("", tool_calls=[{"name": "calcola", "args": {"espressione": espressione}, "id": id}])

def test_errore_dello_strumento_diventa_tool_message_d_errore(caplog):
    finto = ModelloFinto([richiesta_calcolo("k1"), AIMessage("Non si può dividere per zero.")])
    nuova = esegui_turno(costruisci_grafo(finto, [calcola_finta]), [], "Quanto fa 1/0?")
    assert [m.type for m in nuova] == ["human", "ai", "tool", "ai"]
    assert (nuova[2].content, nuova[2].status, nuova[2].tool_call_id, nuova[2].name) == \
        ("Errore: divisione per zero", "error", "k1", "calcola")
    assert len(finto.chiamate) == 2 and finto.chiamate[1][-1].type == "tool"
    assert "nodo_strumenti: errore dello strumento calcola: divisione per zero" in \
        [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]

def test_le_altre_eccezioni_dello_strumento_annullano_il_turno():
    def rotto(espressione: str) -> str:
        raise RuntimeError("difetto")
    strumento = StructuredTool.from_function(func=rotto, name="calcola", description="prova")
    with pytest.raises(RuntimeError):
        esegui_turno(costruisci_grafo(ModelloFinto([richiesta_calcolo("k1")]), [strumento]), [], "?")

def test_un_errore_non_blocca_le_altre_richieste():
    doppia = AIMessage("", tool_calls=[{"name": "calcola", "args": {"espressione": "1/0"}, "id": "a"},
                                       {"name": "ora_corrente", "args": {}, "id": "b"}])
    finto = ModelloFinto([doppia, AIMessage("ok")])
    nuova = esegui_turno(costruisci_grafo(finto, [calcola_finta, orologio]), [], "?")
    risposte = [m for m in nuova if m.type == "tool"]
    assert [(m.tool_call_id, m.status) for m in risposte] == [("a", "error"), ("b", "success")]
    assert risposte[1].content == "lunedì 2026-10-26T16:42:10+01:00 (Europe/Rome)"

def test_il_prompt_chiede_la_calcolatrice_e_conserva_l_orologio():
    assert "chiama lo strumento calcola" in PROMPT_DI_SISTEMA
    assert "senza inventare un risultato" in PROMPT_DI_SISTEMA
    assert "chiama sempre lo strumento ora_corrente" in PROMPT_DI_SISTEMA
```

- [ ] **Step 2: Scrivere i test che falliscono in `tests/test_main.py`**:
  - nella fixture `ambiente_pulito`, aggiungere `monkeypatch.setattr(avvio, "carica_strumenti_mcp", lambda: [])`,
    così nessun test di `main()` avvia il server vero;
  - poi i due test:

```python
def test_main_errore_mcp_all_avvio_uscita_1(monkeypatch):
    for nome, valore in VALIDO.items():
        monkeypatch.setenv(nome, valore)
    monkeypatch.setattr(avvio, "leggi_modelli_disponibili", lambda url: [VALIDO["LMSTUDIO_MODEL"]])
    def discovery_fallita():
        raise ErroreMCP("server MCP calcolatrice non avviato (python -m calcolatrice_mcp): Connection closed")
    monkeypatch.setattr(avvio, "carica_strumenti_mcp", discovery_fallita)
    codice, errori = esegui_main_con_errore(monkeypatch)
    assert codice == 1
    assert errori.startswith("Errore: server MCP calcolatrice non avviato") and "Traceback" not in errori

def test_main_passa_al_grafo_l_orologio_e_gli_strumenti_mcp(monkeypatch):
    usa_flussi_finti(monkeypatch)
    for nome, valore in VALIDO.items():
        monkeypatch.setenv(nome, valore)
    monkeypatch.setattr(avvio, "leggi_modelli_disponibili", lambda url: [VALIDO["LMSTUDIO_MODEL"]])
    monkeypatch.setattr(avvio, "crea_modello", lambda config: object())
    calcola_finta = StructuredTool.from_function(func=lambda espressione: "4", name="calcola", description="prova")
    monkeypatch.setattr(avvio, "carica_strumenti_mcp", lambda: [calcola_finta])
    ricevuti = []
    monkeypatch.setattr(avvio, "costruisci_grafo", lambda modello, strumenti: ricevuti.append(strumenti) or "grafo")
    monkeypatch.setattr(avvio, "esegui_chat", lambda grafo, server, **opzioni: None)
    assert avvio.main() == 0
    assert [s.name for s in ricevuti[0]] == ["ora_corrente", "calcola"]
```

- [ ] **Step 3: Scrivere `tests/test_integrazione_mcp.py`** (grafo con il modello finto e il **server vero**)

```python
@pytest.fixture(scope="module")
def strumenti():
    return [crea_strumento_orologio(ZoneInfo("Europe/Rome")), *carica_strumenti_mcp()]

def richiesta_calcolo(id, espressione):
    return AIMessage("", tool_calls=[{"name": "calcola", "args": {"espressione": espressione}, "id": id}])

def test_calcolo_con_il_server_vero(strumenti):
    finto = ModelloFinto([richiesta_calcolo("m1", "12.5*8-3"), AIMessage("Fa 97.")])
    nuova = esegui_turno(costruisci_grafo(finto, strumenti), [], "Quanto fa 12,5 per 8 meno 3?")
    assert (nuova[2].content, nuova[2].status, nuova[2].tool_call_id) == ("97", "success", "m1")
    assert nuova[-1].content == "Fa 97."

def test_errore_controllato_senza_falso_successo(strumenti):
    finto = ModelloFinto([richiesta_calcolo("m2", "1/0"), AIMessage("Non si può dividere per zero.")])
    nuova = esegui_turno(costruisci_grafo(finto, strumenti), [], "Quanto fa 1 diviso 0?")
    assert (nuova[2].content, nuova[2].status, nuova[2].tool_call_id) == \
        ("Errore: divisione per zero", "error", "m2")
    assert len(finto.chiamate) == 2

def test_argomento_con_nome_sbagliato_diventa_un_errore(strumenti, caplog):
    sbagliata = AIMessage("", tool_calls=[{"name": "calcola", "args": {"expression": "2+2"}, "id": "w1"}])
    nuova = esegui_turno(costruisci_grafo(ModelloFinto([sbagliata, AIMessage("ok")]), strumenti), [], "2+2?")
    assert nuova[2].status == "error" and nuova[2].content.startswith("Errore: ")
    assert any("argomenti ignorati" in r.getMessage() for r in caplog.records)

def test_cronologia_su_due_turni_con_lo_strumento_mcp(strumenti):
    finto = ModelloFinto([richiesta_calcolo("t1", "2+2"), AIMessage("Fa 4."), AIMessage("Hai chiesto 2+2.")])
    grafo = costruisci_grafo(finto, strumenti)
    cronologia = esegui_turno(grafo, esegui_turno(grafo, [], "Quanto fa 2+2?"), "Che cosa ti ho chiesto?")
    assert [m.type for m in cronologia] == ["human", "ai", "tool", "ai", "human", "ai"]
    assert cronologia[2].content == "4"

def test_limite_di_passaggi_con_lo_strumento_mcp(strumenti):
    finto = ModelloFinto([richiesta_calcolo(f"l{i}", "1+1") for i in range(20)])
    with pytest.raises(GraphRecursionError):
        esegui_turno(costruisci_grafo(finto, strumenti), [], "?")
```

- [ ] **Step 4:** `.\.venv\Scripts\python.exe -m pytest tests/test_grafo.py tests/test_main.py
  tests/test_integrazione_mcp.py -v` → FAIL sui test nuovi.
- [ ] **Step 5: Implementare** le modifiche a `grafo.py` e `__main__.py` secondo le Interfaces.
- [ ] **Step 6:** stesso comando → PASS. Poi `.\.venv\Scripts\python.exe -m pytest` → tutti verdi (i 111
  originali e tutti i nuovi), con il numero totale nel report. Confinamento dell'asincronia:
  `Select-String -Path assistente\*.py -Pattern "asyncio|langchain_mcp_adapters" | Where-Object { $_.Filename -ne "client_mcp.py" }`
  → nessuna riga.
- [ ] **Step 7: Commit** `feat(grafo): collega gli strumenti MCP e restituisce gli errori come ToolMessage`.

### Task 5: Prove reali con LM Studio e prova da pipe

**Files:**
- Modify: `tests/test_reale.py`

**Interfaces:**
- Consumes: `carica_strumenti_mcp()` (Task 3), grafo e prompt del Task 4.

- [ ] **Step 1: Aggiornare la fixture `grafo`** con
  `[crea_strumento_orologio(config.fuso), *carica_strumenti_mcp()]`, come in `main`, e aggiungere:

```python
def test_reale_calcolo(grafo):
    cronologia = esegui_turno(grafo, [], "Quanto fa 12,5 per 8 meno 3?")
    risultati = [m.content for m in cronologia if m.type == "tool" and m.name == "calcola"]
    assert "97" in risultati and "97" in cronologia[-1].text
```

- [ ] **Step 2:** con LM Studio acceso (`google/gemma-4-e4b`) e il `.env` compilato, in background e da solo:
  `.\.venv\Scripts\python.exe -m pytest -m reale -v` → 5 passed. Se `test_reale_calcolo` fallisce perché il modello
  non chiama `calcola`:
  - un solo giro di ritocco, solo sul testo della frase del prompt (Task 4) e della docstring (Task 2), con i test
    automatici aggiornati;
  - poi rieseguire;
  - se fallisce ancora, fermarsi e riportarlo, senza toccare limiti o contratto.
- [ ] **Step 3: Prova da pipe** in un figlio pulito (vedi Global Constraints), con uno script `.ps1` in UTF-8 con
  BOM nella cartella scratchpad della sessione, non nel progetto. Lo script contiene:
  - la riga `$OutputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false`;
  - `"Quanto fa 12,5 per 8 meno 3?`nQuanto fa 5 diviso 0?`n/esci" | .\.venv\Scripts\python.exe -m assistente`.

  Atteso:
  - la riga del catalogo;
  - `instradamento: richiesta strumento calcola …`;
  - `client_mcp: calcola eseguito in …`;
  - `nodo_strumenti: calcola -> 97` e una risposta con 97;
  - per la divisione per zero: un `calcola` con `WARNING … divisione per zero` e una risposta senza numero
    inventato, oppure una risposta diretta del modello. Riportare quale dei due.

  Annotare le durate lette nei log.
- [ ] **Step 4: Commit** `test(reale): aggiunge la prova reale della calcolatrice MCP` (più gli eventuali ritocchi
  di testo dello Step 2, nominati nel messaggio).

### Task 6: Docker

**Files:**
- Modify: `Dockerfile`

- [ ] **Step 1:** aggiungere `COPY calcolatrice_mcp/ calcolatrice_mcp/` subito dopo `COPY assistente/ assistente/`.
- [ ] **Step 2:** con Docker Desktop acceso, `docker compose build` → riuscito. Se mancano wheel Linux per Python 3.14
  e pip prova a compilare: fermarsi e riportarlo (nessuno strumento di compilazione aggiunto senza approvazione).
- [ ] **Step 3: Prova da pipe nel container** (LM Studio acceso):
  `"Quanto fa 12,5 per 8 meno 3?`n/esci" | docker compose run --rm -T assistente`. Atteso: la riga del catalogo,
  la richiesta e l'esecuzione di `calcola` nei log, la risposta con 97. Poi `docker compose down`. I container
  `datalab-*` non si toccano.
- [ ] **Step 4: Commit** `feat(docker): include il server MCP della calcolatrice nell'immagine`.

### Task 7: Documentazione e verifica finale

**Files:**
- Modify: `README.md`, `CLAUDE.md` (sezione Struttura)

- [ ] **Step 1: README**, sezione nuova `## Calcolatrice (strumento MCP)` dopo `## Strumento orologio`:
  - che cosa fa e perché è un server MCP;
  - lo schema discovery → richiesta → esecuzione → `ToolMessage`;
  - dove stanno server e client;
  - le righe di log reali dei Task 5 e 6;
  - la durata misurata;
  - gli errori controllati.

  Poi:
  - in `## Test`, i file di test nuovi e il comando per provare solo il server
    (`.\.venv\Scripts\python.exe -m pytest tests/test_server_mcp.py -v`);
  - in `## Diagnosi`, i livelli della slide: il server da solo (quel comando) → discovery all'avvio (riga del
    catalogo o `Errore: server MCP calcolatrice non avviato …`) → richiesta del modello (`instradamento`) →
    esecuzione (`client_mcp`) → `ToolMessage` (`nodo_strumenti`).
- [ ] **Step 2: `CLAUDE.md`**, sezione Struttura:
  - `calcolatrice_mcp/`: server MCP della calcolatrice (`calcolo.py` logica pura, `server.py` FastMCP,
    `python -m calcolatrice_mcp`);
  - `assistente/client_mcp.py`: discovery e strumenti MCP sincroni.

  I comandi non cambiano.
- [ ] **Step 3: Verifica in una PowerShell pulita** (senza `PYTHONIOENCODING`):
  - `.\.venv\Scripts\python.exe -m pytest` → tutti verdi;
  - ogni comando nuovo o modificato del README, eseguito così com'è scritto.
- [ ] **Step 4: Commit** `docs: documenta la calcolatrice MCP nel README e nel CLAUDE.md`.

---

## Dopo il piano
1. Revisione finale dell'intero branch con **Opus**, dall'inizio del piano a `HEAD`. Poi una sola ondata di
   correzioni e una revisione mirata.
2. Verifica del controller, rieseguita di persona: test automatici, test reali, prove da pipe in locale e in Docker,
   `git status` pulito.
3. Merge in `dev` (`git merge --no-ff feature/calcolatrice -m "merge: integra feature/calcolatrice in dev"`) **solo
   su richiesta dell'utente**, poi i test su `dev`. Nessun push senza richiesta.
