"""Collegamento al modello servito da LM Studio e controllo all'avvio."""

import json
import urllib.error
import urllib.request
from http.client import HTTPException

from langchain_openai import ChatOpenAI

from assistente.config import Configurazione, ErroreConfigurazione

CHIAVE_API = "lm-studio"  # segnaposto: LM Studio non controlla la chiave, ma il client ne vuole una
TIMEOUT_CONTROLLO = 5.0
TIMEOUT_MODELLO = 180.0


class ErroreServer(RuntimeError):
    """Il server di LM Studio non risponde o risponde in modo inatteso."""


def estrai_identificativi(corpo: bytes) -> list[str]:
    """Estrae gli identificativi (`data[].id`) dalla risposta JSON di `GET /v1/models`."""
    try:
        return [elemento["id"] for elemento in json.loads(corpo)["data"]]
    except (ValueError, KeyError, TypeError):
        raise ErroreServer("la risposta non è un elenco di modelli in formato JSON") from None


def leggi_modelli_disponibili(base_url: str, timeout: float = TIMEOUT_CONTROLLO) -> list[str]:
    """Chiede a LM Studio l'elenco dei modelli; se il server non risponde solleva `ErroreServer`."""
    url = f"{base_url}/models"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as risposta:
            corpo = risposta.read()
    except (OSError, HTTPException) as errore:  # include URLError, HTTPError e i timeout
        motivo = errore.reason if isinstance(errore, urllib.error.URLError) else errore
        raise ErroreServer(
            f"Impossibile leggere l'elenco dei modelli da {url}: {motivo}. "
            "Avviare il server locale in LM Studio e controllare LMSTUDIO_BASE_URL."
        ) from errore
    try:
        return estrai_identificativi(corpo)
    except ErroreServer as errore:
        raise ErroreServer(f"Risposta inattesa da {url}: {errore}.") from errore


def verifica_modello(modello: str, disponibili: list[str]) -> None:
    """Controlla che `modello` sia tra gli identificativi del server; altrimenti li elenca."""
    if modello not in disponibili:
        elenco = ", ".join(disponibili) or "nessuno"
        raise ErroreConfigurazione(
            f"Il modello «{modello}» non è disponibile in LM Studio. "
            f"Modelli disponibili: {elenco}. "
            "Impostare LMSTUDIO_MODEL in .env con uno di questi identificativi."
        )


def crea_modello(config: Configurazione) -> ChatOpenAI:
    """Crea il client del modello: temperatura 0, un solo nuovo tentativo, timeout lungo."""
    return ChatOpenAI(
        model=config.modello,
        base_url=config.base_url,
        api_key=CHIAVE_API,
        temperature=0,
        timeout=TIMEOUT_MODELLO,
        max_retries=1,
    )
