"""Valori e aiuti condivisi dai test."""

import io
import logging
import socket
import threading
import time

import pytest
import uvicorn

from assistente.cli import esegui_chat
from note_api.server import crea_app

VALIDO = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "google/gemma-4-e4b",
          "APP_TIMEZONE": "Europe/Rome"}

SERVER_FINTO = "http://server/v1"


@pytest.fixture(autouse=True)
def livello_log_app_ripristinato():
    """Rimette il livello del logger `assistente` com'era: il comando `/log` lo cambia davvero."""
    logger_app = logging.getLogger("assistente")
    livello = logger_app.level
    yield
    logger_app.setLevel(livello)


class FlussoDiTesto(io.TextIOWrapper):
    """Flusso di testo su byte, con la codifica cp1252 che Windows usa per pipe e file.

    `contenuto` sono i byte da leggere; dopo le scritture i byte emessi sono in `buffer.getvalue()`.
    Con `interattivo=True` si dichiara un terminale.
    """

    def __init__(self, contenuto: bytes = b"", interattivo: bool = False):
        super().__init__(io.BytesIO(contenuto), encoding="cp1252", errors="strict", newline="\n")
        self.interattivo = interattivo

    def isatty(self):
        return self.interattivo


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


def chat(grafo, righe, con_attesa=False, livello_log="INFO"):
    """Esegue la chat con le `righe` date (poi fine input) e restituisce le stringhe stampate.

    Con `con_attesa=True` usa un indicatore di attesa finto, che scrive nella stessa lista.
    `livello_log` è il livello d'avvio dei log, da cui dipende la modalità iniziale di `/log`.
    """
    da_leggere = list(righe)
    stampato = []

    def leggi(_invito):
        if not da_leggere:
            raise EOFError
        return da_leggere.pop(0)

    attesa = AttesaFinta(stampato) if con_attesa else None
    esegui_chat(grafo, SERVER_FINTO, leggi=leggi, scrivi=stampato.append, attesa=attesa,
                livello_log=livello_log)
    return stampato


def porta_libera() -> int:
    """Una porta TCP locale libera in questo momento."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def servizio_note(tmp_path_factory):
    """Servizio delle note vero (uvicorn in un thread) su un DB temporaneo; restituisce l'URL."""
    porta = porta_libera()
    percorso = tmp_path_factory.mktemp("note") / "note.db"
    server = uvicorn.Server(uvicorn.Config(crea_app(percorso), host="127.0.0.1", port=porta, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    limite = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > limite:
            raise RuntimeError("il servizio delle note di prova non è partito")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{porta}"
    server.should_exit = True
    thread.join(timeout=10)
