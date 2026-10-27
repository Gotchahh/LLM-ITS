# Assistente del laboratorio

Applicazione da terminale in Python costruita attorno a un grafo LangGraph esplicito.
In questa fase il grafo risponde sempre con una frase fissa: il collegamento al modello
locale (LM Studio) e lo strumento orologio arriveranno negli incrementi successivi.

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

Il modulo `assistente/config.py` legge e valida queste variabili, ma l'avvio dell'applicazione
non lo usa ancora: sarà collegato in un incremento successivo.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Le prove che richiedono LM Studio attivo hanno il marcatore `reale` e sono escluse di default.

## Avvio

Prova con due righe in ingresso (un messaggio e il comando `/esci`):

```powershell
"ciao`n/esci" | .\.venv\Scripts\python.exe -m assistente
```

Stampa `Assistente> Il grafo è in esecuzione.` e `Alla prossima!`.
Lo stesso comando senza ingresso da pipe apre la chat interattiva (prompt `Tu> `, `/esci` per uscire).
