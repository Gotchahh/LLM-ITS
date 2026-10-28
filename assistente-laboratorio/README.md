# Assistente del laboratorio

Applicazione da terminale in Python costruita attorno a un grafo LangGraph esplicito.
Il grafo inoltra la conversazione al modello locale servito da LM Studio e conserva la
cronologia per la durata della sessione (nessuna persistenza). Il modello può chiedere lo
strumento orologio `ora_corrente`, che il programma esegue davvero.

I comandi sono per PowerShell (Windows) e vanno eseguiti dalla cartella `assistente-laboratorio/`.

## Requisiti

- Python 3.14.7 (avviabile con `py -3.14`)

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

Le prime tre sono obbligatorie: se mancano o sono vuote, l'errore le elenca e rimanda a `.env.example`.

Le due modalità di log, scelte con `LOG_LEVEL`:

- `INFO`: i passaggi dell'applicazione sono visibili su stderr nel formato `[INFO] messaggio`;
- `WARNING`: solo il dialogo, più eventuali avvisi ed errori.

Solo i log dell'applicazione seguono `LOG_LEVEL`; quelli delle librerie esterne restano a `WARNING`.

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

Sono tre prove: una risposta ordinaria (senza strumento), il ricordo di un'informazione data nel turno
precedente e due domande sull'ora nella stessa sessione (due richieste di `ora_corrente`, una per turno).
Con un modello locale possono richiedere alcuni minuti (la prima chiamata carica il modello; con
`google/gemma-4-e4b` le tre prove sono durate circa 4 minuti e mezzo).

## Avvio

LM Studio deve avere il server locale avviato e il modello di `LMSTUDIO_MODEL` disponibile. Dalla cartella
`assistente-laboratorio/`:

```powershell
.\.venv\Scripts\python.exe -m assistente
```

Si apre la chat interattiva: prompt `Tu> `, risposte `Assistente> `. Comandi: `/esci` (oppure Ctrl+C o fine
dell'input) per uscire; una riga vuota viene ignorata; un altro comando che inizia con `/` mostra
`Comando sconosciuto. Comandi disponibili: /esci` senza interrogare il modello.

All'avvio l'applicazione controlla che il server risponda e che `LMSTUDIO_MODEL` sia tra i modelli
restituiti da `/v1/models`; se non lo è, stampa su stderr l'errore con l'elenco dei modelli disponibili
ed esce con codice 1.

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

stampa `Tu> Tu> Alla prossima!`.

## Strumento orologio

Per le domande su ora, data o giorno attuali il modello chiede lo strumento `ora_corrente`, senza argomenti, e
il programma lo esegue nel fuso `APP_TIMEZONE`. Prova con tre domande (la terza chiede l'ora di un'altra città):

```powershell
"Che ore sono?`nChe giorno della settimana è oggi?`nChe ore sono a Tokyo?`n/esci" | .\.venv\Scripts\python.exe -m assistente
```

Con `LOG_LEVEL=INFO` la chiamata allo strumento si riconosce nei log, su stderr, da queste due righe, che
precedono la risposta finale:

```text
[INFO] instradamento: richiesta strumento ora_corrente {}
[INFO] nodo_strumenti: ora_corrente -> mercoledì 2026-10-28T09:41:03+01:00 (Europe/Rome)
```

La prima è la richiesta strutturata del modello (nome e argomenti), la seconda il risultato dell'esecuzione,
che viene restituito al modello: segue una nuova `nodo_llm: chiamata al modello` con due messaggi in più
(la richiesta e il risultato) e infine `instradamento: nessuno strumento -> fine`. Una risposta sull'ora senza
queste due righe non proviene dallo strumento.

Per l'ora di un'altra città il modello chiama l'orologio e converte da sé: la risposta riporta anche l'ora
locale di partenza, così il calcolo si controlla a mano. La conversione può essere sbagliata: nella prova del
28/10/2026 una volta il modello ha risposto 16:42 a Tokyo partendo dalle 09:42 di Roma, mentre il valore
corretto era 17:42 (Tokyo è UTC+9, Roma in quel giorno UTC+1); un'altra esecuzione con la stessa domanda ha
dato 17:45 da 09:45.

Modalità silenziosa, con la variabile impostata solo per la sessione di PowerShell corrente:

```powershell
$env:LOG_LEVEL = "WARNING"
"Che ore sono?`nChe giorno della settimana è oggi?`nChe ore sono a Tokyo?`n/esci" | .\.venv\Scripts\python.exe -m assistente
Remove-Item Env:LOG_LEVEL
```

Restano solo i dialoghi, senza righe `[INFO]`:

```text
Tu> Assistente> Sono le 09:44 del giorno mercoledì 28 ottobre 2026, ora di Roma.
Tu> Assistente> Oggi è mercoledì.
Tu> Assistente> Attualmente sono le 09:45 a Roma (ora di partenza). A Tokyo, ora sono le **17:45** di mercoledì 28 ottobre 2026.
Tu> Alla prossima!
```

Il grafo ammette al massimo 10 passaggi per turno: se il modello continua a chiedere strumenti la chat stampa
`Errore: limite di 10 passaggi raggiunto. Turno annullato.`, scarta il turno e prosegue.

## Diagnosi

- **Il server non è disponibile**: l'avvio termina con
  `Errore: Impossibile leggere l'elenco dei modelli da http://.../v1/models: ...` e codice 1. Avviare il
  server locale in LM Studio e controllare `LMSTUDIO_BASE_URL`.
- **Il modello è assente**: l'avvio termina con
  `Errore: Il modello «...» non è disponibile in LM Studio. Modelli disponibili: ...` e codice 1. Copiare in
  `LMSTUDIO_MODEL` uno degli identificativi elencati.
- **Il server si ferma durante la chat**, o una richiesta supera il timeout (180 s, con un solo nuovo
  tentativo): la chat stampa
  `Errore: nessuna risposta valida da LM Studio (<indirizzo>): <Classe>: <dettaglio>. Turno annullato.`
  Il turno è scartato (domanda e risposta non entrano nella cronologia) e la chat prosegue: riprovare dopo
  aver riavviato il server. Con `LOG_LEVEL=DEBUG` il traceback completo compare nel log.
- **Contesto esaurito** (sessione lunga): LM Studio rifiuta la richiesta e l'errore compare con lo stesso
  messaggio. Aumentare la lunghezza di contesto del modello nelle impostazioni di caricamento in LM Studio.
  Attenzione: la politica di overflow di LM Studio può anche tagliare messaggi in silenzio, senza errore;
  se il modello sembra dimenticare l'inizio della conversazione, aumentare il contesto o riavviare la sessione.
- **Risposta vuota o non valida**: se il modello risponde senza testo (o con una richiesta di strumento
  malformata) compare `Errore: il modello non ha prodotto una risposta valida. Turno annullato.` e nel log un
  avviso `[WARNING]`.
