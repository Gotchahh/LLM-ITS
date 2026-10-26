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
