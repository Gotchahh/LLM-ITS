# Giorni e scadenze nel grafo — specifica di design (Lezione 5, feature 3)

> Stato: approvata dall'utente il 03/11/2026, al termine del brainstorming con Superpowers. Branch `feature/giorni-scadenze`, nato da
> `dev` (`b3b2eb3`, con calcolatrice MCP e convertitore già integrati).
> Parte dalle specifiche precedenti (`2026-10-26-assistente-laboratorio-design.md`,
> `2026-11-03-calcolatrice-mcp-design.md`, `2026-11-03-convertitore-design.md`): tutto ciò che qui non è detto
> resta com'è là.

## Intento e perché
In laboratorio capita di chiedere all'assistente cose come «quanti giorni mancano al 25 dicembre?» o «che giorno
è Pasqua il prossimo anno?». Il modello locale sbaglia facilmente i conti sul calendario (mesi di lunghezza
diversa, anni bisestili, Pasqua mobile) e non sa che giorno è oggi: chiede uno strumento, il programma fa il
calcolo e il modello risponde con una frase sua.

È la terza delle sei feature della Lezione 5, nella modalità **funzione Python nel grafo**, come l'orologio e il
convertitore. Il **ciclo del grafo non cambia**: richiesta del modello → esecuzione → `ToolMessage` correlato →
nuova chiamata al modello.

### Perché la funzione nel grafo (e non API o MCP)
Sono calcoli puri sul calendario, più la data di oggi che il programma ha già (lo stesso orologio di
`ora_corrente`): nessun dato esterno, nessuno stato da conservare, nessun processo da condividere. Un server
aggiungerebbe un processo, una dipendenza e un punto di guasto senza vantaggi.

## Obiettivi (criteri di riuscita)
1. Ognuna delle cinque domande qui sotto produce una richiesta strutturata dello strumento giusto, l'esecuzione
   nel programma e un `ToolMessage` con il `tool_call_id` della richiesta; la risposta usa il risultato. Tutto
   visibile nei log (`nodo_strumenti: <strumento> -> ...`, già prodotto dal grafo).
2. I risultati sono esatti (anni bisestili, cambi di mese e d'anno, Pasqua) e la data di oggi viene dal fuso
   configurato.
3. Una richiesta impossibile produce un `ToolMessage` d'errore (`status="error"`) con la spiegazione in italiano;
   il modello dice che non si può fare e perché, senza inventare una data o un numero.
4. Nulla si rompe: cronologia, limite dei passaggi, orologio, convertitore, calcolatrice MCP, `/log`, scritta
   «Ragionando...» invariati; tutti i test automatici esistenti ancora verdi.
5. Avvio locale e con Docker Compose; README e `CLAUDE.md` aggiornati con soli comandi verificati (PowerShell).

## Non-obiettivi
Giorni lavorativi, festività (oltre a Pasqua), ponti; Pasquetta, Pasqua ortodossa o altre feste mobili; ore e
minuti (restano a `ora_corrente`); calendari diversi dal gregoriano (giuliano per le date antiche); fusi orari
diversi da quello configurato per il calcolo di «oggi»; date scritte in formati diversi da quelli concordati
(il modello le converte); promemoria o scadenze salvate (nessuna persistenza: le note sono un'altra feature);
nuove variabili d'ambiente o dipendenze; workflow e RAG.

## Anti-obiettivi (fallimento anche se “funziona”)
- Una data o un numero restituiti quando la richiesta non ha senso (data inesistente, anno fuori intervallo,
  Pasqua prima del 1583): falso successo.
- Un conteggio basato su una data di oggi diversa da quella dell'orologio dell'assistente (per esempio UTC invece
  di `APP_TIMEZONE` vicino alla mezzanotte).
- Una risposta sul calendario senza traccia della chiamata allo strumento nei log, o test simulati presentati come
  prova che il modello locale usa lo strumento.
- La nuova regola nel prompt che fa smettere al modello di usare `ora_corrente`, `converti` o `calcola`.
- Messaggi d'errore in inglese o tecnici (traccia di validazione pydantic) restituiti al modello.

## Vincoli (da CLAUDE.md)
Codice sincrono, moduli piccoli. Nel pacchetto `assistente/` non si importano direttamente `openai`, `httpx` né
`pydantic` (eccezione: i tipi di `langchain_core`). Nessuna dipendenza nuova. Lavoro solo in
`assistente-laboratorio/`, sul branch `feature/giorni-scadenze`; Conventional Commits in italiano, staging
selettivo; merge e push solo su richiesta dell'utente. Test automatici senza modello (istante controllato)
separati dalle prove reali; le prove da pipe senza `PYTHONIOENCODING`, in una PowerShell pulita.

## Decisioni prese con l'utente (03/11/2026)
- **Domande coperte** (elenco completo):
  1. quanti giorni mancano a una data (o quanti ne sono passati);
  2. quanti giorni ci sono tra due date;
  3. che data sarà tra N giorni (o era N giorni fa);
  4. che giorno della settimana è (o era) una data;
  5. in che giorno cade Pasqua in un certo anno.
- **Data senza anno**: si usa la **prossima** occorrenza; se il 25 dicembre è già passato, si conta fino al
  25 dicembre dell'anno dopo.
- **Errori**: quando non si può fare, l'assistente lo dice e spiega perché.
- **Modalità**: funzione Python nel grafo (dal piano della Lezione 5); l'utente ha approvato la proposta.

## Proposte dell'assistente accettate dall'utente
- **Oggi** viene dallo stesso orologio di `ora_corrente`, nel fuso `APP_TIMEZONE`, con istante iniettabile nei
  test.
- **Quattro strumenti piccoli** invece di uno grande con molte opzioni (un modello piccolo sceglie meglio tra
  strumenti semplici): `giorni_tra`, `sposta_data`, `giorno_settimana`, `pasqua`.
- **Formato delle date in ingresso**: `AAAA-MM-GG` (per esempio `2026-12-25`) oppure `MM-GG` (per esempio `12-25`)
  quando l'anno non c'è.
- **Formato del risultato**: date per esteso in italiano, con il giorno della settimana, per esempio
  «venerdì 25 dicembre 2026 – mancano 52 giorni».
- **Pasqua**: quella cattolica (occidentale), calcolata sul calendario gregoriano, dal 1583 in poi.
- **«Tra due date»**: semplice differenza; dal 10 al 12 marzo sono 2 giorni.
- **29 febbraio senza anno**: il prossimo anno bisestile che lo contiene.
- **Data passata con anno**: si conta comunque, «sono passati N giorni».
- **Date antiche** (per esempio 14 luglio 1789): calendario gregoriano anche prima del 1582, come fa Python.
- **Errori** come `ToolException`, che il grafo esistente trasforma in `ToolMessage` con `status="error"`.
- **Verifiche**: test automatici con oggi fissato; prove reali con gemma per «Quanti giorni mancano al 25
  dicembre?» (numero confrontato con quello calcolato sulla data reale) e «Che giorno è Pasqua nel 2027?»
  (28 marzo); prova Docker da pipe.

## Comportamento

### Date in ingresso
- `AAAA-MM-GG`: quella data. `MM-GG`: la prossima occorrenza a partire da oggi, **oggi compreso** *(scelta
  dell'assistente: il 25 dicembre, «quanti giorni mancano al 25 dicembre» dà «è oggi», non 365)*.
- Spazi iniziali e finali ignorati. Qualsiasi altro testo è un errore che mostra i due formati ammessi.
- Anni ammessi: da 1 a 9999 (limite di `datetime.date`).

### Strumenti
I nomi dei parametri sono indicativi; i testi esatti dei risultati sono lasciati a chi costruisce, purché
contengano le informazioni indicate.

| Strumento | Parametri | Risultato (esempio con oggi = lunedì 3 novembre 2026) |
|---|---|---|
| `giorni_tra` | `data` (arrivo), `partenza` facoltativa (oggi se manca) | `12-25` → «da lunedì 3 novembre 2026 a venerdì 25 dicembre 2026: mancano 52 giorni»; data passata → «sono passati N giorni»; stessa data → «è oggi» (o «0 giorni» con partenza esplicita) |
| `sposta_data` | `giorni` (intero, negativo per il passato), `data` di partenza facoltativa (oggi se manca) | `30` → «tra 30 giorni: mercoledì 3 dicembre 2026»; `-10` → «10 giorni prima: venerdì 24 ottobre 2026» |
| `giorno_settimana` | `data` | `1789-07-14` → «martedì 14 luglio 1789» |
| `pasqua` | `anno` facoltativo (anno corrente se manca) | `2027` → «Pasqua 2027: domenica 28 marzo 2027» |

*(scelta dell'assistente)* In `giorni_tra` con due date senza anno, ciascuna è la propria prossima occorrenza da
oggi; se così l'arrivo cade prima della partenza, il risultato è «sono passati N giorni» come per le date con
anno. Il caso è raro (il modello di solito scrive l'anno) e resta coerente con la regola concordata. Lo stesso
vale se una sola delle due date è senza anno: ognuna si risolve da sola.

*(scelte dell'assistente)*
- `pasqua` senza anno dà la Pasqua dell'anno corrente anche se è già passata; per «la prossima Pasqua» il modello
  passa l'anno.
- `giorni` deve essere un intero: un numero con la parte decimale (`2.5`) è un errore che spiega il parametro.
- Qualsiasi risultato fuori dall'intervallo 1–9999 (per esempio `sposta_data` oltre l'anno 9999 o prima
  dell'anno 1) dà l'errore «anno fuori dall'intervallo 1–9999».

### Errori (ToolException, messaggio in italiano)
| Caso | Esempio | Messaggio (contenuto atteso) |
|---|---|---|
| data inesistente | `2026-02-30`, `2026-13-01`, `02-30` | data non valida, con la data ricevuta |
| formato non riconosciuto | `25 dicembre`, `25/12/2026` | formato non riconosciuto, con i formati ammessi `2026-12-25` o `12-25` |
| anno fuori intervallo | `pasqua(0)`, `sposta_data(10**7)` | anno fuori dall'intervallo 1–9999 |
| Pasqua prima del 1583 | `pasqua(1500)` | calcolo affidabile solo dal 1583 (calendario gregoriano) |
| argomenti mancanti o del tipo sbagliato | `giorni="tanti"` | spiegazione dei parametri in italiano (niente testo pydantic) |

### Prompt di sistema
Si aggiunge una regola: per giorni mancanti o trascorsi, differenze tra date, date future o passate, giorno della
settimana di una data e data di Pasqua chiamare lo strumento adatto invece di calcolare da sé, passando le date
come `AAAA-MM-GG` o `MM-GG`; usare il risultato così com'è e, se lo strumento restituisce un errore, dire che non
si può fare e perché. Le regole esistenti restano; per l'ora attuale resta `ora_corrente`.

## Verifiche
- **Test automatici senza modello**, con oggi fissato: ogni strumento; cambio di mese e d'anno; anni bisestili
  (29 febbraio con e senza anno); data senza anno già passata, futura e uguale a oggi; date passate con anno;
  Pasqua di anni noti (2024 → 31 marzo, 2025 → 20 aprile, 2026 → 5 aprile, 2027 → 28 marzo, 2038 → 25 aprile,
  1583 → 10 aprile); oggi calcolato nel fuso configurato vicino alla mezzanotte; tutti gli errori della tabella;
  giro completo nel grafo con un modello simulato (successo ed errore).
- **Prove reali con gemma** (marcatore `reale`): «Quanti giorni mancano al 25 dicembre?» → chiamata a
  `giorni_tra` e numero uguale a quello calcolato sulla data reale di oggi; «Che giorno è Pasqua nel 2027?» →
  chiamata a `pasqua` e risposta con 28 marzo.
- **Docker**: build e una prova da pipe.

## Lasciato a chi costruisce
- Nome e collocazione del modulo (proposta: `assistente/calendario.py` con
  `crea_strumenti_calendario(fuso, adesso) -> list[BaseTool]`, collegato in `__main__.py` accanto all'orologio,
  riusando i nomi dei giorni di `assistente/strumenti.py`).
- Algoritmo di Pasqua (per esempio quello anonimo gregoriano, «Meeus/Jones/Butcher»).
- Testo esatto delle descrizioni, dei risultati, dei messaggi d'errore e della regola nel prompt.
