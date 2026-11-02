"""Interfaccia da terminale: ciclo di lettura, invocazione del grafo e stampa."""

import logging

from langgraph.errors import GraphRecursionError

from assistente.config import LIVELLO_LOG_PREDEFINITO, ModalitaLog
from assistente.grafo import LIMITE_PASSAGGI, RispostaNonValida, esegui_turno

logger = logging.getLogger(__name__)

COMANDO_ESCI = "/esci"
COMANDO_LOG = "/log"
MESSAGGIO_LOG_VISIBILI = "Log visibili. Scrivi /log per nasconderli."
MESSAGGIO_LOG_NASCOSTI = "Log nascosti: solo dialogo. Scrivi /log per mostrarli."
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


def crea_indicatore_attesa(ingresso, uscita) -> IndicatoreAttesa | None:
    """Restituisce l'indicatore solo se ingresso e uscita sono un terminale."""
    if ingresso.isatty() and uscita.isatty():
        return IndicatoreAttesa(uscita)
    return None


def prepara_terminale(*flussi) -> None:
    """Fa usare UTF-8 ai flussi che non sono un terminale (pipe, redirect), senza errori di codifica.

    Su Windows pipe e file usano la codifica ANSI (cp1252), mentre PowerShell, impostato come nel README,
    scambia UTF-8: «è» diventerebbe «Ã¨», il BOM «ï»¿» e un'emoji nella risposta interromperebbe la sessione.
    I byte non decodificabili in ingresso diventano U+FFFD e i caratteri non codificabili in uscita «?».
    I terminali veri (tastiera e schermo, anche nel container) restano come sono.
    """
    for flusso in flussi:
        if not flusso.isatty():
            flusso.reconfigure(encoding="utf-8", errors="replace")


def esegui_chat(grafo, server: str, leggi=input, scrivi=print, attesa=None,
                livello_log: str = LIVELLO_LOG_PREDEFINITO) -> None:
    """Legge le righe dell'utente, esegue un turno del grafo per ciascuna e stampa la risposta.

    La cronologia vive solo in questa funzione, per la durata della sessione. Un turno fallito
    stampa un errore e viene scartato: la cronologia resta com'era e la chat prosegue.
    `/log` alterna log visibili e nascosti, a partire dalla modalità di `livello_log`.
    Con un indicatore `attesa` e i log nascosti, la scritta compare durante il turno e sparisce
    prima di ogni stampa successiva (risposta, errore o saluto dopo Ctrl+C).
    Termina con `/esci`, a fine input o con Ctrl+C.
    """
    cronologia = []
    modalita_log = ModalitaLog(livello_log)
    try:
        while True:
            # La pipe di PowerShell può anteporre uno o due BOM (U+FEFF), che strip() non considera spazio.
            riga = leggi("Tu> ").lstrip("\ufeff").strip()
            if not riga:
                continue
            if riga.startswith("/"):
                comando = riga.lower()
                if comando == COMANDO_ESCI:
                    break
                if comando == COMANDO_LOG:
                    visibili = modalita_log.alterna()
                    scrivi(MESSAGGIO_LOG_VISIBILI if visibili else MESSAGGIO_LOG_NASCOSTI)
                else:
                    scrivi(f"Comando sconosciuto. Comandi disponibili: {COMANDO_ESCI}, {COMANDO_LOG}")
                continue
            # La scritta di attesa si decide a ogni turno, quindi segue i cambi fatti con /log.
            usa_attesa = attesa is not None and not modalita_log.visibili
            try:
                if usa_attesa:
                    attesa.mostra()
                try:
                    cronologia = esegui_turno(grafo, cronologia, riga)
                finally:
                    if usa_attesa:
                        attesa.nascondi()
            except GraphRecursionError:
                scrivi(f"Errore: limite di {LIMITE_PASSAGGI} passaggi raggiunto. Turno annullato.")
            except RispostaNonValida:
                scrivi("Errore: il modello non ha prodotto una risposta valida. Turno annullato.")
            except Exception as errore:
                logger.debug("Dettaglio dell'errore del turno", exc_info=True)
                dettaglio = str(errore).removesuffix(".")   # i messaggi del client finiscono già con un punto
                scrivi(
                    f"Errore: nessuna risposta valida da LM Studio ({server}): "
                    f"{type(errore).__name__}: {dettaglio}. Turno annullato."
                )
            else:
                scrivi(f"Assistente> {cronologia[-1].text}")
    except (EOFError, KeyboardInterrupt):
        pass
    scrivi("Alla prossima!")
