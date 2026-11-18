# Riassunto della cronologia — specifica di design (Lezione 6, step 3)

> Stato: approvata dall'utente il 17/11/2026. Branch `feature/riassunto`, nato da `dev` (`6d7956a`, con router e revisore).

## Intento e perché
Con un modello locale il contesto è limitato e ogni turno aggiunge messaggi (domande, risposte, richieste e
risultati degli strumenti). Su una conversazione lunga il prompt cresce, le risposte rallentano e alla fine il
contesto si satura. Un **nodo LLM all'inizio del turno**, il riassunto, sostituisce i messaggi più vecchi con un
riassunto e lascia intatti gli ultimi turni, così la conversazione resta utilizzabile su molti turni senza perdere
le informazioni importanti (per esempio il nome dell'utente detto al primo turno). È lo step 3 (avanzato) della
Lezione 6; l'utente ha chiesto di partire direttamente dalle slide, quindi le decisioni sotto sono dell'assistente
salvo dove indicato.

## Modifiche dopo le prove reali (17/11/2026, confermate dall'utente lo stesso giorno)
Le prove con gemma hanno portato a tre scostamenti da quanto approvato; le parti sotto restano come approvate:
1. **Come l'agente riceve il riassunto**: non in coda al prompt di sistema ma come primo messaggio della conversazione
   (un messaggio dell'utente subito dopo il prompt di sistema, solo nella chiamata, non nella cronologia). Con tutti gli
   strumenti, in coda o in testa al prompt gemma ignorava il riassunto (0 su 4); in un secondo messaggio di sistema
   smetteva di chiamare gli strumenti (0 su 3); come primo messaggio chiamava gli strumenti (3 su 3) e usava il nome
   (2 su 2). Il router lo riceve ancora in coda al suo prompt; il revisore no.
2. **Client dedicato al riassunto**: senza ragionamento come quello del router, ma con un tetto di 400 token invece di
   80, che troncherebbe un riassunto di qualche riga. Un riassunto troncato comunque (`finish_reason` «length») è
   trattato come un errore: cronologia invariata, WARNING `riassunto: risposta troncata, cronologia invariata`.
3. **`riassunto.txt` con un esempio**: con regole generiche gemma scriveva «si è presentato dicendo il suo nome»
   senza il nome, oppure copiava l'orario; un esempio unico (nome per esteso, ora senza valore) risolve entrambe.

## Requisiti delle slide (pag. 6 e 19)
1. Soglia configurabile, in numero di messaggi o stima dei token, oltre la quale si riassume.
2. Nodo riassunto all'inizio del turno: comprime i messaggi vecchi e conserva gli ultimi N.
3. Il riassunto è un **campo dello stato** che viene aggiornato, non accumulato.
4. Il taglio non separa mai una richiesta di strumento dal relativo `ToolMessage`.

Evidenze richieste: log con il numero di messaggi prima e dopo il riassunto; un'informazione data al primo turno
(il nome dell'utente) usata dopo la compressione; sotto la soglia il nodo non chiama il modello.

## Decisioni (dell'assistente, da confermare con l'approvazione)
- **Soglia in numero di messaggi** (non stima dei token): è deterministica, si testa senza modello e si legge nei
  log. Contano tutti i messaggi della cronologia, compresa la domanda del turno e i messaggi degli strumenti.
  Variabile `RIASSUNTO_SOGLIA`, intero ≥ 1, default **20**; «supera» vuol dire strettamente maggiore (con 20
  messaggi non si riassume, con 21 sì).
- **Si conservano gli ultimi N turni interi**, contati come turni (un turno = una domanda dell'utente con tutto ciò
  che la segue fino alla domanda successiva), oltre alla domanda del turno in corso. Variabile `RIASSUNTO_TURNI`,
  intero ≥ 1, default **2**. Tagliando solo all'inizio di un turno (prima di una domanda dell'utente) il requisito 4
  è garantito per costruzione: richieste e risultati degli strumenti stanno sempre nello stesso turno.
- Il nodo chiama il modello **solo se** la cronologia supera la soglia **e** ci sono messaggi più vecchi degli
  ultimi N turni; altrimenti non fa nulla (nessuna chiamata, log a livello DEBUG).
- **Il riassunto sostituisce il precedente**: il modello riceve il riassunto precedente (se c'è) più i messaggi da
  togliere e scrive un nuovo riassunto unico, che prende il posto del vecchio nel campo `riassunto` dello stato. I
  messaggi riassunti vengono tolti dalla cronologia.
- **Dove si usa il riassunto** (per l'agente superato dalla modifica 1: lo riceve come primo messaggio della
  conversazione): l'agente lo riceve in coda al prompt di sistema (per esempio «Riassunto della
  conversazione precedente: …»). Anche il router lo riceve in coda al suo prompt, così una domanda di seguito che
  si riferisce a qualcosa ormai riassunto non viene scambiata per fuori ambito. Il revisore no: giudica solo domanda
  e risposta del turno.
- Stesso modello di LM Studio, client **senza ragionamento** (come router e revisore; client dedicato con 400 token
  per la modifica 2), **output testuale libero**
  (non strutturato). Istruzioni in un file di configurazione **`riassunto.txt`** (versionato, variabile facoltativa
  `RIASSUNTO_FILE`), con gli stessi controlli di `ambito.txt`.
- Il riassunto conserva le informazioni stabili (chi è l'utente, preferenze, decisioni prese, note e apparecchi di
  cui si è parlato, domande lasciate aperte) e **non** i risultati che invecchiano, come l'ora corrente: per quelli
  l'agente deve richiamare lo strumento.
- **Errore, risposta vuota o troncata (modifica 2) del riassunto → nessuna compressione**: la cronologia e il riassunto precedente restano
  come sono, WARNING nel log, il turno prosegue (stesso principio di router e revisore: un nodo ausiliario che
  fallisce non blocca la risposta).
- **Il riassunto vive solo per la sessione**, come la cronologia: la CLI lo conserva tra un turno e l'altro insieme
  alla cronologia; un turno fallito lascia entrambi com'erano. Nessuna persistenza.

## Obiettivi
1. Conversazione lunga: superata la soglia, il log mostra `riassunto: N messaggi -> M` e il prompt dell'agente
   resta limitato.
2. Il nome dato al primo turno viene usato correttamente dopo la compressione.
3. Sotto la soglia il modello del riassunto non viene chiamato.
4. Nessun taglio separa una richiesta di strumento dal suo `ToolMessage`.
5. Nulla si rompe: router, revisore, strumenti, `/log`, prove reali esistenti.

## Non-obiettivi
Resource e prompt MCP e gli step successivi; stima dei token; comandi della CLI per vedere o azzerare il
riassunto; persistenza tra sessioni; riassunto incrementale a ogni turno sotto la soglia.

## Anti-obiettivi
- Un riassunto che si accumula (riassunto del riassunto aggiunto in coda ogni volta) invece di essere sostituito.
- Una richiesta di strumento separata dal suo `ToolMessage`: l'API la rifiuterebbe.
- Il riassunto chiamato a ogni turno anche sotto la soglia (costa secondi per niente).
- Un errore del riassunto che fa perdere messaggi o annulla il turno.
- Informazioni vecchie e superate (l'ora di tre turni fa) presentate dall'agente come attuali.

## Comportamento

### Configurazione
- `riassunto.txt` (istruzioni del riassunto) e variabile facoltativa `RIASSUNTO_FILE`; mancante, vuoto, non UTF-8 →
  errore chiaro all'avvio e codice 1.
- `RIASSUNTO_SOGLIA` (default 20) e `RIASSUNTO_TURNI` (default 2) facoltative, interi ≥ 1; valore non valido →
  errore chiaro all'avvio che nomina la variabile.
- `.env.example` e README aggiornati; in Docker `riassunto.txt` entra nell'immagine.

### Grafo
```
START → nodo_riassunto → nodo_router ─in ambito→ nodo_llm ⇄ nodo_strumenti
                                     └─fuori ambito→ nodo_rifiuto → END
nodo_llm (risposta senza strumenti) → nodo_revisore → … (invariato)
```
- Lo stato guadagna il campo `riassunto` (testo, vuoto finché non serve), che a differenza dei campi del turno
  (revisioni, bozze) **passa da un turno all'altro**.
- `nodo_riassunto`:
  - conta i messaggi; sotto la soglia, o se non c'è nulla oltre gli ultimi N turni, restituisce senza modifiche;
  - altrimenti divide la cronologia all'inizio del turno che precede di N quello corrente: i messaggi prima del taglio
    sono quelli da riassumere;
  - manda al modello le istruzioni, il riassunto precedente e i messaggi da riassumere **trascritti come testo**
    (per esempio «Utente: …», «Assistente: …», «Strumento ora_corrente: …»), così il modello senza strumenti non
    riceve richieste di strumento grezze;
  - aggiorna `riassunto` e toglie i messaggi riassunti dalla cronologia;
  - log: `riassunto: 24 messaggi -> 7 in 8.1 s` (INFO); sotto la soglia `riassunto: 12 messaggi, sotto la soglia di
    20` (DEBUG); errore `riassunto: errore (<tipo>), cronologia invariata` (WARNING).
- Il limite dei passaggi del grafo cresce di quanto serve per il nuovo nodo.
- Senza riassunto configurato il grafo resta quello di oggi (i test esistenti restano validi).

### CLI
- Oltre alla cronologia conserva il riassunto e li passa entrambi al turno successivo; il grafo li restituisce
  entrambi. Un turno fallito non cambia né l'una né l'altro. Nient'altro cambia per l'utente.

## Verifiche
- **Test senza modello** (modello del riassunto simulato):
  - sotto la soglia: nessuna chiamata al modello del riassunto, cronologia invariata;
  - sopra la soglia: una chiamata; i messaggi vecchi tolti, gli ultimi N turni e la domanda intatti; `riassunto`
    aggiornato; log con prima e dopo;
  - secondo riassunto: il modello riceve il riassunto precedente e il nuovo **sostituisce** il vecchio;
  - turni con strumenti: dopo il taglio nessuna richiesta di strumento senza il suo `ToolMessage` e nessun
    `ToolMessage` orfano;
  - sopra la soglia ma con meno di N+1 turni: nessuna chiamata;
  - errore, testo vuoto e risposta troncata del modello: cronologia e riassunto invariati, WARNING, il turno
    prosegue;
  - il router riceve il riassunto nel prompt di sistema, l'agente come primo messaggio della conversazione
    (modifica 1); il revisore no;
  - CLI: il riassunto passa da un turno all'altro e resta invariato dopo un turno fallito;
  - configurazione: file mancante o vuoto, `RIASSUNTO_SOGLIA` e `RIASSUNTO_TURNI` non validi.
- **Prove reali con gemma** (soglia bassa impostata dal test): al primo turno l'utente dice il proprio nome, poi
  alcuni turni (anche con strumenti) fino a superare la soglia; il log mostra la compressione e alla domanda «Come
  mi chiamo?» la risposta contiene il nome; il riassunto reale, chiamato direttamente su una cronologia scritta dal
  test, contiene il nome. Le prove esistenti restano verdi.
- **Pipe** locale e **Docker**.

## Lasciato a chi costruisce
Testo di `riassunto.txt` e della frase che introduce il riassunto nei prompt; formato della trascrizione; come
passare il riassunto tra CLI e grafo (firma di `esegui_turno`); di quanto alzare il limite dei passaggi.
