# Assistente del laboratorio

Applicazione da terminale in Python costruita attorno a un grafo LangGraph esplicito.
Il grafo inoltra la conversazione al modello locale servito da LM Studio e conserva la
cronologia per la durata della sessione (nessuna persistenza). Il modello può chiedere lo
strumento orologio `ora_corrente`, i quattro strumenti del calendario `giorni_tra`, `sposta_data`,
`giorno_settimana` e `pasqua` (vedi «Giorni e scadenze»), il convertitore di unità `converti` (vedi «Convertitore») e lo strumento
`calcola` della calcolatrice, offerto da un server MCP (vedi «Calcolatrice»), e gli strumenti delle note
`salva_nota`, `elenca_note` e `cancella_nota`, offerti da un'API FastAPI (vedi «Note»); il programma li esegue davvero.

I comandi sono per PowerShell (Windows) e vanno eseguiti dalla cartella `assistente-laboratorio/`.
Gli esempi di output riportati sono di esecuzioni reali: le chat e i log dello strumento orologio, anche
in Docker, sono del 28/10/2026; il confronto tra gli orologi, i casi con `docker compose up`/`down` e con `.env`
mancante sono del 02/11/2026; riprovati lo stesso giorno, con lo stesso esito, anche i messaggi d'errore della
Diagnosi (server o modello assenti, `Connection refused` dal container) e `Get-NetTCPConnection`. Le prove della calcolatrice e del convertitore, in locale e in Docker, sono del 03/11/2026; quelle di giorni e scadenze e delle note del 09/11/2026. Orari e offset (per esempio `-04:00`, EDT) cambiano con la data.

## Requisiti

- Python 3.14.7 (avviabile con `py -3.14`)
- LM Studio con il server locale avviato e un modello caricato che supporti il tool calling (per esempio
  `google/gemma-4-e4b`); resta sul computer host, anche con Docker
- Docker Desktop, solo per l'avvio con Docker Compose (vedi «Avvio con Docker Compose»)

## Installazione

Creare l'ambiente virtuale e installare le dipendenze (versioni fissate in `requirements.txt`
e `requirements-dev.txt`):

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
```

`pip check` deve rispondere `No broken requirements found.`

Si usa direttamente `.\.venv\Scripts\python.exe`, senza attivare l'ambiente
(`Activate.ps1` può essere bloccato dalla policy di esecuzione di PowerShell).

## Configurazione

La configurazione arriva da variabili d'ambiente, senza credenziali. Si parte dal file di esempio
(il file `.env` reale è escluso da Git):

```powershell
Copy-Item .env.example .env
```

Se `.env` esiste già il comando lo sovrascrive: in quel caso modificare il file a mano.

| Variabile | Esempio | Significato |
|---|---|---|
| `LMSTUDIO_BASE_URL` | `http://localhost:1234/v1` | Indirizzo dell'API di LM Studio, con lo schema (`http://`); una barra finale viene tolta |
| `LMSTUDIO_MODEL` | `google/gemma-4-e4b` | Identificativo del modello, uguale a quello restituito da `GET /v1/models` |
| `APP_TIMEZONE` | `Europe/Rome` | Fuso orario IANA per lo strumento orologio |
| `LOG_LEVEL` | `INFO` | Facoltativa (default `INFO`), maiuscole o minuscole |
| `NOTE_API_URL` | `http://localhost:8000` | Facoltativa (default `http://localhost:8000`): indirizzo del servizio delle note |

Le prime tre sono obbligatorie: se mancano o sono vuote, l'errore le elenca e rimanda a `.env.example`.

Le due modalità di log:

- visibili (`LOG_LEVEL=INFO`, oppure `DEBUG` per più dettagli): i passaggi dell'applicazione compaiono su
  stderr nel formato `[INFO] messaggio`;
- nascosti (`LOG_LEVEL=WARNING`, oppure `ERROR`): solo il dialogo, più eventuali avvisi ed errori. Solo nella
  chat interattiva da tastiera, durante l'attesa del modello compare `Ragionando...`, che sparisce all'arrivo
  della risposta; con l'input da pipe, o con i log visibili, non compare.

`LOG_LEVEL` sceglie la modalità iniziale. Durante la chat il comando `/log` passa dall'una all'altra per la
sessione in corso, senza modificare `.env`: alla sessione successiva si riparte da `LOG_LEVEL`. Da `DEBUG` o
`INFO` i log si nascondono (livello `WARNING`) e un secondo `/log` riporta il livello iniziale; da `WARNING` o
`ERROR` si mostrano (livello `INFO`) e un secondo `/log` riporta il livello iniziale. La scritta `Ragionando...`
segue il cambio: compare dalla domanda successiva a un `/log` che nasconde i log e sparisce dopo uno che li mostra.

Solo i log dell'applicazione seguono `LOG_LEVEL` e `/log`; quelli delle librerie esterne restano a `WARNING`.

Per leggere l'identificativo del modello dal server (LM Studio deve essere in esecuzione):

```powershell
Invoke-RestMethod http://localhost:1234/v1/models
```

La risposta contiene l'elenco `data`, con un campo `id` per ogni modello disponibile: quello scelto va copiato in
`LMSTUDIO_MODEL`. Per stampare solo gli identificativi:

```powershell
(Invoke-RestMethod http://localhost:1234/v1/models).data.id
```

All'avvio l'applicazione legge `.env` dalla cartella corrente; le variabili già impostate nell'ambiente
hanno la precedenza sul file.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Le prove che richiedono LM Studio attivo hanno il marcatore `reale` e sono escluse di default.
Si attivano esplicitamente (LM Studio con il server avviato, il modello caricato e `.env` compilato):

```powershell
.\.venv\Scripts\python.exe -m pytest -m reale -v
```

Sono dieci prove: una risposta ordinaria (senza strumento), il ricordo di un'informazione data nel turno
precedente, due domande sull'ora nella stessa sessione (almeno una richiesta di `ora_corrente` per turno: il modello può
chiamarla più volte nello stesso turno), l'ora
di New York (una richiesta di `ora_corrente` con il fuso `America/New_York`) e un calcolo («Quanto fa 12,5 per 8
meno 3?»: il risultato `97` deve venire dallo strumento `calcola` e comparire nella risposta) e due conversioni
(«Quanti metri sono 4 cm?» e «Quanti gradi Fahrenheit sono 20 °C?»: i risultati `4 cm = 0,04 m` e `20 °C = 68 °F`
devono venire dallo strumento `converti`, e `0,04` e `68` comparire nella risposta), i giorni che mancano al
25 dicembre (il risultato di `giorni_tra` deve coincidere con il numero calcolato sulla data reale di oggi, che deve
comparire nella risposta), la Pasqua del 2027 (`pasqua` deve restituire `Pasqua 2027: domenica 28 marzo 2027` e
la risposta contenere `28 marzo`) e le note («Segnati che il microscopio 2 va calibrato.» deve produrre un
`salva_nota` riuscito e, in una conversazione nuova, «Che note ho?» un `elenca_note` con la nota e la parola
`microscopio` nella risposta; il test avvia da sé il servizio su un DB temporaneo).
Con un modello locale possono richiedere diversi minuti (il 09/11/2026, con `google/gemma-4-e4b`, 412 s; ogni prova
fa più chiamate al modello e la prima carica il modello). Se il modello non chiama lo strumento la prova fallisce:
il fallimento va riportato, non aggirato.

I test delle note (senza modello) sono in `tests/test_note_api.py` (il servizio con il `TestClient` di FastAPI su un
DB temporaneo), `tests/test_note.py` (gli strumenti contro un vero uvicorn avviato dai test, anche spento) e in
`tests/test_grafo.py`.

I test di giorni e scadenze (senza modello, con oggi fissato al 03/11/2026) sono in `tests/test_calendario.py`
(lettura delle date, conteggi, anni bisestili, Pasqua, errori, oggi nel fuso configurato vicino alla mezzanotte) e
in `tests/test_grafo.py` (il giro nel grafo con un modello finto, anche con errore).

I test del convertitore (senza modello) sono in `tests/test_convertitore.py` (conversioni, formato, nomi delle
unità, errori) e in `tests/test_grafo.py` (il giro nel grafo con un modello finto, anche con errore).

I test della calcolatrice (tutti senza modello) sono in quattro file:

- `tests/test_calcolo.py`: la logica pura (risultati, formato dei numeri, errori, nessuna esecuzione di codice);
- `tests/test_server_mcp.py`: il server MCP avviato davvero su stdio (catalogo, invocazione, errori);
- `tests/test_client_mcp.py`: il client (strumenti sincroni, errori di validazione e di trasporto, Ctrl+C);
- `tests/test_integrazione_mcp.py`: il grafo con un modello finto e il server MCP vero.

I test che avviano il server sono più lenti degli altri (circa 2 s per ogni avvio). Per provare solo il server:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_server_mcp.py -v
```

## Avvio

LM Studio deve avere il server locale avviato e il modello di `LMSTUDIO_MODEL` disponibile. Dalla cartella
`assistente-laboratorio/`:

```powershell
.\.venv\Scripts\python.exe -m assistente
```

Si apre la chat interattiva: prompt `Tu> `, risposte `Assistente> `. Comandi: `/esci` (oppure Ctrl+C o fine
dell'input) per uscire; `/log` per mostrare o nascondere i log dell'applicazione (vedi sotto); una riga vuota
viene ignorata; un altro comando che inizia con `/` (anche `/log on`) mostra
`Comando sconosciuto. Comandi disponibili: /esci, /log` senza interrogare il modello. I comandi non
entrano nella cronologia e non distinguono maiuscole e spazi ai bordi (`/LOG`, ` /esci `).

All'avvio l'applicazione controlla che il server risponda e che `LMSTUDIO_MODEL` sia tra i modelli
restituiti da `/v1/models`; se non lo è, stampa su stderr l'errore con l'elenco dei modelli disponibili
ed esce con codice 1.

Gli esempi con l'ingresso da pipe usano lettere accentate, che Windows PowerShell 5.1 perde: il testo inviato a un
programma viene codificato con `$OutputEncoding`, che di default è ASCII, e «è» arriva al programma (e al modello)
come `?`. Il programma non può recuperarle. Prima delle prove da pipe si imposta UTF-8 senza BOM, in ingresso e in
uscita, nella finestra di PowerShell corrente (in una nuova finestra va ripetuto):

```powershell
$OutputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
```

Quando l'ingresso o l'uscita non sono un terminale (pipe, `<`, `>`) il programma legge e scrive in UTF-8 e ignora i
BOM iniziali. Con l'uscita rediretta un'emoji nella risposta del modello non interrompe più la sessione (prima
terminava con un `UnicodeEncodeError`). Con la tastiera e lo schermo il programma non cambia nulla.

Prova con tre righe in ingresso da pipe (due messaggi e il comando `/esci`):

```powershell
"Il mio colore preferito è il verde.`nQual è il mio colore preferito?`n/esci" | .\.venv\Scripts\python.exe -m assistente
```

Con l'ingresso da pipe il testo dell'utente non viene riscritto: dopo ogni `Tu> ` compare direttamente
l'output successivo. Con `LOG_LEVEL=INFO` i log di `nodo_llm` (su stderr) precedono ogni risposta:

```text
Tu> [INFO] nodo_llm: chiamata al modello (2 messaggi)
[INFO] nodo_llm: risposta ricevuta in ... s
Assistente> ...
Tu> [INFO] nodo_llm: chiamata al modello (4 messaggi)
[INFO] nodo_llm: risposta ricevuta in ... s
Assistente> ...
Tu> Alla prossima!
```

La seconda chiamata riceve 4 messaggi (sistema, domanda, risposta, nuova domanda): è la cronologia della
sessione. L'ultimo `Tu> ` è quello a cui risponde `/esci`, seguito da `Alla prossima!`. Con
`LOG_LEVEL=WARNING` restano solo i dialoghi: `Tu> Assistente> ...`.

Una riga vuota o di soli spazi viene ignorata senza interrogare il modello:

```powershell
"   `n/esci" | .\.venv\Scripts\python.exe -m assistente
```

stampa `Tu> Tu> Alla prossima!`. Dopo `chcp 65001` PowerShell antepone un BOM al testo della pipe: il programma lo
ignora e la riga resta vuota, con o senza la riga UTF-8 di sopra.

Per conservare il dialogo in un file si redirige lo stdout; i log (stderr) restano sullo schermo:

```powershell
"Il mio colore preferito è il verde.`nQual è il mio colore preferito?`n/esci" | .\.venv\Scripts\python.exe -m assistente > chat.txt
Get-Content chat.txt
```

`Get-Content` mostra `Tu> Assistente> ...` con accenti ed emoji intatti (il modello ne usa spesso); in PowerShell 5.1
`>` salva il file in UTF-16. Provato il 02/11/2026 con la console predefinita (`chcp 850`) e la riga UTF-8 di sopra.
Senza quella riga le lettere accentate di ingresso arrivano come `?` e quelle in uscita compaiono alterate
(`├¿` al posto di `è`): è la codifica di PowerShell, non del programma.

## Strumento orologio

Per le domande su ora, data o giorno attuali il modello chiede lo strumento `ora_corrente` e il programma lo
esegue. Senza argomenti lo strumento dà l'ora del fuso `APP_TIMEZONE`; con l'argomento facoltativo `fuso` (un nome
IANA, per esempio `America/New_York`) dà l'ora di un'altra località, calcolata dal programma e non dal modello.
Un fuso non valido (per esempio `New York`) non interrompe il turno: lo strumento restituisce un testo d'errore
con un esempio di nome corretto, che il modello può leggere e correggere. Prova con tre domande (la terza chiede
l'ora di un'altra città):

```powershell
"Che ore sono?`nChe giorno della settimana è oggi?`nChe ore sono a New York?`n/esci" | .\.venv\Scripts\python.exe -m assistente
```

Con `LOG_LEVEL=INFO` la chiamata allo strumento si riconosce nei log, su stderr, da queste due righe, che
precedono la risposta finale (qui per la prima domanda):

```text
[INFO] instradamento: richiesta strumento ora_corrente {}
[INFO] nodo_strumenti: ora_corrente -> mercoledì 2026-10-28T10:44:58+01:00 (Europe/Rome)
```

La prima è la richiesta strutturata del modello (nome e argomenti), la seconda il risultato dell'esecuzione,
che viene restituito al modello: segue una nuova `nodo_llm: chiamata al modello` con due messaggi in più
(la richiesta e il risultato) e infine `instradamento: nessuno strumento -> fine`. Una risposta sull'ora senza
queste due righe non proviene dallo strumento.

Per l'ora di un'altra città la richiesta contiene il fuso e il risultato porta l'offset di quella località
(qui `-04:00`, per la terza domanda):

```text
[INFO] instradamento: richiesta strumento ora_corrente {"fuso": "America/New_York"}
[INFO] nodo_strumenti: ora_corrente -> mercoledì 2026-10-28T05:45:49-04:00 (America/New_York)
```

Modalità silenziosa, con la variabile impostata solo per la sessione di PowerShell corrente:

```powershell
$env:LOG_LEVEL = "WARNING"
"Che ore sono?`nChe giorno della settimana è oggi?`nChe ore sono a New York?`n/esci" | .\.venv\Scripts\python.exe -m assistente
Remove-Item Env:LOG_LEVEL
```

Restano solo i dialoghi, senza righe `[INFO]`:

```text
Tu> Assistente> Sono le 10:46 di mercoledì 28 ottobre 2026, ora di Roma (CET).
Tu> Assistente> Oggi è mercoledì.
Tu> Assistente> A New York sono le 05:47 di mercoledì 28 ottobre 2026 (ora EDT).
Tu> Alla prossima!
```

Il grafo ammette al massimo 10 passaggi per turno: se il modello continua a chiedere strumenti la chat stampa
`Errore: limite di 10 passaggi raggiunto. Turno annullato.`, scarta il turno e prosegue.

## Giorni e scadenze (funzione nel grafo)

Per le domande sul calendario il modello ha quattro strumenti; il conto lo fa il programma, non il modello:

- `giorni_tra(data, partenza)`: giorni che mancano a `data` o che sono passati, da oggi o da `partenza`
  (`da lunedì 9 novembre 2026 a venerdì 25 dicembre 2026: mancano 46 giorni`; «è oggi» se la data è oggi);
- `sposta_data(giorni, data)`: la data tra N giorni (o N giorni fa, con N negativo), da oggi o da `data`
  (`tra 30 giorni: giovedì 3 dicembre 2026`, con oggi martedì 3 novembre 2026);
- `giorno_settimana(data)`: la data per esteso con il giorno della settimana (`martedì 14 luglio 1789`);
- `pasqua(anno)`: la Pasqua cattolica di un anno, dal 1583 (`Pasqua 2027: domenica 28 marzo 2027`); senza anno,
  quella dell'anno corrente.

Le date si passano come `AAAA-MM-GG` (`2026-12-25`) oppure `MM-GG` (`12-25`) quando l'anno non c'è: in questo caso
vale la **prossima** occorrenza, oggi compreso (il 29 febbraio senza anno è quello del prossimo anno bisestile).
«Oggi» è la data dell'orologio dell'assistente nel fuso `APP_TIMEZONE`, non quella UTC.

Quando la richiesta non ha senso lo strumento restituisce un errore in italiano, che il modello deve spiegare senza
inventare una data: data inesistente (`data non valida «2026-02-30»`), formato non riconosciuto (con i due formati
ammessi), anno fuori dall'intervallo 1–9999, Pasqua prima del 1583, argomenti mancanti o del tipo sbagliato (per
esempio `giorni` con i decimali).

Sono **funzioni Python del grafo** (`assistente/calendario.py`), come l'orologio e il convertitore: calcoli puri
sul calendario più la data di oggi, che il programma ha già; nessun dato esterno né stato, quindi un server
aggiungerebbe solo un processo e un punto di guasto. Prova reale da pipe del 09/11/2026 (`LOG_LEVEL=INFO`,
`google/gemma-4-e4b`; uguale in Docker):

```text
[INFO] instradamento: richiesta strumento giorni_tra {"data": "12-25"}
[INFO] nodo_strumenti: giorni_tra -> da lunedì 9 novembre 2026 a venerdì 25 dicembre 2026: mancano 46 giorni
[INFO] nodo_llm: chiamata al modello (4 messaggi)
[INFO] nodo_llm: risposta ricevuta in 15.5 s
[INFO] instradamento: nessuno strumento -> fine
Tu> Assistente> Mancano 46 giorni al 25 dicembre (venerdì 25 dicembre 2026).
[INFO] nodo_llm: chiamata al modello (6 messaggi)
[INFO] nodo_llm: risposta ricevuta in 10.6 s
[INFO] instradamento: richiesta strumento pasqua {"anno": 2027}
[INFO] nodo_strumenti: pasqua -> Pasqua 2027: domenica 28 marzo 2027
[INFO] nodo_llm: chiamata al modello (8 messaggi)
[INFO] nodo_llm: risposta ricevuta in 15.7 s
[INFO] instradamento: nessuno strumento -> fine
Tu> Assistente> Pasqua nel 2027 cade di domenica 28 marzo 2027.
```

## Note (API FastAPI)

Il modello può salvare, elencare e cancellare note con tre strumenti: `salva_nota(testo)`, `elenca_note(cerca)`
(`cerca` facoltativo, senza distinzione di maiuscole) e `cancella_nota(numero)`. Le note **restano** dopo la chiusura
dell'assistente; la cronologia della chat invece no. Le salva un servizio separato, `note_api/`: un'API FastAPI con
un file SQLite, che l'assistente chiama via HTTP con `urllib` (`assistente/note.py`).

Perché un'API e non una funzione nel grafo o MCP: le note sono dati con stato che appartengono a un servizio con un
proprio ciclo di vita (in Docker un container separato con il suo volume); un'API HTTP le rende disponibili a
qualsiasi client.

Avvio locale in **due terminali**. Nel primo il servizio (lasciarlo aperto; si ferma con Ctrl+C):

```powershell
.\.venv\Scripts\python.exe -m note_api
```

Nel secondo l'assistente, come in «Avvio». Variabili del servizio, tutte facoltative: `NOTE_DB` (file SQLite,
default `dati/note.db`, cartella creata se manca ed esclusa da Git), `NOTE_HOST` (default `127.0.0.1`),
`NOTE_PORT` (default `8000`). L'assistente trova il servizio con `NOTE_API_URL` (vedi «Configurazione»).

Endpoint (JSON): `GET /salute`; `POST /note` con `{"testo": "..."}` (da 1 a 500 caratteri, spazi esterni tolti);
`GET /note?cerca=...` (al massimo 20 note, dalla più recente, con il totale); `DELETE /note/{numero}`. Ogni errore ha
il corpo `{"errore": "<messaggio in italiano>"}` (`400` testo o numero non validi, `404` nota inesistente).

Errori che il modello riceve e deve spiegare senza inventare note: servizio spento (`servizio note non
raggiungibile a http://localhost:8000: avviarlo con python -m note_api`), nota inesistente (`nessuna nota con numero
3`), testo vuoto o troppo lungo. Se il servizio non risponde all'avvio, l'assistente parte comunque con un avviso.

Prova reale da pipe del 09/11/2026 (`LOG_LEVEL=INFO`, `google/gemma-4-e4b`), in tre sessioni separate: le prime due
con il servizio avviato su un DB di prova (`NOTE_DB`), la terza con il servizio spento:

```text
[INFO] instradamento: richiesta strumento salva_nota {"testo": "il microscopio 2 va calibrato"}
[INFO] nodo_strumenti: salva_nota -> nota 1 salvata: «il microscopio 2 va calibrato»
Tu> Assistente> Ho salvato la nota: "il microscopio 2 va calibrato".

[INFO] instradamento: richiesta strumento elenca_note {}
[INFO] nodo_strumenti: elenca_note -> 1 nota: n. 1 (9/11/2026 11:24) il microscopio 2 va calibrato
[INFO] instradamento: richiesta strumento cancella_nota {"numero": 1}
[INFO] nodo_strumenti: cancella_nota -> nota 1 cancellata: «il microscopio 2 va calibrato»
Tu> Assistente> Ho cancellato la nota n. 1 ("il microscopio 2 va calibrato").

[WARNING] servizio note non raggiungibile a http://localhost:8000: gli strumenti delle note risponderanno con un errore
[INFO] instradamento: richiesta strumento salva_nota {"testo": "la centrifuga fa rumore"}
[WARNING] nodo_strumenti: errore dello strumento salva_nota: servizio note non raggiungibile a http://localhost:8000: avviarlo con python -m note_api
Tu> Assistente> Mi dispiace, ma non è stato possibile salvare la nota perché il servizio delle note non risulta raggiungibile.
```

## Convertitore (funzione nel grafo)

Per le conversioni di unità il modello chiede lo strumento `converti`, con tre argomenti: `valore` (un numero),
`da` e `a` (le unità). Le unità ammesse sono:

- lunghezze: `mm`, `cm`, `m`, `km`, `in` (pollici), `ft` (piedi), `mi` (miglia);
- pesi: `mg`, `g`, `kg`, `t` (tonnellate), `lb` (libbre), `oz` (once);
- temperature: `°C`, `°F`, `K`.

Il modello può scrivere il simbolo o il nome italiano, al singolare o al plurale e senza badare alle maiuscole
(`centimetri`, `Fahrenheit`, `libbre`). Lo strumento restituisce un testo come `25 m = 0,025 km`: il valore di
partenza com'è, il risultato arrotondato a 6 cifre significative, con la virgola decimale e mai in notazione
esponenziale. Il conto lo fa il programma, non il modello.

Quando la conversione non ha senso lo strumento restituisce un errore in italiano, che il modello deve spiegare
senza inventare un numero: grandezze diverse (`non si può convertire un peso (kg) in una lunghezza (m)`), unità
fuori elenco (`unità non supportata «iarde»`, con l'elenco delle unità), temperature sotto lo zero assoluto, pesi
o lunghezze negativi, valore non numerico.

Come l'orologio, il convertitore è una **funzione Python del grafo** (`assistente/convertitore.py`): è un calcolo
puro e locale, senza dati esterni né stato, quindi un server separato aggiungerebbe solo un processo e un punto di
guasto. Prova reale da pipe del 03/11/2026 (`LOG_LEVEL=INFO`, `google/gemma-4-e4b`; uguale in Docker):

```text
[INFO] instradamento: richiesta strumento converti {"a": "km", "da": "metri", "valore": 25}
[INFO] nodo_strumenti: converti -> 25 m = 0,025 km
[INFO] nodo_llm: chiamata al modello (4 messaggi)
[INFO] nodo_llm: risposta ricevuta in 18.7 s
[INFO] instradamento: nessuno strumento -> fine
Tu> Assistente> 25 metri sono **0,025 km**.
```

Nella stessa prova, a «Quanti metri sono 5 kg?» il modello ha risposto da solo, senza chiamare lo strumento, che
chilogrammi e metri misurano grandezze diverse: la risposta era corretta, ma la spiegazione non veniva dal
programma. I messaggi d'errore dello strumento sono verificati dai test automatici.

## Calcolatrice (strumento MCP)

Per i calcoli il modello chiede lo strumento `calcola`, con un solo argomento testuale `espressione` (per
esempio `12.5*8-3`). Sono ammessi numeri (con il punto per i decimali), `+ - * / // % **` e parentesi; `%` è il
resto della divisione, non la percentuale. Il risultato è calcolato dal programma, mai dal modello, e senza
eseguire codice: l'espressione viene analizzata e si valutano solo le operazioni ammesse.

A differenza dell'orologio, che è una funzione Python del grafo, la calcolatrice è un **server MCP**: un
programma separato che dichiara i propri strumenti con il protocollo MCP. L'assistente non conosce in anticipo
lo strumento: lo scopre chiedendo il catalogo al server.

- Server: cartella `calcolatrice_mcp/` (`calcolo.py` la logica pura, `server.py` il server FastMCP); si avvia con
  `python -m calcolatrice_mcp` e comunica su stdin/stdout (trasporto stdio). Non serve avviarlo a mano: lo avvia
  l'assistente.
- Client: `assistente/client_mcp.py`. All'avvio legge il catalogo e rende sincroni gli strumenti per il grafo.

Il percorso di una domanda è quello dell'orologio, con un passo in più all'inizio:

1. **discovery**, all'avvio: l'assistente avvia il server e ne legge il catalogo (nome, descrizione e schema di
   `calcola`);
2. **richiesta**: il modello risponde con una richiesta strutturata di `calcola` invece che con un testo;
3. **esecuzione**: il nodo degli strumenti chiama il server MCP, che calcola il risultato;
4. **`ToolMessage`**: il risultato torna al modello come messaggio correlato alla richiesta; il modello scrive la
   risposta finale.

Prova da pipe (prima domanda: un calcolo; seconda: una divisione per zero):

```powershell
"Quanto fa 12,5 per 8 meno 3?`nQuanto fa 5 diviso 0?`n/esci" | .\.venv\Scripts\python.exe -m assistente
```

Con `LOG_LEVEL=INFO` i quattro passi si riconoscono nei log su stderr (esecuzione reale del 03/11/2026 con
`google/gemma-4-e4b`; la riga del catalogo è accorciata):

```text
[INFO] client_mcp: catalogo di calcolatrice letto in 2.4 s: calcola (Calcola un'espressione aritmetica e restituisce il risultato esatto; ...)
[INFO] nodo_llm: chiamata al modello (2 messaggi)
[INFO] nodo_llm: risposta ricevuta in 18.6 s
[INFO] instradamento: richiesta strumento calcola {"espressione": "12.5*8-3"}
[INFO] client_mcp: calcola eseguito in 2.6 s
[INFO] nodo_strumenti: calcola -> 97
[INFO] nodo_llm: chiamata al modello (4 messaggi)
[INFO] nodo_llm: risposta ricevuta in 27.4 s
[INFO] instradamento: nessuno strumento -> fine
Tu> Assistente> Il risultato di 12,5 per 8 meno 3 è 97.
```

Il modello ha scritto `12,5` all'italiana nella domanda ma `12.5` nell'argomento, come chiede la descrizione dello
strumento. Ogni chiamata a `calcola` avvia un nuovo processo del server: la discovery e ogni calcolo richiedono
tra 2,5 e 3 s in locale e poco più di 1 s nel container Docker (catalogo 1,3 s, `calcola` 1,1 s), molto meno della
risposta del modello (circa 20 s).

**Errori controllati.** Un'espressione non valida non interrompe il turno: il server risponde con un messaggio
d'errore in italiano, che arriva al modello come `ToolMessage` con stato `error`, e nel log compare un
`[WARNING]`. Per la seconda domanda:

```text
[INFO] instradamento: richiesta strumento calcola {"espressione": "5/0"}
[WARNING] nodo_strumenti: errore dello strumento calcola: divisione per zero
[INFO] nodo_llm: chiamata al modello (8 messaggi)
[INFO] nodo_llm: risposta ricevuta in 23.8 s
[INFO] instradamento: nessuno strumento -> fine
Tu> Assistente> Non è possibile calcolare 5 diviso 0; si tratta di un errore di divisione per zero.
```

Gli altri errori controllati: espressione vuota o più lunga di 200 caratteri, sintassi non valida, elementi non
ammessi (nomi, funzioni, testo), virgola decimale (`2,5`: si suggerisce il punto), `^` invece di `**`, esponente
oltre 100 in valore assoluto, numeri oltre `10**100` in valore assoluto, risultato non reale. Se il server non
risponde durante la chat (errore di trasporto), anche il modello riceve un `ToolMessage` d'errore
(`server MCP calcolatrice non raggiungibile: ...`) e la chat continua; nel log compaiono due `[WARNING]`, uno di
`client_mcp` e uno di `nodo_strumenti`. Questo caso è coperto solo dai test automatici. Se il server non parte
all'avvio, il programma termina con codice 1 (vedi «Diagnosi»).

## Mostrare e nascondere i log

Il comando `/log` alterna le due modalità di log (vedi «Configurazione») senza interrogare il modello e senza
entrare nella cronologia; risponde con `Log nascosti: solo dialogo. Scrivi /log per mostrarli.` oppure
`Log visibili. Scrivi /log per nasconderli.` Prova da pipe, con il livello predefinito (`INFO`): una domanda con
i log visibili, `/log`, una domanda con i log nascosti, `/log`, una domanda di nuovo con i log visibili:

```powershell
"Che ore sono?`n/log`nChe ore sono a New York?`n/log`nChe giorno è oggi?`n/esci" | .\.venv\Scripts\python.exe -m assistente
```

```text
Tu> [INFO] nodo_llm: chiamata al modello (2 messaggi)
[INFO] nodo_llm: risposta ricevuta in ... s
[INFO] instradamento: richiesta strumento ora_corrente {}
[INFO] nodo_strumenti: ora_corrente -> mercoledì 2026-10-28T11:40:19+01:00 (Europe/Rome)
[INFO] nodo_llm: chiamata al modello (4 messaggi)
[INFO] nodo_llm: risposta ricevuta in ... s
[INFO] instradamento: nessuno strumento -> fine
Assistente> Sono le 11:40 di mercoledì 28 ottobre 2026, ora di Roma (CET).
Tu> Log nascosti: solo dialogo. Scrivi /log per mostrarli.
Tu> Assistente> A New York sono le 06:40 di mercoledì 28 ottobre 2026 (EDT).
Tu> Log visibili. Scrivi /log per nasconderli.
Tu> [INFO] nodo_llm: chiamata al modello (10 messaggi)
[INFO] nodo_llm: risposta ricevuta in ... s
[INFO] instradamento: richiesta strumento ora_corrente {}
[INFO] nodo_strumenti: ora_corrente -> mercoledì 2026-10-28T11:41:34+01:00 (Europe/Rome)
[INFO] nodo_llm: chiamata al modello (12 messaggi)
[INFO] nodo_llm: risposta ricevuta in ... s
[INFO] instradamento: nessuno strumento -> fine
Assistente> Oggi è mercoledì 28 ottobre 2026.
Tu> Alla prossima!
```

Il secondo turno non lascia righe `[INFO]`, ma ha usato comunque lo strumento: la terza chiamata riceve 10
messaggi (sistema, quattro per ciascuno dei due turni con lo strumento, nuova domanda), quindi i due `/log` non
sono entrati nella cronologia. In questa prova la scritta `Ragionando...` non compare mai: si vede solo nella
chat da tastiera, e solo con i log nascosti.

## Avvio con Docker Compose

L'applicazione si avvia anche in un container. LM Studio **non** è containerizzato: resta sul computer host, con il
server avviato e il modello caricato come per l'avvio locale. Servono Docker Desktop avviato (`docker info` deve
rispondere) e un `.env` compilato come in «Configurazione».

- `Dockerfile`: immagine `python:3.14.7-slim`, dipendenze installate da `requirements.txt` prima della copia del
  codice (cache dei layer), copia di `assistente/`, avvio con `python -m assistente`. `requirements-dev.txt` e i
  test restano fuori dall'immagine.
- `compose.yaml`: servizio `note` (stessa immagine, `python -m note_api`, note nel volume `note-dati` su `/app/dati`)
  e servizio `assistente` con `NOTE_API_URL=http://note:8000` e `depends_on: note`, così `docker compose run`
  avvia anche il servizio delle note; `assistente` ha le variabili di `.env`, ma con `LMSTUDIO_BASE_URL` impostata a
  `http://host.docker.internal:1234/v1` (nel container `localhost` è il container stesso, non il computer host),
  `stdin_open` e `tty` per la chat da tastiera, `host.docker.internal` mappato sull'host; nessuna porta pubblicata.
- `.dockerignore`: `.env`, `.venv`, cache, `.git`, `tests`, `docs` non entrano nell'immagine. Il `.env` arriva al
  container come variabili d'ambiente, non come file: in `/app` ci sono solo `assistente/` e `requirements.txt`.

Costruzione dell'immagine e controllo che le librerie si importino:

```powershell
docker compose build
docker compose run --rm assistente python -c "import assistente, langgraph; print('ok')"
```

La seconda riga stampa `ok`. Il primo `build` scarica l'immagine di base e le dipendenze e può richiedere un po' di tempo.

Prova con input da pipe (`-T` disattiva il pseudo-terminale, necessario per l'ingresso da pipe), con la stessa
domanda sull'ora della sezione «Strumento orologio»:

```powershell
"Che ore sono?`n/esci" | docker compose run --rm -T assistente
```

```text
Tu> [INFO] nodo_llm: chiamata al modello (2 messaggi)
[INFO] nodo_llm: risposta ricevuta in 16.0 s
[INFO] instradamento: richiesta strumento ora_corrente {}
[INFO] nodo_strumenti: ora_corrente -> mercoledì 2026-10-28T12:02:30+01:00 (Europe/Rome)
[INFO] nodo_llm: chiamata al modello (4 messaggi)
[INFO] nodo_llm: risposta ricevuta in 26.2 s
[INFO] instradamento: nessuno strumento -> fine
Assistente> Sono le 12:02 e 30 secondi di mercoledì 28 ottobre 2026, secondo l'ora di Roma (CET).
Tu> Alla prossima!
```

Il container ha raggiunto LM Studio sull'host e la richiesta di `ora_corrente` e la sua esecuzione compaiono
nei log come in locale. Con l'input da pipe la scritta `Ragionando...` non compare.

Note in Docker: la prova da pipe del 09/11/2026 ha salvato una nota in una sessione e l'ha ritrovata in una seconda
sessione (`docker compose run --rm -T -e LOG_LEVEL=INFO assistente`, due volte), con le stesse righe di log della
sezione «Note». `docker compose down` ferma e rimuove anche il container `note`, ma il volume resta (`docker volume
ls --filter name=note-dati` mostra `assistente-laboratorio_note-dati`).

Chat interattiva: si avvia con `run`, non con `up` (vedi «Diagnosi»).

```powershell
docker compose run --rm --name assistente-demo assistente
```

Da un secondo terminale si seguono i log del container e si controlla che sia in esecuzione:

```powershell
docker logs -f assistente-demo
docker ps
```

`--name assistente-demo` dà al container un nome fisso, così `docker logs -f assistente-demo` non richiede di
cercare l'identificativo. `--rm` rimuove il container all'uscita; la rete creata da Compose si toglie con
`docker compose down`. I comandi della chat sono quelli dell'avvio locale (`/esci`, `/log`).

La demo interattiva non è automatizzabile: l'ha provata a mano l'utente il 28/10/2026 e, secondo il suo resoconto,
hanno funzionato una conversazione a due turni, due domande sull'ora, la domanda su New York, `/log` con la scritta
`Ragionando...` e Ctrl+C durante l'attesa. Questi passaggi non sono stati ripetuti nella verifica finale (che ha
coperto soltanto i comandi da pipe e `docker compose build`). Checklist per ripetere la prova a mano:

1. `docker compose build`, poi `docker compose run --rm --name assistente-demo assistente`.
2. Conversazione su due turni (per esempio il colore preferito e poi la domanda su quale sia).
3. Due domande sull'ora nella stessa sessione, con il giorno della settimana corretto.
4. «Che ore sono a New York?»: nel log la richiesta contiene `"fuso": "America/New_York"`.
5. Da un secondo terminale `docker logs -f assistente-demo` mostra gli stessi log.
6. `/log` nasconde i log e fa comparire `Ragionando...` durante l'attesa; un secondo `/log` li mostra di nuovo.
7. Ctrl+C durante l'attesa: saluto e uscita senza traceback.

Confronto tra l'orologio dell'host e quello della macchina virtuale di Docker (l'ora dello strumento parte dal
sistema in cui gira il programma):

```powershell
Get-Date
docker run --rm python:3.14.7-slim date
```

```text
lunedì 2 novembre 2026 09:27:28
Mon Nov  2 08:27:28 UTC 2026
```

Il container mostra l'ora in UTC, l'host in ora di Roma (CET, UTC+01:00): le due ore coincidono.

## Diagnosi

- **Le note non funzionano** («servizio note non raggiungibile ...» nel log o nella risposta): in locale avviare
  `.\.venv\Scripts\python.exe -m note_api` in un secondo terminale e controllare `NOTE_API_URL`. Con il servizio
  spento l'assistente parte comunque, con un avviso; su Windows l'avvio richiede qualche secondo in più per i
  tentativi di connessione.
- **Il server non è disponibile**: l'avvio termina con
  `Errore: Impossibile leggere l'elenco dei modelli da http://.../v1/models: ...` e codice 1. Avviare il
  server locale in LM Studio e controllare `LMSTUDIO_BASE_URL`. Provato con `LMSTUDIO_BASE_URL=http://localhost:9/v1`:
  messaggio come sopra e codice 1.
- **Il modello è assente**: l'avvio termina con
  `Errore: Il modello «...» non è disponibile in LM Studio. Modelli disponibili: ...` e codice 1. Copiare in
  `LMSTUDIO_MODEL` uno degli identificativi elencati. Provato con `LMSTUDIO_MODEL=modello-inesistente`.
- **`.env` non è in UTF-8**: l'avvio termina con `Errore: Il file .env non è in UTF-8 ...` e codice 1. Succede se
  il file è stato creato con `>` o `Out-File` di PowerShell 5.1, che scrivono UTF-16. Ricrearlo con
  `Copy-Item .env.example .env`. Provato il 02/11/2026 con `"LMSTUDIO_MODEL=google/gemma-4-e4b" > .env` in una
  cartella temporanea.
- **`LMSTUDIO_BASE_URL` non valido** (senza schema, oppure con parentesi quadre non chiuse come `http://[::1/v1`):
  `Errore: LMSTUDIO_BASE_URL non è un indirizzo valido: «...». Serve lo schema, per esempio http://localhost:1234/v1.`
  e codice 1. Provato il 02/11/2026 con `http://[::1/v1`.
- **Le lettere accentate arrivano come `?`** con l'ingresso da pipe in PowerShell 5.1: vedi «Avvio» (riga con
  `$OutputEncoding`).
- **Il server si ferma durante la chat**, o una richiesta supera il timeout (180 s, con un solo nuovo
  tentativo): il programma stampa
  `Errore: nessuna risposta valida da LM Studio (<indirizzo>): <Classe>: <dettaglio>. Turno annullato.`,
  scarta il turno (domanda e risposta non entrano nella cronologia) e prosegue. Il 28/10/2026 l'utente ha provato a mano
  a fermare LM Studio a metà chat e a riavviarlo e, secondo il suo resoconto sintetico, ha funzionato; non
  ripetuto nella verifica finale. Il timeout (180 s) *non è stato provato*: lo coprono solo i test automatici con
  un modello finto. Con `LOG_LEVEL=DEBUG` si ottiene il traceback completo nel log.
- **Contesto esaurito** (sessione lunga): *non provato*. La cronologia cresce senza tagli per tutta la sessione.
  Se LM Studio rifiuta la richiesta, l'errore dovrebbe comparire con lo stesso messaggio del punto precedente; in
  quel caso conviene uscire con `/esci` e riavviare. Aumentare la lunghezza di contesto nelle impostazioni di
  caricamento in LM Studio è il rimedio previsto, ma non è stato provato. La politica di overflow di LM Studio
  potrebbe anche tagliare messaggi in silenzio (ipotesi non verificata): se il modello sembra dimenticare l'inizio della
  conversazione, riavviare la sessione.
- **Risposta vuota o non valida**: se il modello risponde senza testo (o con una richiesta di strumento
  malformata) il programma stampa `Errore: il modello non ha prodotto una risposta valida. Turno annullato.` e
  scrive un avviso `[WARNING]` nel log. Verificato solo dai test automatici con un modello finto, non con il
  modello reale.

Per la calcolatrice MCP (vedi «Calcolatrice») si controllano i livelli in ordine, dal server alla risposta:

1. **Il server da solo**, senza modello e senza assistente:
   `.\.venv\Scripts\python.exe -m pytest tests/test_server_mcp.py -v` (quattro test: catalogo, invocazione
   diretta, due errori). Se fallisce, il problema è nel server o nelle dipendenze MCP.
2. **Discovery all'avvio**: con `LOG_LEVEL=INFO` la prima riga è
   `[INFO] client_mcp: catalogo di calcolatrice letto in ... s: calcola (...)`. Se il server non parte, l'avvio
   termina con codice 1 e un messaggio come
   `Errore: server MCP calcolatrice non avviato (python.exe -m calcolatrice_mcp): Connection closed`, preceduto
   dall'errore del processo del server (per esempio un modulo mancante). Il messaggio è stato provato il
   03/11/2026 chiamando il client con un modulo inesistente; il primo controllo è avviare dalla cartella del
   progetto con l'ambiente virtuale completo (`requirements.txt`).
3. **Richiesta del modello**: `[INFO] instradamento: richiesta strumento calcola {"espressione": "..."}`. Se manca,
   il modello ha risposto senza chiamare lo strumento e il numero non viene dalla calcolatrice.
4. **Esecuzione**: `[INFO] client_mcp: calcola eseguito in ... s`. Un `[WARNING] client_mcp: server MCP
   calcolatrice non raggiungibile: ...` indica un errore di trasporto (il server si è interrotto).
5. **`ToolMessage`**: `[INFO] nodo_strumenti: calcola -> <risultato>` è il risultato restituito al modello; un
   `[WARNING] nodo_strumenti: errore dello strumento calcola: <motivo>` è un errore controllato (per esempio
   `divisione per zero`) che il modello riceve e deve spiegare senza inventare un numero.

Per il convertitore (vedi «Convertitore») con `LOG_LEVEL=INFO`: `[INFO] instradamento: richiesta strumento
converti {...}` mostra la richiesta del modello e `[INFO] nodo_strumenti: converti -> <risultato>` il risultato; un
errore controllato (per esempio unità non supportata) compare come `[WARNING] nodo_strumenti: errore dello
strumento converti: <motivo>`. Se manca la riga `richiesta strumento converti`, il modello ha risposto senza lo
strumento e il numero non viene dal programma.

Per giorni e scadenze (vedi «Giorni e scadenze») vale lo stesso con `giorni_tra`, `sposta_data`,
`giorno_settimana` e `pasqua`: senza la riga `richiesta strumento <nome>` la data o il numero non vengono dal
programma. Se il conteggio sembra spostato di un giorno, controllare `APP_TIMEZONE`: «oggi» è calcolato in quel fuso.

Con Docker Compose (sintomo, primo controllo):

- **Il container resta `Up` ma non succede nulla** (avviato con `docker compose up` invece di `run`): l'applicazione
  attende un input che nessuno può digitare e non scrive nulla. Provato il 02/11/2026: con `docker compose up -d`
  `docker ps` mostra il container `Up` e `docker compose logs` è vuoto; con `docker compose up` (in primo piano) compare
  solo `Attaching to assistente-1` e il comando non termina. Si ferma e si rimuove con `docker compose down`. Per chattare usare `docker compose run`.
- **Il container termina subito, con codice 1**: l'errore di avvio compare nell'output del terminale (per esempio
  server o modello non disponibili, come nelle prime due voci). Provato con `LMSTUDIO_BASE_URL` sbagliata (vedi
  la voce «Nessuna connessione al modello»).
- **`docker compose` si lamenta di un file `.env` non trovato**: il file indicato da `env_file` deve esistere.
  Provato il 02/11/2026 in una copia temporanea del progetto senza `.env`: `docker compose config` e `docker compose run` terminano
  con codice 1 e `env file ...\.env not found: CreateFile ...\.env: The system cannot find the file specified.`
  Creare il file come in «Configurazione» (`Copy-Item .env.example .env`).
- **Nessuna connessione al modello**: controllare in ordine il server di LM Studio (avviato, modello caricato),
  l'URL configurato e la raggiungibilità. Nel container `localhost` è il container stesso: con
  `LMSTUDIO_BASE_URL=http://localhost:1234/v1` l'avvio termina subito con codice 1.

  ```powershell
  "/esci" | docker compose run --rm -T -e LMSTUDIO_BASE_URL=http://localhost:1234/v1 assistente
  ```

  ```text
  Errore: Impossibile leggere l'elenco dei modelli da http://localhost:1234/v1/models: [Errno 111] Connection refused. Avviare il server locale in LM Studio e controllare LMSTUDIO_BASE_URL.
  ```

  Compose usa invece `http://host.docker.internal:1234/v1`, che dal container arriva all'host. Su questo PC,
  con Docker Desktop, LM Studio ascoltava soltanto su `127.0.0.1` e il container lo ha raggiunto lo stesso:

  ```powershell
  Get-NetTCPConnection -LocalPort 1234 -State Listen | Select-Object LocalAddress, LocalPort, State
  ```

  ```text
  LocalAddress LocalPort  State
  ------------ ---------  -----
  127.0.0.1         1234 Listen
  ```

  Se in un'altra configurazione la connessione dal container viene rifiutata, i controlli da fare (non
  necessari qui, quindi non provati) sono l'indirizzo di ascolto di LM Studio, cioè l'opzione «Serve on Local
  Network», e il firewall di Windows.
- **Risposta sull'ora senza uso dell'orologio**: cercare nei log del container le richieste di strumento
  (`instradamento: richiesta strumento ora_corrente ...`) e il percorso seguito (`nodo_strumenti`, poi
  `instradamento: nessuno strumento -> fine`). Un'ora senza queste righe non proviene dallo strumento. Con i log
  nascosti (`/log`) o con `LOG_LEVEL=WARNING` le righe non compaiono.
- **Il container è già scomparso e non si può ispezionare**: `--rm` lo rimuove all'uscita. Per esaminare un
  arresto dopo la chiusura, ripetere il comando senza `--rm` e guardare `docker ps -a` e `docker logs`. Un
  container in esecuzione non dimostra che funzionino tutti i componenti: bisogna vedere la risposta del modello
  e, per l'orologio, le righe di `ora_corrente`.
- **L'ora risulta sbagliata di colpo**: l'orologio della macchina virtuale di Docker Desktop può restare indietro
  dopo la sospensione del PC (problema noto con WSL2; non riprodotto qui). Confrontare l'ora dell'host con quella
  del container come in «Avvio con Docker Compose»: se differiscono, l'errore viene dall'orologio della macchina
  virtuale e non dall'applicazione (primo tentativo: riavviare Docker Desktop, non provato qui).
