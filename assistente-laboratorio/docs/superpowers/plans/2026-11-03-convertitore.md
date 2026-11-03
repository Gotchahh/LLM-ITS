# Convertitore di unità nel grafo — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** aggiungere lo strumento locale `converti(valore, da, a)` per lunghezze, pesi e temperature, eseguito dal ciclo del grafo esistente.

**Architecture:** un modulo nuovo `assistente/convertitore.py` con la logica pura (tabelle delle unità, conversione, formato) e la fabbrica dello strumento LangChain; gli errori sono `ToolException`, che `nodo_strumenti` trasforma già in `ToolMessage` con `status="error"`. Il grafo non cambia: si aggiunge una regola al prompt di sistema e lo strumento all'elenco in `__main__.py`.

**Tech Stack:** Python 3.14.7, `langchain_core` (`StructuredTool`, `ToolException`), `decimal` e `math` della libreria standard, pytest.

**Spec:** `docs/superpowers/specs/2026-11-03-convertitore-design.md`

## Global Constraints
- Nessuna dipendenza nuova; nessuna nuova variabile d'ambiente.
- In `assistente/` niente import diretti di `openai`, `httpx`, `pydantic`.
- Codice sincrono, moduli piccoli; i comandi si eseguono da `assistente-laboratorio/` in PowerShell con `.\.venv\Scripts\python.exe`.
- Branch `feature/convertitore`; Conventional Commits in italiano con la riga `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; prima di ogni commit `git status`, diff, staging selettivo. Niente merge né push.
- Messaggi d'errore e testi per il modello in italiano; mai un numero quando la conversione fallisce.
- Prove da pipe senza `PYTHONIOENCODING`, in una PowerShell pulita (`Remove-Item Env:PYTHONIOENCODING; powershell.exe -NoProfile -File <script>.ps1`, script UTF-8 con BOM nello scratchpad).

## Review Focus
1. Il modello passa unità con spazi o maiuscole insolite (`" Gradi  Celsius "`, `"KM"`, `"°c"`): devono essere riconosciute (spazi interni ridotti a uno). Test in Task 1.
2. Risultati molto piccoli o molto grandi (1 mg → t, 1000 mi → mm): mai notazione esponenziale. Test in Task 1.
3. Temperature negative valide (−40 °C, −459,67 °F, 0 K) non vanno scambiate per «valore negativo»: il controllo dei negativi vale solo per lunghezze e pesi. Test in Task 1.
4. Il valore ricevuto come testo non numerico (`"tanti"`) deve arrivare al modello come `ToolMessage` d'errore in italiano, non come successo né come traccia pydantic. Test in Task 2 (attraverso il grafo).
5. La nuova regola nel prompt non deve togliere quelle di `ora_corrente` e `calcola`. Test in Task 2.

---

### Task 1: logica e strumento `converti`

**Files:**
- Create: `assistente/convertitore.py`
- Test: `tests/test_convertitore.py`

**Interfaces:**
- Produces:
  - `formatta_numero(x: float, cifre: int | None = None) -> str`: notazione decimale ordinaria, virgola, niente zeri finali inutili, niente `-0`; con `cifre` arrotonda a quel numero di cifre significative, senza lo riporta com'è (`repr` più corto).
  - `converti(valore: float, da: str, a: str) -> str`: restituisce `"<valore> <simbolo da> = <risultato> <simbolo a>"` (valore com'è, risultato a 6 cifre significative) o solleva `ToolException`.
  - `crea_strumento_convertitore() -> BaseTool`: `StructuredTool` di nome `"converti"`, parametri `valore`, `da`, `a`.

- [ ] **Step 1: scrivere i test che falliscono** in `tests/test_convertitore.py` (parametrizzati dove possibile; `ToolException` da `langchain_core.tools`):

```python
@pytest.mark.parametrize("valore, da, a, atteso", [
    (2, "cm", "m", "2 cm = 0,02 m"),
    (4, "centimetri", "metri", "4 cm = 0,04 m"),
    (25, "m", "km", "25 m = 0,025 km"),
    (1, "mi", "m", "1 mi = 1609,34 m"),
    (1, "pollice", "cm", "1 in = 2,54 cm"),
    (1, "piede", "pollici", "1 ft = 12 in"),
    (1, "mm", "m", "1 mm = 0,001 m"),
    (1, "lb", "kg", "1 lb = 0,453592 kg"),
    (16, "once", "libbre", "16 oz = 1 lb"),
    (1, "t", "kg", "1 t = 1000 kg"),
    (1, "mg", "g", "1 mg = 0,001 g"),
    (1, "chili", "grammi", "1 kg = 1000 g"),
    (20, "°C", "°F", "20 °C = 68 °F"),
    (0, "celsius", "kelvin", "0 °C = 273,15 K"),
    (-40, "C", "F", "-40 °C = -40 °F"),
    (0, "K", "°C", "0 K = -273,15 °C"),
    (-459.67, "fahrenheit", "K", "-459,67 °F = 0 K"),
    (2.5, "m", "m", "2,5 m = 2,5 m"),
    (1234567, "m", "km", "1234567 m = 1234,57 km"),
])
def test_conversioni(valore, da, a, atteso): assert converti(valore, da, a) == atteso
```

  Altri test, con questi nomi e asserzioni:
  - `test_nomi_senza_maiuscole_e_spazi`: `converti(1, " KM ", "M") == "1 km = 1000 m"` e `converti(20, " Gradi  Celsius ", "°f") == "20 °C = 68 °F"`.
  - `test_mai_notazione_esponenziale`: `converti(1, "mg", "t") == "1 mg = 0,000000001 t"`; `converti(1000, "mi", "mm") == "1000 mi = 1609340000 mm"`; `converti(0.000001, "km", "mm") == "0,000001 km = 0,001 mm"`.
  - `test_formatta_numero`: `formatta_numero(-0.0) == "0"`, `formatta_numero(0.1 + 0.2, 6) == "0,3"`, `formatta_numero(-1e-12, 6) == "-0,000000000001"`, `formatta_numero(1609.344, 6) == "1609,34"`.
  - `test_grandezze_diverse`: `converti(5, "kg", "m")` solleva `ToolException` con `"peso"` e `"lunghezza"` nel messaggio; `converti(5, "°C", "g")` con `"temperatura"` e `"peso"`.
  - `test_unita_sconosciuta`: `converti(10, "m", "iarde")` → messaggio con `«iarde»` e con `"km"`, `"lb"`, `"°F"` (elenco delle unità); vale anche per un `da` sconosciuto.
  - `test_sotto_lo_zero_assoluto`: `converti(-300, "°C", "K")`, `converti(-1, "K", "°C")`, `converti(-500, "°F", "°C")` → messaggio con `"zero assoluto"` e `"-273,15 °C"`.
  - `test_peso_o_lunghezza_negativi`: `converti(-5, "kg", "g")` → `"peso"` e `"negativo"`; `converti(-1, "m", "cm")` → `"lunghezza"` e `"negativ"`; `converti(0, "kg", "g") == "0 kg = 0 g"`.
  - `test_valore_non_finito`: `converti(float("inf"), "m", "km")` e `converti(float("nan"), "m", "km")` → messaggio con `"numero"`.
  - `test_strumento`: `crea_strumento_convertitore()` ha `name == "converti"`, `set(args) == {"valore", "da", "a"}`, `invoke({"valore": 2, "da": "cm", "a": "m"}) == "2 cm = 0,02 m"`; `invoke({"valore": "tanti", "da": "m", "a": "km"})` solleva `ToolException` con `"numero"` nel messaggio e senza `"validation"`.

- [ ] **Step 2: eseguire e vedere fallire**
  Run: `.\.venv\Scripts\python.exe -m pytest tests/test_convertitore.py -q`
  Expected: errore di import (`assistente.convertitore` non esiste).

- [ ] **Step 3: implementare `assistente/convertitore.py`**
  - Tabelle: per ogni unità simbolo, grandezza (`"lunghezza"`, `"peso"`, `"temperatura"`), fattore verso la base (m, kg) e nomi accettati, esattamente come la tabella della specifica. Indice di ricerca su `" ".join(testo.split()).lower()`.
  - Fattori esatti: in 0,0254; ft 0,3048; mi 1609,344; lb 0,45359237; oz 0,028349523125 (calcolo in `float`, l'arrotondamento a 6 cifre assorbe gli errori di rappresentazione).
  - Temperature via kelvin: K = °C + 273,15; °C = (°F − 32) × 5/9. Controllo dello zero assoluto sul valore convertito in kelvin, prima di arrotondare (0 K esatto valido; per −459,67 °F tollerare l'errore di rappresentazione con `kelvin < -1e-9`). Il risultato di una temperatura passa per `round(..., 10)` prima del formato: senza, −459,67 °F darebbe un residuo come `5,68434e-14 K` invece di `0 K`.
  - Ordine dei controlli: unità riconosciute → stessa grandezza → valore finito → negativo (solo lunghezza e peso) → zero assoluto (solo temperatura).
  - `formatta_numero`: con `cifre`, `format(x, f".{cifre}g")`; poi passare per `Decimal(str(...))` e `format(d, "f")` per togliere l'esponente, togliere gli zeri finali dopo il punto e il punto finale, sostituire `.` con `,`, trasformare `-0` in `0`.
  - Strumento: `StructuredTool.from_function(func=converti, name="converti", description=..., handle_validation_error=<funzione che solleva ToolException(<messaggio italiano col "numero">)>)`; descrizioni in italiano dei tre parametri con `Annotated` come in `assistente/strumenti.py`, che elencano le unità per grandezza. Verificare nel test che il `ToolException` sollevato dentro `handle_validation_error` esca da `invoke` (se la versione di `langchain_core` lo intercettasse, validare `valore` dentro `converti` con firma `valore: float | str` e lasciarne traccia nel commit).

- [ ] **Step 4: eseguire e vedere passare**
  Run: `.\.venv\Scripts\python.exe -m pytest tests/test_convertitore.py -q` → tutti passati; poi `.\.venv\Scripts\python.exe -m pytest -q` → 188 + nuovi, nessun fallimento.

- [ ] **Step 5: commit**
  `git add assistente/convertitore.py tests/test_convertitore.py`; messaggio `feat(strumenti): aggiunge lo strumento converti per lunghezze, pesi e temperature`.

### Task 2: collegamento al grafo e all'avvio

**Files:**
- Modify: `assistente/grafo.py` (`PROMPT_DI_SISTEMA`)
- Modify: `assistente/__main__.py` (elenco strumenti)
- Test: `tests/test_grafo.py`, `tests/test_main.py`

**Interfaces:**
- Consumes: `crea_strumento_convertitore()` (Task 1).
- Produces: elenco strumenti all'avvio nell'ordine `["ora_corrente", "converti", "calcola"]`.

- [ ] **Step 1: scrivere i test che falliscono**
  - `tests/test_grafo.py::test_il_prompt_chiede_il_convertitore`: `"chiama lo strumento converti" in PROMPT_DI_SISTEMA`; restano veri `"chiama lo strumento calcola"`, `"chiama sempre lo strumento ora_corrente"`, `"senza inventare un risultato"`.
  - `tests/test_grafo.py::test_percorso_con_il_convertitore(caplog)`: `ModelloFinto` con una richiesta `converti` `{"valore": 25, "da": "m", "a": "km"}` id `"v1"`, poi `AIMessage("25 metri sono 0,025 km.")`; tipi `["human", "ai", "tool", "ai"]`, `nuova[2].tool_call_id == "v1"`, `nuova[2].content == "25 m = 0,025 km"`, `nuova[2].status == "success"`, e `"nodo_strumenti: converti -> 25 m = 0,025 km"` in `caplog.messages`.
  - `tests/test_grafo.py::test_conversione_impossibile_diventa_errore`: richiesta `{"valore": 5, "da": "kg", "a": "m"}` → `ToolMessage` con `status == "error"`, contenuto che inizia con `"Errore: "` e contiene `"peso"`.
  - `tests/test_grafo.py::test_valore_non_numerico_diventa_errore`: richiesta `{"valore": "tanti", "da": "m", "a": "km"}` → `status == "error"`, `"numero"` nel contenuto.
  - `tests/test_main.py`: nel test esistente che controlla l'elenco (riga con `["ora_corrente", "calcola"]`) l'atteso diventa `["ora_corrente", "converti", "calcola"]`.

- [ ] **Step 2: eseguire e vedere fallire**
  Run: `.\.venv\Scripts\python.exe -m pytest tests/test_grafo.py tests/test_main.py -q` → falliscono il test del prompt e quello dell'elenco.

- [ ] **Step 3: implementare**
  - Prompt: aggiungere in fondo una frase del tipo «Per ogni conversione tra unità di lunghezza, peso o temperatura chiama lo strumento converti invece di calcolare da te o con calcola, e usa il risultato così com'è; se lo strumento restituisce un errore, di' che la conversione non si può fare e perché.» Non toccare le frasi esistenti.
  - `__main__.py`: `costruisci_grafo(crea_modello(config), [crea_strumento_orologio(config.fuso), crea_strumento_convertitore(), *strumenti_mcp])`.

- [ ] **Step 4: eseguire e vedere passare**
  Run: `.\.venv\Scripts\python.exe -m pytest -q` → tutto verde.

- [ ] **Step 5: commit**
  `git add assistente/grafo.py assistente/__main__.py tests/test_grafo.py tests/test_main.py`; messaggio `feat(grafo): collega lo strumento converti e aggiunge la regola nel prompt`.

### Task 3: prove reali, Docker e documentazione

**Files:**
- Modify: `tests/test_reale.py`
- Modify: `README.md`, `CLAUDE.md`

**Interfaces:**
- Consumes: `crea_strumento_convertitore()` (Task 1), prompt e avvio (Task 2).

- [ ] **Step 1: prove reali** in `tests/test_reale.py`: la fixture `grafo` aggiunge `crea_strumento_convertitore()` nello stesso ordine di `main`; nuovi test
  - `test_reale_conversione_lunghezza`: `esegui_turno(grafo, [], "Quanti metri sono 4 cm?")`; tra i `ToolMessage` di nome `converti` uno uguale a `"4 cm = 0,04 m"`, e `"0,04"` nella risposta finale.
  - `test_reale_conversione_temperatura`: `"Quanti gradi Fahrenheit sono 20 °C?"`; un `ToolMessage` `converti` uguale a `"20 °C = 68 °F"`, e `"68"` nella risposta finale.

- [ ] **Step 2: eseguire le prove reali** (LM Studio acceso con `google/gemma-4-e4b`)
  Run: `.\.venv\Scripts\python.exe -m pytest -m reale -v` → 7 passati. Se una prova fallisce per scelta del modello, ritoccare solo la descrizione dello strumento o la regola nel prompt (nel modulo, con il test automatico corrispondente aggiornato) e ripetere; non indebolire le asserzioni senza chiedere all'utente.

- [ ] **Step 3: prova Docker da pipe** in una PowerShell pulita: `docker compose build`, poi `"Quanti km sono 25 metri?" | docker compose run --rm -T assistente` (con `LOG_LEVEL=INFO`, come nelle prove della calcolatrice) → nel log `instradamento: richiesta strumento converti` e `nodo_strumenti: converti -> 25 m = 0,025 km`; risposta con `0,025`. Prova da pipe anche in locale con `.\.venv\Scripts\python.exe -m assistente`.

- [ ] **Step 4: documentazione**
  - README: introduzione (terzo strumento), sezione «Convertitore (funzione nel grafo)» tra «Strumento orologio» e «Calcolatrice» con unità, formato, errori, motivazione della modalità e il log reale della prova; sezione «Test» con i nuovi test reali e `tests/test_convertitore.py`; una voce in «Diagnosi» (manca `richiesta strumento converti` → il modello ha risposto senza lo strumento). Solo comandi eseguiti in questo task.
  - `CLAUDE.md` (progetto), sezione Struttura: riga `convertitore.py: strumento converti (lunghezze, pesi, temperature; logica pura e fabbrica dello strumento)`.

- [ ] **Step 5: verifica e commit**
  Run: `.\.venv\Scripts\python.exe -m pytest -q` → tutto verde. Due commit: `test(reale): aggiunge le prove reali del convertitore` (`tests/test_reale.py`) e `docs: documenta il convertitore nel README e nel CLAUDE.md` (`README.md`, `CLAUDE.md`).

### Dopo i task
Una revisione finale dell'intero branch con un subagente `opus` (`git diff 5d971fc..HEAD`), correzione di ciò che è Critical o Important, resoconto all'utente. Merge in `dev` solo su sua richiesta.
