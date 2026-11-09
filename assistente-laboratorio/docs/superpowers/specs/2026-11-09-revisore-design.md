# Revisore della risposta — specifica di design (Lezione 6, step 2)

> Stato: approvata dall'utente il 09/11/2026. Branch `feature/revisore`, nato da `dev` (`30f68ee`, con il router).

## Intento e perché
Un modello locale piccolo a volte risponde solo a una parte della domanda o divaga. Un **secondo nodo LLM**, il
revisore, legge la domanda e la risposta proposta dall'agente e decide se è coerente; se non lo è, il motivo torna
all'agente, che riscrive la risposta, entro un limite di revisioni. È lo step 2 (intermedio) della Lezione 6.

## Decisioni (proposte dell'assistente accettate dall'utente)
- **Severità moderata**: rifiuta solo se manca una parte della domanda o se la risposta è fuori tema; non giudica lo
  stile né la verità dei fatti (compito degli strumenti); in caso di dubbio approva.
- Il revisore vede la domanda dell'utente e la risposta proposta; il rifiuto del router non passa dal revisore.
- Se rifiuta: il motivo torna all'agente come indicazione; l'agente riscrive (anche usando di nuovo gli strumenti).
- Limite: **2 revisioni per turno** (configurabile); al limite si restituisce l'ultima risposta con un avviso nel log.
- L'utente vede **solo la risposta finale**: bozze rifiutate e indicazioni servono durante il turno e poi vengono
  tolte dalla cronologia.
- Revisore senza ragionamento, come il router (~7–10 s in più per risposta); output illeggibile o errore del revisore
  → la bozza è approvata, con un avviso nel log.
- Istruzioni del revisore in un file di configurazione (come `ambito.txt`); limite da variabile d'ambiente.

## Obiettivi (evidenze delle slide)
1. Domanda in due parti con risposta parziale: rifiuto motivato e nuova risposta completa.
2. Risposta coerente: approvata al primo passaggio.
3. Limite rispettato con un revisore simulato che rifiuta sempre.
4. Nulla si rompe: router, strumenti, cronologia, `/log`, prove reali esistenti.

## Non-obiettivi
Riassunto della cronologia e step successivi; correzione dei fatti; revisione delle risposte di rifiuto; mostrare
all'utente le bozze; streaming.

## Anti-obiettivi
- Revisioni a vuoto su risposte corrette (severità eccessiva): ogni giro costa decine di secondi.
- Bozze rifiutate o indicazioni del revisore che restano nella cronologia dei turni successivi.
- Un turno che non finisce: il limite deve valere sempre.
- Il revisore che consuma i passaggi dell'agente fino a far scattare il limite di ricorsione del grafo.

## Comportamento

### Configurazione
- File `revisore.txt` (istruzioni del revisore, versionato), variabile facoltativa `REVISORE_FILE`; stessi controlli di
  `ambito.txt` (mancante, vuoto, non UTF-8 → errore chiaro e codice 1).
- `REVISIONI_MAX` facoltativa, intero ≥ 0 (default 2; 0 = il revisore approva senza giri); valore non valido → errore
  chiaro all'avvio.
- In Docker `revisore.txt` entra nell'immagine.

### Grafo
```
START → nodo_router ─conversazione→ nodo_llm ⇄ nodo_strumenti
                    └─fuori ambito→ nodo_rifiuto → END
nodo_llm (risposta senza richieste di strumenti) → nodo_revisore ─coerente / limite→ END
                                                                 └─non coerente→ nodo_llm (con l'indicazione)
```
- `nodo_revisore`: stesso modello senza strumenti, client senza ragionamento (come il router), prompt = `revisore.txt`;
  riceve la domanda dell'utente del turno e la risposta proposta. Output strutturato
  `{"coerente": true | false, "motivo": "<breve, in italiano>"}`.
  Log: `revisore: coerente (<motivo>)` / `revisore: non coerente (<motivo>), revisione 1 di 2` /
  `revisore: limite di revisioni raggiunto, si restituisce l'ultima risposta` (WARNING).
- Non coerente sotto il limite: alla cronologia del turno si aggiunge un'indicazione per l'agente con il motivo (per
  esempio «La risposta precedente non è completa: <motivo>. Riscrivi la risposta alla domanda dell'utente.»), poi di
  nuovo `nodo_llm`.
- Contatore delle revisioni nello stato, che riparte da zero a ogni turno.
- A fine turno la cronologia restituita contiene la domanda, gli eventuali messaggi degli strumenti e **solo la
  risposta approvata** (o l'ultima, al limite): bozze rifiutate e indicazioni vengono rimosse.
- Senza revisore configurato il grafo resta quello di oggi (i test esistenti restano validi). Il limite dei passaggi
  si alza quanto serve perché due revisioni non tolgano passaggi all'agente.

## Verifiche
- **Test senza modello**: revisore simulato che approva subito (una sola chiamata all'agente); che rifiuta una volta
  (due chiamate all'agente, la seconda riceve l'indicazione con il motivo, cronologia finale con la sola risposta
  approvata); che rifiuta sempre (al limite: ultima risposta, WARNING, numero di chiamate atteso); output illeggibile
  ed errore → approvazione con WARNING; rifiuto del router senza revisore; turno con strumenti seguito da revisione;
  configurazione (file, `REVISIONI_MAX` non valido).
- **Prove reali con gemma**: il revisore reale, chiamato su una domanda in due parti con una risposta parziale
  scritta dal test, la giudica non coerente con un motivo; una domanda in due parti al grafo completo («Quanti giorni
  mancano a Natale e che giorno della settimana sarà?») produce una risposta finale con entrambe le parti; una
  domanda semplice è approvata al primo passaggio; le prove esistenti ancora verdi.
- **Pipe** locale e **Docker**.

## Lasciato a chi costruisce
Testo di `revisore.txt` e dell'indicazione; come marcare e rimuovere bozze e indicazioni (per esempio un attributo sui
messaggi e la rimozione con gli identificativi); quanti passaggi aggiungere al limite.
