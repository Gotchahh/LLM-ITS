"""Interfaccia da terminale: ciclo di lettura, invocazione del grafo e stampa."""

import logging

from langgraph.errors import GraphRecursionError

from assistente.grafo import LIMITE_PASSAGGI, RispostaNonValida, esegui_turno

logger = logging.getLogger(__name__)

COMANDO_ESCI = "/esci"
TESTO_ATTESA = "Ragionando..."


class IndicatoreAttesa:
    """Scritta fissa mostrata durante l'attesa del modello e cancellata subito dopo."""

    def __init__(self, uscita):
        self.uscita = uscita
        self.visibile = False

    def mostra(self) -> None:
        """Scrive la scritta senza andare a capo."""
        self.uscita.write(TESTO_ATTESA)
        self.uscita.flush()
        self.visibile = True

    def nascondi(self) -> None:
        """Cancella la scritta (backspace, spazi, backspace); non fa nulla se non è visibile."""
        if not self.visibile:
            return
        n = len(TESTO_ATTESA)
        self.uscita.write("\b" * n + " " * n + "\b" * n)
        self.uscita.flush()
        self.visibile = False


def crea_indicatore_attesa(livello_log: str, ingresso, uscita) -> IndicatoreAttesa | None:
    """Restituisce l'indicatore solo con log silenziosi (WARNING o ERROR) e ingresso e uscita da terminale."""
    silenzioso = livello_log in ("WARNING", "ERROR")
    if silenzioso and ingresso.isatty() and uscita.isatty():
        return IndicatoreAttesa(uscita)
    return None


def esegui_chat(grafo, server: str, leggi=input, scrivi=print, attesa=None) -> None:
    """Legge le righe dell'utente, esegue un turno del grafo per ciascuna e stampa la risposta.

    La cronologia vive solo in questa funzione, per la durata della sessione. Un turno fallito
    stampa un errore e viene scartato: la cronologia resta com'era e la chat prosegue.
    Con un indicatore `attesa`, la scritta compare durante il turno e sparisce prima di ogni
    stampa successiva (risposta, errore o saluto dopo Ctrl+C).
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
                if attesa is not None:
                    attesa.mostra()
                try:
                    cronologia = esegui_turno(grafo, cronologia, riga)
                finally:
                    if attesa is not None:
                        attesa.nascondi()
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
