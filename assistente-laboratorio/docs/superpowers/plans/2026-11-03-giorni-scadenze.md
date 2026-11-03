# Giorni e scadenze nel grafo — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** aggiungere quattro strumenti locali sul calendario (`giorni_tra`, `sposta_data`, `giorno_settimana`, `pasqua`), eseguiti dal ciclo del grafo esistente.

**Architecture:** un modulo nuovo `assistente/calendario.py` con la logica pura (lettura delle date, formato italiano, Pasqua) e la fabbrica dei quattro strumenti, che leggono «oggi» da un `adesso` iniettabile nel fuso configurato, come l'orologio. Gli errori sono `ToolException`, che `nodo_strumenti` trasforma già in `ToolMessage` con `status="error"`. Il grafo non cambia: si aggiunge una regola al prompt e gli strumenti all'elenco in `__main__.py`.

**Tech Stack:** Python 3.14.7, `datetime`/`zoneinfo` della libreria standard, `langchain_core` (`StructuredTool`, `ToolException`), pytest.

**Spec:** `docs/superpowers/specs/2026-11-03-giorni-scadenze-design.md`

## Global Constraints
- Nessuna dipendenza nuova; nessuna nuova variabile d'ambiente.
- In `assistente/` niente import diretti di `openai`, `httpx`, `pydantic`.
- Codice sincrono, moduli piccoli; comandi da `assistente-laboratorio/` in PowerShell con `.\.venv\Scripts\python.exe`.
- Branch `feature/giorni-scadenze`; Conventional Commits in italiano con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; prima di ogni commit `git status`, diff, staging selettivo. Niente merge né push.
- Testi per il modello e messaggi d'errore in italiano; mai una data o un numero quando la richiesta non ha senso.
- Prove da pipe senza `PYTHONIOENCODING`, in una PowerShell pulita (script UTF-8 con BOM nello scratchpad, `powershell.exe -NoProfile -File`).

## Review Focus
1. «Oggi» vicino alla mezzanotte: alle 23:30 UTC del 2 novembre a Roma è già il 3 novembre; il conteggio deve usare il 3. Test in Task 1.
2. Date senza anno uguali a oggi, appena passate (ieri) e il 29 febbraio: prossima occorrenza corretta, oggi compreso. Test in Task 1.
3. Singolare e plurale («manca 1 giorno», «tra 1 giorno»): niente «1 giorni». Test in Task 1.
4. Spazi attorno alle date (`" 12-25 "`) e numeri passati come testo (`"30"`): accettati; `2.5` giorni: errore in italiano attraverso il grafo. Test in Task 1 e Task 2.
5. La nuova regola nel prompt non deve togliere quelle di `ora_corrente`, `converti` e `calcola`. Test in Task 2.

---

### Task 1: logica e strumenti del calendario

**Files:**
- Create: `assistente/calendario.py`
- Test: `tests/test_calendario.py`

**Interfaces:**
- Consumes: `GIORNI` da `assistente/strumenti.py` (nomi dei giorni, lunedì = indice 0).
- Produces:
  - `formatta_data(d: date) -> str` → `"venerdì 25 dicembre 2026"`.
  - `leggi_data(testo: str, oggi: date) -> date`: `AAAA-MM-GG` o `MM-GG` (prossima occorrenza da `oggi` compreso); altrimenti `ToolException`.
  - `data_di_pasqua(anno: int) -> date` (algoritmo anonimo gregoriano, Meeus/Jones/Butcher); `ToolException` sotto il 1583 o fuori da 1–9999.
  - `giorni_tra(data: str, partenza: str | None, oggi: date) -> str`, `sposta_data(giorni: int, data: str | None, oggi: date) -> str`, `giorno_settimana(data: str, oggi: date) -> str`, `pasqua(anno: int | None, oggi: date) -> str`.
  - `crea_strumenti_calendario(fuso: ZoneInfo, adesso: Callable[[], datetime] = lambda: datetime.now(UTC)) -> list[BaseTool]`: i quattro strumenti in questo ordine, nomi `giorni_tra`, `sposta_data`, `giorno_settimana`, `pasqua`; parametri come le funzioni pure senza `oggi`, che vale `adesso().astimezone(fuso).date()` a ogni chiamata.

- [ ] **Step 1: scrivere i test che falliscono** in `tests/test_calendario.py`, con `OGGI = date(2026, 11, 3)` (martedì):
  - `test_formatta_data`: `formatta_data(date(2026, 12, 25)) == "venerdì 25 dicembre 2026"`.
  - `test_leggi_data` (parametrizzato, con `OGGI`): `"2026-12-25"` → `date(2026, 12, 25)`; `" 12-25 "` → `date(2026, 12, 25)`; `"11-03"` → `date(2026, 11, 3)` (oggi compreso); `"11-02"` → `date(2027, 11, 2)`; `"02-29"` → `date(2028, 2, 29)`; `"1789-07-14"` → `date(1789, 7, 14)`.
  - `test_leggi_data_errori` (parametrizzato): `"2026-02-30"`, `"2026-13-01"`, `"02-30"` → messaggio con `"non valida"` e la data ricevuta; `"25 dicembre"`, `"25/12/2026"`, `""` → messaggio con `"2026-12-25"` e `"12-25"`.
  - `test_giorni_tra` (parametrizzato, oggi = `OGGI`):
    - `("12-25", None)` → `"da martedì 3 novembre 2026 a venerdì 25 dicembre 2026: mancano 52 giorni"`;
    - `("2026-01-01", None)` → `"da martedì 3 novembre 2026 a giovedì 1 gennaio 2026: sono passati 306 giorni"`;
    - `("2026-11-04", None)` → termina con `": manca 1 giorno"`; `("2026-11-02", None)` → termina con `": è passato 1 giorno"`;
    - `("11-03", None)` → `"martedì 3 novembre 2026: è oggi"`;
    - `("2026-06-02", "2026-03-10")` → termina con `": mancano 84 giorni"`; `("2026-03-10", "2026-03-10")` → termina con `": 0 giorni"`;
    - `("2027-03-01", "2027-02-01")` → termina con `": mancano 28 giorni"`.
  - `test_sposta_data` (parametrizzato):
    - `(30, None)` → `"tra 30 giorni: giovedì 3 dicembre 2026"`; `(-10, None)` → `"10 giorni fa: sabato 24 ottobre 2026"`;
    - `(1, None)` → `"tra 1 giorno: mercoledì 4 novembre 2026"`; `(0, None)` → `"oggi: martedì 3 novembre 2026"`;
    - `(60, None)` → termina con `"sabato 2 gennaio 2027"`;
    - `(1, "2028-02-28")` → `"1 giorno dopo lunedì 28 febbraio 2028: martedì 29 febbraio 2028"`; `(-1, "2027-01-01")` → `"1 giorno prima di venerdì 1 gennaio 2027: giovedì 31 dicembre 2026"`.
  - `test_giorno_settimana`: `giorno_settimana("1789-07-14", OGGI) == "martedì 14 luglio 1789"`; `giorno_settimana("12-25", OGGI) == "venerdì 25 dicembre 2026"`.
  - `test_pasqua` (parametrizzato `anno, atteso`): 1583 → `date(1583, 4, 10)`, 2024 → `date(2024, 3, 31)`, 2025 → `date(2025, 4, 20)`, 2026 → `date(2026, 4, 5)`, 2027 → `date(2027, 3, 28)`, 2038 → `date(2038, 4, 25)`, 2285 → `date(2285, 3, 22)`; `data_di_pasqua(anno) == atteso`. Inoltre `pasqua(2027, OGGI) == "Pasqua 2027: domenica 28 marzo 2027"` e `pasqua(None, OGGI) == "Pasqua 2026: domenica 5 aprile 2026"`.
  - `test_errori_di_intervallo`: `pasqua(1500, OGGI)` → `"1583"` nel messaggio; `pasqua(0, OGGI)` e `pasqua(10000, OGGI)` → `"1–9999"`; `sposta_data(10**7, None, OGGI)` e `sposta_data(-10**7, None, OGGI)` → `"1–9999"`.
  - `test_oggi_nel_fuso_configurato`: strumenti creati con `ZoneInfo("Europe/Rome")` e `adesso=lambda: datetime(2026, 11, 2, 23, 30, tzinfo=UTC)`; `giorni_tra.invoke({"data": "12-25"})` termina con `"mancano 52 giorni"`.
  - `test_strumenti`: nomi `["giorni_tra", "sposta_data", "giorno_settimana", "pasqua"]`; argomenti `{"data", "partenza"}`, `{"giorni", "data"}`, `{"data"}`, `{"anno"}`; `sposta_data.invoke({"giorni": "30"})` (testo) == `"tra 30 giorni: giovedì 3 dicembre 2026"` con `adesso` fisso al 3/11/2026 10:00 UTC; `sposta_data.invoke({"giorni": 2.5})` e `giorni_tra.invoke({})` sollevano `ToolException` in italiano (con il nome del parametro, senza `"validation"`).

- [ ] **Step 2: eseguire e vedere fallire**
  Run: `.\.venv\Scripts\python.exe -m pytest tests/test_calendario.py -q`
  Expected: errore di import (`assistente.calendario` non esiste).

- [ ] **Step 3: implementare `assistente/calendario.py`**
  - Mesi in italiano minuscoli (`gennaio` … `dicembre`); giorni da `GIORNI`.
  - `leggi_data`: regex `^\d{4}-\d{2}-\d{2}$` e `^\d{2}-\d{2}$` dopo `strip()`; data inesistente → «data non valida «…»»; altro testo → «formato di data non riconosciuto «…»: usare 2026-12-25 oppure 12-25 se l'anno non c'è». Per `MM-GG` provare l'anno di `oggi` e i successivi finché la data esiste ed è ≥ `oggi` (al massimo 8 anni, per il 29 febbraio).
  - Messaggi di intervallo: «anno fuori dall'intervallo 1–9999»; Pasqua: «la data di Pasqua si calcola solo dal 1583, dopo l'introduzione del calendario gregoriano». `sposta_data` cattura `OverflowError` di `date + timedelta`.
  - Singolare/plurale: «1 giorno», «N giorni»; «manca»/«mancano», «è passato»/«sono passati».
  - Strumenti: `StructuredTool.from_function` con parametri `Annotated` descritti in italiano (formati delle date, «omettere per oggi»), descrizioni che dicono quando usarli, `handle_validation_error` che solleva `ToolException` con un messaggio che spiega i parametri di quello strumento (come `_rifiuta_valore` in `assistente/convertitore.py`). `giorni: int`, `anno: int | None = None`, `partenza`/`data` facoltative `str | None = None`.

- [ ] **Step 4: eseguire e vedere passare**
  Run: `.\.venv\Scripts\python.exe -m pytest tests/test_calendario.py -q` → tutti passati; poi `.\.venv\Scripts\python.exe -m pytest -q` → 228 + nuovi, nessun fallimento.

- [ ] **Step 5: commit**
  `git add assistente/calendario.py tests/test_calendario.py`; messaggio `feat(strumenti): aggiunge gli strumenti del calendario per giorni, scadenze e Pasqua`.

### Task 2: collegamento al grafo e all'avvio

**Files:**
- Modify: `assistente/grafo.py` (`PROMPT_DI_SISTEMA`), `assistente/__main__.py` (elenco strumenti)
- Test: `tests/test_grafo.py`, `tests/test_main.py`

**Interfaces:**
- Consumes: `crea_strumenti_calendario(fuso, adesso)` (Task 1).
- Produces: elenco all'avvio `["ora_corrente", "giorni_tra", "sposta_data", "giorno_settimana", "pasqua", "converti", "calcola"]`, con `crea_strumenti_calendario(config.fuso)`.

- [ ] **Step 1: scrivere i test che falliscono**
  - `tests/test_grafo.py::test_il_prompt_chiede_gli_strumenti_del_calendario`: `PROMPT_DI_SISTEMA` contiene `"giorni_tra"`, `"sposta_data"`, `"giorno_settimana"`, `"pasqua"`, `"AAAA-MM-GG"`; restano `"chiama lo strumento converti"`, `"chiama lo strumento calcola"`, `"chiama sempre lo strumento ora_corrente"`.
  - `tests/test_grafo.py::test_percorso_con_il_calendario(caplog)`: strumenti di `crea_strumenti_calendario(ZoneInfo("Europe/Rome"), adesso=<3/11/2026 10:00 UTC>)`; `ModelloFinto` chiede `giorni_tra` `{"data": "12-25"}` id `"d1"`, poi `AIMessage("Mancano 52 giorni.")`; `ToolMessage` con `tool_call_id == "d1"`, `status == "success"`, contenuto che termina con `"mancano 52 giorni"`; in `caplog.messages` una riga che inizia con `"nodo_strumenti: giorni_tra -> "`.
  - `tests/test_grafo.py::test_errori_del_calendario_diventano_tool_message_d_errore` (parametrizzato): `("pasqua", {"anno": 1500}, "1583")`, `("giorni_tra", {"data": "2026-02-30"}, "non valida")`, `("sposta_data", {"giorni": 2.5}, "giorni")` → `status == "error"`, contenuto che inizia con `"Errore: "` e contiene il testo atteso.
  - `tests/test_main.py`: l'atteso dell'elenco diventa `["ora_corrente", "giorni_tra", "sposta_data", "giorno_settimana", "pasqua", "converti", "calcola"]`.

- [ ] **Step 2: eseguire e vedere fallire**
  Run: `.\.venv\Scripts\python.exe -m pytest tests/test_grafo.py tests/test_main.py -q` → falliscono il test del prompt e quello dell'elenco.

- [ ] **Step 3: implementare**
  - Prompt: una frase in fondo, per esempio «Per giorni mancanti o trascorsi fino a una data o tra due date chiama giorni_tra, per la data tra N giorni o N giorni fa chiama sposta_data, per il giorno della settimana di una data chiama giorno_settimana e per la data di Pasqua chiama pasqua, passando le date come AAAA-MM-GG oppure MM-GG se l'anno non è indicato; non calcolare da te, usa il risultato così com'è e, se lo strumento restituisce un errore, di' che non si può fare e perché.» Non toccare le frasi esistenti.
  - `__main__.py`: `strumenti = [crea_strumento_orologio(config.fuso), *crea_strumenti_calendario(config.fuso), crea_strumento_convertitore(), *strumenti_mcp]`; import in ordine alfabetico.

- [ ] **Step 4: eseguire e vedere passare**
  Run: `.\.venv\Scripts\python.exe -m pytest -q` → tutto verde.

- [ ] **Step 5: commit**
  `git add assistente/grafo.py assistente/__main__.py tests/test_grafo.py tests/test_main.py`; messaggio `feat(grafo): collega gli strumenti del calendario e aggiunge la regola nel prompt`.

### Task 3: prove reali, Docker e documentazione

**Files:**
- Modify: `tests/test_reale.py`, `README.md`, `CLAUDE.md`

**Interfaces:**
- Consumes: `crea_strumenti_calendario` (Task 1), prompt e avvio (Task 2).

- [ ] **Step 1: prove reali** in `tests/test_reale.py`: la fixture `grafo` usa lo stesso elenco di `main`; nuovi test
  - `test_reale_giorni_al_25_dicembre`: oggi reale `datetime.now(config.fuso).date()` (la fixture deve esporre `config.fuso`, per esempio con una seconda fixture `config` di modulo); atteso `n = (leggi_data("12-25", oggi) - oggi).days`; `esegui_turno(grafo, [], "Quanti giorni mancano al 25 dicembre?")`; un `ToolMessage` `giorni_tra` che termina con `f"mancano {n} giorni"` (o `"è oggi"` se `n == 0`) e `str(n)` nella risposta finale.
  - `test_reale_pasqua_2027`: `"Che giorno è Pasqua nel 2027?"`; un `ToolMessage` `pasqua` uguale a `"Pasqua 2027: domenica 28 marzo 2027"` e `"28 marzo"` nella risposta finale.

- [ ] **Step 2: eseguire le prove reali** (LM Studio acceso con `google/gemma-4-e4b`)
  Run: `.\.venv\Scripts\python.exe -m pytest -m reale -v` → 9 passati. Se una prova fallisce per scelta del modello, ritoccare solo descrizioni o regola nel prompt (con i test automatici aggiornati) e ripetere; non indebolire le asserzioni senza chiedere all'utente.

- [ ] **Step 3: prove da pipe** in una PowerShell pulita, `LOG_LEVEL=INFO`, locale e Docker (`docker compose build`, poi `docker compose run --rm -T -e LOG_LEVEL=INFO assistente`), con «Quanti giorni mancano al 25 dicembre?» e «Che giorno è Pasqua nel 2027?» → nel log `richiesta strumento giorni_tra` / `pasqua` e i risultati; risposte con il numero e con 28 marzo.

- [ ] **Step 4: documentazione**
  - README: introduzione (strumenti del calendario); sezione «Giorni e scadenze (funzione nel grafo)» dopo «Convertitore», con le quattro funzioni, i formati delle date, la regola della data senza anno, gli errori, la motivazione della modalità e il log reale della prova; «Test» con le nuove prove reali (nove, tempo misurato) e `tests/test_calendario.py`; una voce in «Diagnosi». Solo comandi eseguiti in questo task.
  - `CLAUDE.md` (progetto), sezione Struttura: riga `calendario.py: strumenti giorni_tra, sposta_data, giorno_settimana, pasqua (oggi dal fuso configurato, istante iniettabile)`.
  - Specifica: correggere gli esempi della tabella degli strumenti (oggi è martedì 3 novembre 2026, non lunedì; `30` → «giovedì 3 dicembre 2026», `-10` → «sabato 24 ottobre 2026»: la specifica riportava giorni della settimana sbagliati).

- [ ] **Step 5: verifica e commit**
  Run: `.\.venv\Scripts\python.exe -m pytest -q` → tutto verde. Commit `test(reale): aggiunge le prove reali del calendario` (`tests/test_reale.py`) e `docs: documenta giorni e scadenze nel README e nel CLAUDE.md` (`README.md`, `CLAUDE.md`, la specifica).

### Dopo i task
Una revisione finale dell'intero branch con un subagente `opus` (`git diff b3b2eb3..HEAD`), correzione di ciò che è Critical o Important con test RED→GREEN, resoconto all'utente. Merge in `dev` solo su sua richiesta.
