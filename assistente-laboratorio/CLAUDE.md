# Assistente del laboratorio

Progetto del corso «Deep Learning e LLM: costruire chatbot e agenti».
La cartella del progetto è `assistente-laboratorio/`; i comandi si eseguono da lì, in PowerShell.

## Obiettivo
Un'applicazione da terminale in Python che conversa con un modello locale e:
- organizza il flusso in un grafo LangGraph esplicito (stato, nodi, instradamento riconoscibili);
- usa un modello servito da LM Studio, che resta sul computer host;
- conserva la cronologia della conversazione per la durata della sessione (nessuna persistenza);
- offre uno strumento orologio con fuso orario esplicito, richiesto dal modello tramite tool calling
  ed eseguito davvero dal programma;
- si avvia anche con Docker Compose.

## Confini
- Implementare solo i requisiti concordati. Altri strumenti, MCP, workflow e RAG arriveranno
  nelle lezioni successive: non anticiparli.
- Niente interfacce grafiche, servizi cloud o framework non concordati.
- Lavorare solo dentro `assistente-laboratorio/`. La repository contiene altre lezioni:
  non leggerle per copiarne il codice e non modificarle.
- Lavorare nel branch corrente; nessun branch o worktree nuovo se non richiesto.

## Struttura
- `assistente/`: pacchetto avviato con `python -m assistente`.
  - `config.py`: variabili d'ambiente, validazione, configurazione dei log.
  - `strumenti.py`: strumento `ora_corrente` (fuso facoltativo, istante iniettabile).
  - `modello.py`: `ChatOpenAI` verso LM Studio e controllo dell'elenco modelli all'avvio.
  - `grafo.py`: stato, nodi e instradamento; `costruisci_grafo(modello, strumenti)`.
  - `cli.py`, `__main__.py`: ciclo di chat, cronologia, comandi `/esci` e `/log`, scritta «Ragionando...».
- `tests/`: test automatici senza modello; `test_reale.py` contiene le prove con LM Studio (marcatore `reale`).
- `docs/superpowers/`: specifica e piano.
- `Dockerfile`, `compose.yaml`, `.dockerignore`: avvio con Docker Compose.
- `.env.example` (esempio senza credenziali), `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`.

## Scelte tecniche
- Python 3.14.7 (`py -3.14 -m venv .venv`; immagine Docker `python:3.14.7-slim`). Si usa
  `.\.venv\Scripts\python.exe` direttamente, senza `Activate.ps1`.
- Codice sincrono e moduli piccoli, con una separazione semplice tra
  grafo, collegamento al modello, strumenti e interfaccia da terminale.
- LM Studio sull'host, raggiunto tramite la sua API compatibile con OpenAI.
- Indirizzo del server e identificativo del modello solo da variabili d'ambiente
  (`LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL`; inoltre `APP_TIMEZONE` e `LOG_LEVEL`).
  L'identificativo è quello restituito dal server (`GET /v1/models`), mai inventato.
- Un file di configurazione di esempio senza credenziali; il file reale (`.env`) resta fuori da Git.
- Docker Compose per l'applicazione; LM Studio non va containerizzato.
- Dipendenze motivate, concordate e con versioni fissate in `requirements.txt`; `pytest` solo in
  `requirements-dev.txt`.
- Comandi documentati anche per PowerShell (Windows).

## Comandi
- Installazione: `py -3.14 -m venv .venv`, poi `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`.
- Avvio: `.\.venv\Scripts\python.exe -m assistente`.
- Test automatici (nessun modello; i `reale` sono esclusi di default): `.\.venv\Scripts\python.exe -m pytest`.
- Test reali (LM Studio attivo, `.env` compilato; richiedono diversi minuti):
  `.\.venv\Scripts\python.exe -m pytest -m reale -v`.
- Docker: `docker compose build`, poi `docker compose run --rm --name assistente-demo assistente`
  (si usa `run`, non `up`; con input da pipe `docker compose run --rm -T assistente`).

## Metodo: Superpowers
- Usare le skill di Superpowers per brainstorming, specifica, piano, implementazione e verifica.
- Non scrivere codice prima che io abbia approvato la specifica e poi il piano.
- Salvare specifica e piano in `assistente-laboratorio/docs/superpowers/`.
- Procedere per incrementi piccoli, ciascuno verificato prima del commit.

## Test e verifiche
- Test automatici ripetibili che non richiedono un modello attivo (grafo, cronologia,
  instradamento, strumento con istante controllato).
- Prove reali con LM Studio e con Docker tenute separate e attivate esplicitamente.
- Una risposta simulata non dimostra che il modello locale sappia usare lo strumento.
- Nel resoconto indicare che cosa è stato eseguito, con quale esito, e che cosa resta da provare.

## Git
- Conventional Commits in italiano, per esempio `feat(grafo): ...`, `test(strumenti): ...`,
  `docs: ...`.
- Prima di ogni commit: `git status`, controllo del diff, staging selettivo dei soli file pertinenti.
- Mai versionare credenziali, `.env`, ambienti virtuali, cache o pesi dei modelli.
- Push soltanto su mia richiesta.

## Documentazione
- Tenere aggiornato il README con configurazione, avvio, test e diagnosi, riportando solo
  comandi verificati.
- Aggiornare questo file quando cambiano convenzioni stabili (struttura, comandi di test,
  regole di lavoro), non per annotare l'avanzamento.
