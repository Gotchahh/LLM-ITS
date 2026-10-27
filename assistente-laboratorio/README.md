# Assistente del laboratorio

Applicazione da terminale in Python costruita attorno a un grafo LangGraph esplicito.
Il grafo inoltra la conversazione al modello locale servito da LM Studio e conserva la
cronologia per la durata della sessione (nessuna persistenza). Lo strumento orologio
arriverà negli incrementi successivi.

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

Sono due prove: una risposta ordinaria e il ricordo di un'informazione data nel turno precedente.
Con un modello locale possono richiedere alcuni minuti (la prima chiamata carica il modello).

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
l'output successivo, per esempio i log `[INFO] nodo_llm: chiamata al modello (2 messaggi)` e
`[INFO] nodo_llm: risposta ricevuta in ... s` (su stderr, con `LOG_LEVEL=INFO`) e poi la risposta
`Assistente> ...`; con `LOG_LEVEL=WARNING` resta solo `Tu> Assistente> ...`. La seconda risposta usa la
cronologia: a ogni chiamata la richiesta cresce (2 messaggi, poi 4, ...). Se `$OutputEncoding` di
PowerShell è UTF-8 con BOM (così era nell'ambiente di prova), la pipe antepone un BOM alla prima riga: una
prima riga `/esci` non verrebbe riconosciuta come comando, per questo l'esempio inizia con un messaggio.

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
