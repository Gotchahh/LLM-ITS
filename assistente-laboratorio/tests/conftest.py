"""Valori e aiuti condivisi dai test."""

from assistente.cli import esegui_chat

VALIDO = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "google/gemma-4-e4b",
          "APP_TIMEZONE": "Europe/Rome"}

SERVER_FINTO = "http://server/v1"


class ModelloFinto:
    """Modello simulato: restituisce o solleva, nell'ordine, le voci di `risposte`.

    Registra i messaggi di ogni chiamata in `chiamate` e gli strumenti di ogni `bind_tools`
    in `strumenti_associati`.
    """

    def __init__(self, risposte):
        self.risposte = list(risposte)
        self.chiamate = []
        self.strumenti_associati = []

    def bind_tools(self, strumenti):
        self.strumenti_associati.append(strumenti)
        return self

    def invoke(self, messaggi):
        self.chiamate.append(list(messaggi))
        voce = self.risposte.pop(0)
        if isinstance(voce, BaseException):
            raise voce
        return voce


class AttesaFinta:
    """Indicatore di attesa simulato: registra `[mostra]` e `[nascondi]` tra le righe stampate."""

    def __init__(self, stampato):
        self.stampato = stampato

    def mostra(self):
        self.stampato.append("[mostra]")

    def nascondi(self):
        self.stampato.append("[nascondi]")


def chat(grafo, righe, con_attesa=False):
    """Esegue la chat con le `righe` date (poi fine input) e restituisce le stringhe stampate.

    Con `con_attesa=True` usa un indicatore di attesa finto, che scrive nella stessa lista.
    """
    da_leggere = list(righe)
    stampato = []

    def leggi(_invito):
        if not da_leggere:
            raise EOFError
        return da_leggere.pop(0)

    attesa = AttesaFinta(stampato) if con_attesa else None
    esegui_chat(grafo, SERVER_FINTO, leggi=leggi, scrivi=stampato.append, attesa=attesa)
    return stampato
