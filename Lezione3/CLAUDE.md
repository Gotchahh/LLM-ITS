# Assistente del laboratorio
- Obiettivo: un client Python per un modello locale.
- client.py contiene il client: domanda da terminale, risposta in streaming,
  cronologia della sessione in memoria.
- README.md descrive la preparazione dell'ambiente.
- requirements.txt contiene le dipendenze concordate.
- Usare PowerShell nei comandi per Windows.
- Preferire Python sincrono e modifiche circoscritte.
- Non aggiungere dipendenze senza motivarle e concordarle.
- Non inserire segreti, pesi o ambiente virtuale in Git.
- Non sono presenti test automatici in questo checkpoint.
- Avvio dalla cartella Lezione3: .\venv\Scripts\python.exe client.py
- Verifica manuale: due domande diverse, riga vuota, esci e Ctrl+C,
  server fermo e ripristinato; nome ricordato nella sessione e
  dimenticato al riavvio.

## Vincoli sul client
- URL e modello solo da .env (LM_BASE_URL, LM_MODEL): mai valori fissi nel codice.
- Conservare "reasoning_effort": "none" nel payload: senza, la risposta arriva vuota.
- Mantenere distinti i messaggi di Timeout, ConnectionError e HTTPError.
- Nessuna interfaccia grafica, applicazione web o framework.
- La cronologia resta in memoria: nessun file o database.
- Una richiesta fallita non lascia la domanda nella cronologia.

## Metodo di lavoro
- Prima leggere i file e proporre un piano; modificare solo dopo l'approvazione.
- Distinguere le prove eseguite da quelle ancora da fare; se LM Studio non
  risponde, segnalarlo senza simulare una risposta.
- Aggiornare README e questo file solo dopo una verifica riuscita.
- Scrivere i file in UTF-8 senza BOM.

## Git
- Commit e push solo su richiesta esplicita.
- Un commit per modifica verificata, una sola estensione per commit.
- Messaggi Conventional Commits in italiano, es. feat(client): ...
- Aggiungere i file per nome, non con git add .; LLM_Lez_3.pdf resta fuori.
