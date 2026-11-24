# Convertitore di unità nel grafo — specifica di design (Lezione 5, feature 2)

> Stato: approvata dall'utente il 03/11/2026, al termine del brainstorming con Superpowers. Branch `feature/convertitore`, nato da
> `dev` (`5d971fc`, con la calcolatrice MCP già integrata).
> Parte dalle specifiche precedenti (`2026-10-26-assistente-laboratorio-design.md`,
> `2026-11-03-calcolatrice-mcp-design.md`): tutto ciò che qui non è detto resta com'è là.

## Intento e perché
In laboratorio capita di chiedere conversioni rapide, con parole proprie: «quanti metri sono 2 centimetri?»,
«quanti km sono 25 metri?», «quanti gradi Fahrenheit sono 20 °C?». Il modello locale non deve fare il conto a
mente (sbaglia facilmente fattori e cifre): chiede uno strumento `converti`, il programma fa il calcolo e il
modello riporta il risultato in una frase sua, per esempio «25 metri sono 0,025 km».

È la seconda delle sei feature della Lezione 5, nella modalità **funzione Python nel grafo**, come l'orologio.
Il **ciclo del grafo non cambia**: richiesta del modello → esecuzione → `ToolMessage` correlato → nuova chiamata
al modello.

### Perché la funzione nel grafo (e non API o MCP)
La conversione è un calcolo puro e locale: nessun dato esterno, nessuno stato da conservare, nessun processo da
condividere con altri programmi. Un server (FastAPI o MCP) aggiungerebbe un processo, una dipendenza e un punto
di guasto senza alcun vantaggio; la funzione nel grafo è la soluzione più semplice e la più veloce in risposta.

## Obiettivi (criteri di riuscita)
1. Una domanda di conversione produce una richiesta strutturata di `converti`, l'esecuzione nel programma e un
   `ToolMessage` con il `tool_call_id` della richiesta; la risposta usa il risultato. Tutto visibile nei log
   (`nodo_strumenti: converti -> ...`, già prodotto dal grafo).
2. Le conversioni dell'elenco qui sotto sono esatte (fattori definiti, nessun valore approssimato a mano) e il
   risultato è formattato come concordato.
3. Una richiesta impossibile produce un `ToolMessage` d'errore (`status="error"`) con la spiegazione in italiano;
   il modello dice che non si può fare e perché, senza inventare un numero.
4. Nulla si rompe: cronologia, limite dei passaggi, orologio, calcolatrice MCP, `/log`, scritta «Ragionando...»
   invariati; tutti i test automatici esistenti ancora verdi.
5. Avvio locale e con Docker Compose; README e `CLAUDE.md` aggiornati con soli comandi verificati (PowerShell).

## Non-obiettivi
Altre grandezze (volumi, aree, velocità, tempo, pressione, energia, valute…); altre unità oltre all'elenco
(iarde, pinte, stone, Rankine…); conversioni composte («5 piedi e 3 pollici»); più conversioni in una sola
chiamata dello strumento; precisione o arrotondamento scelti dall'utente; nuove variabili d'ambiente o
dipendenze; workflow e RAG.

## Anti-obiettivi (fallimento anche se “funziona”)
- Un numero restituito quando la conversione non ha senso (grandezze diverse, unità sconosciuta, temperatura
  sotto lo zero assoluto, peso o lunghezza negativi): falso successo.
- Una risposta di conversione senza traccia della chiamata a `converti` nei log, o test simulati presentati come
  prova che il modello locale usa lo strumento.
- Il modello che, con la nuova regola nel prompt, smette di usare `calcola` per i calcoli o `ora_corrente` per
  l'ora.
- Messaggi d'errore in inglese o tecnici (traccia di validazione pydantic) restituiti al modello.

## Vincoli (da CLAUDE.md)
Codice sincrono, moduli piccoli. Nel pacchetto `assistente/` non si importano direttamente `openai`, `httpx` né
`pydantic` (eccezione: i tipi di `langchain_core`). Nessuna dipendenza nuova. Lavoro solo in
`assistente-laboratorio/`, sul branch `feature/convertitore`; Conventional Commits in italiano, staging
selettivo; merge e push solo su richiesta dell'utente. Test automatici senza modello separati dalle prove reali;
le prove da pipe senza `PYTHONIOENCODING`, in una PowerShell pulita.

## Decisioni prese con l'utente (03/11/2026)
- **Grandezze e unità**, elenco completo:
  - lunghezze: mm, cm, m, km, pollici, piedi, miglia;
  - pesi: mg, g, kg, tonnellate, libbre, once;
  - temperature: °C, °F, K.
- **Formato della risposta**: «25 metri sono 0,025 km», cioè con la **virgola decimale** all'italiana.
- **Errori**: quando la conversione non si può fare, l'assistente lo dice e spiega perché.
- **Modalità**: funzione Python nel grafo (dal piano della Lezione 5); l'utente ha approvato la proposta.

## Proposte dell'assistente accettate dall'utente
- **Firma**: `converti(valore, da, a)`; `valore` numero, `da` e `a` testi con l'unità.
- **Risultato**: un testo breve, già con la virgola, del tipo `25 m = 0,025 km` o `20 °C = 68 °F`, che il modello
  riformula nella sua frase.
- **Arrotondamento**: 6 cifre significative, senza zeri finali inutili (1 lb = 0,453592 kg; 1 mi = 1609,34 m).
- **Nomi delle unità**: simbolo oppure nome italiano, singolare o plurale, senza distinguere maiuscole e
  minuscole (`cm`, `centimetri`; `°F`, `Fahrenheit`; `lb`, `libbre`).
- **Pesi e lunghezze negativi**: errore, perché non hanno significato fisico.
- **Errori** come `ToolException`, che il grafo esistente trasforma in `ToolMessage` con `status="error"`.
- **Verifiche**: test automatici completi senza modello; prove reali con gemma per «quanti metri sono 4 cm?»
  (0,04) e «quanti °F sono 20 °C?» (68); prova Docker da pipe.

## Comportamento

### Unità riconosciute
Il confronto avviene dopo `strip()` e senza distinguere maiuscole e minuscole. Simbolo usato nel risultato in
grassetto.

| Grandezza | Unità (simbolo) | Fattore verso l'unità base | Nomi accettati (oltre al simbolo) |
|---|---|---|---|
| lunghezza | **mm** | 0,001 m | millimetro, millimetri |
| lunghezza | **cm** | 0,01 m | centimetro, centimetri |
| lunghezza | **m** (base) | 1 | metro, metri |
| lunghezza | **km** | 1000 m | chilometro, chilometri |
| lunghezza | **in** | 0,0254 m | pollice, pollici |
| lunghezza | **ft** | 0,3048 m | piede, piedi |
| lunghezza | **mi** | 1609,344 m | miglio, miglia |
| peso | **mg** | 0,000001 kg | milligrammo, milligrammi |
| peso | **g** | 0,001 kg | grammo, grammi |
| peso | **kg** (base) | 1 | chilogrammo, chilogrammi, chilo, chili |
| peso | **t** | 1000 kg | tonnellata, tonnellate |
| peso | **lb** | 0,45359237 kg | libbra, libbre |
| peso | **oz** | 0,028349523125 kg | oncia, once |
| temperatura | **°C** | formula | c, celsius, gradi celsius |
| temperatura | **°F** | formula | f, fahrenheit, gradi fahrenheit |
| temperatura | **K** | formula | kelvin |

Le temperature passano dal kelvin: K = °C + 273,15; °C = (°F − 32) × 5/9.

### Risultato
- Testo `<valore> <simbolo da> = <risultato> <simbolo a>`, per esempio `2 cm = 0,02 m`, `20 °C = 68 °F`,
  `0 °C = 273,15 K`.
- Risultato: 6 cifre significative. Valore e risultato: notazione decimale ordinaria (mai esponenziale), virgola
  decimale, nessun separatore delle migliaia, nessuno zero finale inutile, mai `-0`.
- *(scelta dell'assistente)* Il valore di partenza si riporta com'è, senza arrotondarlo (1234567 m resta
  `1234567 m`): arrotondare quello che l'utente ha scritto lo confonderebbe.
- Stessa unità in `da` e `a`: consentito, il risultato è il valore stesso (arrotondato come ogni risultato).
- *(scelta dell'assistente)* `valore` è un `float` nella firma; i controlli (finito, non negativo, non sotto lo
  zero assoluto) valgono sul valore ricevuto, prima di qualsiasi arrotondamento. Nessuna lettura di testi con la
  virgola (`"2,5"`): il modello passa un numero JSON.
- *(scelta dell'assistente)* Il confronto senza maiuscole rende equivalenti `K`/`k`, `mm`/`Mm`, `mg`/`Mg`: va
  bene, perché nell'elenco non ci sono unità che si distinguono solo per le maiuscole.

### Errori (ToolException, messaggio in italiano)
| Caso | Esempio | Messaggio (contenuto atteso) |
|---|---|---|
| grandezze diverse | 5 kg → m | non si può convertire un peso in una lunghezza |
| unità sconosciuta | 10 m → iarde | unità non supportata «iarde», con l'elenco delle unità disponibili |
| sotto lo zero assoluto | −300 °C → K | temperatura impossibile: sotto lo zero assoluto (−273,15 °C) |
| peso o lunghezza negativi | −5 kg → g | un peso (o una lunghezza) non può essere negativo |
| valore non numerico o non finito | «tanti» → m, `inf`, `nan` | il valore deve essere un numero, in italiano (niente testo pydantic) |

Lo zero assoluto esatto (0 K, −273,15 °C, −459,67 °F) è valido.

### Prompt di sistema
Si aggiunge una regola: per ogni conversione tra unità di lunghezza, peso o temperatura chiamare `converti`
invece di calcolare da sé (né con `calcola`), usare il risultato così com'è e, se lo strumento restituisce un
errore, dire che non si può fare e perché. Le regole esistenti restano.

## Verifiche
- **Test automatici senza modello**: ogni unità almeno una volta, conversioni di andata e ritorno, temperature
  (20 °C → 68 °F, 0 °C → 273,15 K, −40 °C = −40 °F), arrotondamento e formato (virgola, niente esponenziale,
  niente `-0`), nomi e maiuscole, tutti gli errori della tabella; giro completo nel grafo con un modello simulato
  (richiesta di `converti` → `ToolMessage` correlato, anche con `status="error"`).
- **Prove reali con gemma** (marcatore `reale`): «quanti metri sono 4 cm?» → chiamata a `converti` e risposta
  con 0,04; «quanti °F sono 20 °C?» → chiamata a `converti` e risposta con 68.
- **Docker**: build e una prova da pipe con una conversione.

## Lasciato a chi costruisce
- Nome e collocazione del modulo (proposta: `assistente/convertitore.py` con `crea_strumento_convertitore()`,
  collegato in `__main__.py` accanto all'orologio).
- Testo esatto della descrizione dello strumento, dei suoi parametri e della regola nel prompt.
- Come gestire la validazione degli argomenti (`handle_validation_error` o equivalente), purché il messaggio sia
  in italiano.
- Testo esatto dei messaggi d'errore, purché dicano il perché come nella tabella.
