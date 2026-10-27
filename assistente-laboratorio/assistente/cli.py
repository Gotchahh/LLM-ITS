"""Interfaccia da terminale: ciclo di lettura, invocazione del grafo e stampa."""

import logging

from langgraph.errors import GraphRecursionError

from assistente.grafo import LIMITE_PASSAGGI, RispostaNonValida, esegui_turno

logger = logging.getLogger(__name__)

COMANDO_ESCI = "/esci"


def esegui_chat(grafo, server: str, leggi=input, scrivi=print) -> None:
    """Legge le righe dell'utente, esegue un turno del grafo per ciascuna e stampa la risposta.

    La cronologia vive solo in questa funzione, per la durata della sessione. Un turno fallito
    stampa un errore e viene scartato: la cronologia resta com'era e la chat prosegue.
    Termina con `/esci`, a fine input o con Ctrl+C.
    """
    cronologia = []
    try:
        while True:
            # La pipe di PowerShell può anteporre un BOM (U+FEFF), che strip() non considera spazio.
            riga = leggi("Tu> ").removeprefix("\ufeff").strip()
            if not riga:
                continue
            if riga.startswith("/"):
                if riga.lower() == COMANDO_ESCI:
                    break
                scrivi(f"Comando sconosciuto. Comandi disponibili: {COMANDO_ESCI}")
                continue
            try:
                cronologia = esegui_turno(grafo, cronologia, riga)
            except GraphRecursionError:
                scrivi(f"Errore: limite di {LIMITE_PASSAGGI} passaggi raggiunto. Turno annullato.")
            except RispostaNonValida:
                scrivi("Errore: il modello non ha prodotto una risposta valida. Turno annullato.")
            except Exception as errore:
                logger.debug("Dettaglio dell'errore del turno", exc_info=True)
                scrivi(
                    f"Errore: nessuna risposta valida da LM Studio ({server}): "
                    f"{type(errore).__name__}: {errore}. Turno annullato."
                )
            else:
                scrivi(f"Assistente> {cronologia[-1].text}")
    except (EOFError, KeyboardInterrupt):
        pass
    scrivi("Alla prossima!")
