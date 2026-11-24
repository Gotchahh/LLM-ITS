# Router dell'ambito — specifica di design (Lezione 6, step 1)

> Stato: approvata dall'utente il 09/11/2026. Branch `feature/router`, nato da `dev` (`2275845`) con il `CLAUDE.md` aggiornato
> (`36439c0`).

## Intento e perché
L'assistente è del laboratorio: domande fuori tema (poesie, sport, ricette…) non hanno senso e oggi ricevono comunque
una risposta. Un **secondo nodo LLM**, il router, posto prima dell'agente, decide se la domanda rientra nell'ambito.
Fuori ambito → risposta di rifiuto, **senza** chiamare l'agente né gli strumenti. È lo step 1 (base) della Lezione 6.

## Decisioni prese con l'utente
- **Ambito**: domande scientifiche o inerenti al laboratorio; fuori da lì l'assistente non risponde.
- Proposte dell'assistente accettate così come presentate:
  - in ambito anche ciò che gli strumenti già coprono (ora e date, calcoli, conversioni, note, apparecchi), saluti e
    ringraziamenti brevi e le domande di seguito («e domani?»), per le quali il router vede anche gli ultimi messaggi;
  - rifiuto breve e cortese con il motivo; agente e strumenti non vengono chiamati;
  - ambito descritto in un file di testo di configurazione, modificabile senza toccare il codice;
  - output strutturato del router (categoria e motivo) visibile nei log;
  - se l'output del router è illeggibile, la domanda passa all'agente (meglio una risposta in più che un rifiuto
    sbagliato);
  - una chiamata al modello in più per ogni domanda.

## Obiettivi (evidenze delle slide)
1. Domanda in ambito: nel log categoria, motivo e passaggio all'agente; il resto come oggi.
2. Domanda fuori ambito: rifiuto; nei log **nessuna** riga di `nodo_llm` (agente) né di strumenti.
3. Test con risposte del router simulate per entrambi i percorsi (e per l'output illeggibile).
4. Nulla si rompe: le 12 prove reali esistenti continuano a passare (il router non deve rifiutarle), tutti i test
   automatici verdi.

## Non-obiettivi
Revisore, riassunto, resource, prompt e gli altri step; scelta degli strumenti da parte del router (resta
all'agente); più categorie oltre alle due; rifiuto generato dal modello; ambito diverso per utente.

## Anti-obiettivi
- Il router che rifiuta domande legittime già coperte dagli strumenti o dalle prove reali (anche «Il mio colore
  preferito è il verde» seguito da «Qual è il mio colore preferito?»: è conversazione con l'utente).
- L'ambito scritto nel codice.
- Il rifiuto che passa comunque per l'agente o per gli strumenti.
- `pydantic` importato nel pacchetto `assistente/` (lo schema dell'output è un dizionario JSON Schema).

## Comportamento

### Configurazione
- File `ambito.txt` nella cartella del progetto, versionato, con il testo dell'ambito in italiano (in ambito / fuori
  ambito, con esempi). Percorso modificabile con la variabile facoltativa `AMBITO_FILE` (default `ambito.txt`).
- File mancante, vuoto o non UTF-8 → errore chiaro all'avvio e codice 1, come per le altre configurazioni.
- In Docker il file entra nell'immagine (`COPY ambito.txt .`).

### Grafo
```
START → nodo_router ─conversazione→ nodo_llm ⇄ nodo_strumenti → END   (come oggi)
                    └─fuori ambito→ nodo_rifiuto → END
```
- `nodo_router`: chiama lo **stesso modello, senza strumenti associati**, con un prompt di sistema proprio (istruzioni
  di classificazione + testo dell'ambito) e gli ultimi messaggi della cronologia (domande e risposte testuali, senza
  i messaggi degli strumenti; per esempio gli ultimi 6) più la domanda corrente. Output strutturato:
  `{"categoria": "conversazione" | "fuori_ambito", "motivo": "<breve, in italiano>"}`.
  Log: `router: conversazione (<motivo>)` oppure `router: fuori ambito (<motivo>)`.
  La decisione del router **non** entra nella cronologia.
- Arco condizionale dopo il router: `conversazione` → `nodo_llm`; `fuori_ambito` → `nodo_rifiuto`.
- `nodo_rifiuto`: aggiunge alla cronologia un `AIMessage` con un testo fisso più il motivo, per esempio «Posso
  aiutarti solo con domande scientifiche o sul laboratorio: <motivo>.» Log: `nodo_rifiuto: domanda fuori ambito`.
- Output illeggibile o non conforme allo schema → log WARNING e si procede come `conversazione`. Un errore di
  connessione al modello invece annulla il turno come oggi.
- Il router si attiva solo se `costruisci_grafo` riceve l'ambito; senza ambito il grafo resta quello di oggi (i test
  esistenti restano validi). Il limite dei passaggi si alza di quanto serve perché il router non tolga passaggi
  all'agente.

### Verifica tecnica da fare per prima (LM Studio era spento durante la specifica)
Controllare con una prova usa e getta che gemma, via LM Studio, produca l'output strutturato con
`with_structured_output` (metodo `json_schema`); se non funziona, usare il metodo `function_calling`, e se nemmeno
quello, chiedere il JSON nel prompt e leggerlo dal testo. Il metodo scelto va annotato nel piano.

## Verifiche
- **Test senza modello**: router simulato (il `ModelloFinto` impara a restituire output strutturati) per in ambito
  (agente chiamato, log), fuori ambito (rifiuto, agente mai chiamato, nessuno strumento), output illeggibile (passa
  all'agente con WARNING); il router riceve gli ultimi messaggi senza quelli degli strumenti; il rifiuto entra nella
  cronologia e il turno successivo funziona; configurazione dell'ambito (file mancante, vuoto, variabile).
- **Prove reali con gemma**: «Scrivimi una poesia sul mare» → rifiuto senza `nodo_llm`; «Cos'è il pH?» → in ambito;
  le 12 prove esistenti ancora verdi.
- **Pipe** locale e **Docker** con una domanda in ambito e una fuori.

## Lasciato a chi costruisce
Testo esatto di `ambito.txt`, del prompt del router e del rifiuto; numero di messaggi passati al router; nomi interni.
