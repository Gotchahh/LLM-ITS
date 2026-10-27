"""Configurazione dell'applicazione: lettura e validazione delle variabili e dei log."""

import logging
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import dotenv_values

VARIABILE_URL = "LMSTUDIO_BASE_URL"
VARIABILE_MODELLO = "LMSTUDIO_MODEL"
VARIABILE_FUSO = "APP_TIMEZONE"
VARIABILE_LOG = "LOG_LEVEL"

OBBLIGATORIE = (VARIABILE_URL, VARIABILE_MODELLO, VARIABILE_FUSO)
LIVELLI_LOG = ("DEBUG", "INFO", "WARNING", "ERROR")
LIVELLO_LOG_PREDEFINITO = "INFO"
FORMATO_LOG = "[%(levelname)s] %(message)s"


class ErroreConfigurazione(ValueError):
    """Configurazione mancante o non valida; il messaggio spiega come correggerla."""


@dataclass(frozen=True)
class Configurazione:
    base_url: str
    modello: str
    fuso: ZoneInfo
    livello_log: str


def leggi_file_env(percorso: Path) -> dict[str, str]:
    """Legge un file `.env` (anche con BOM e fine riga Windows); `{}` se il file non esiste."""
    if not percorso.is_file():
        return {}
    valori = dotenv_values(percorso, encoding="utf-8-sig")
    return {chiave: valore for chiave, valore in valori.items() if valore is not None}


def carica_configurazione(ambiente: Mapping[str, str]) -> Configurazione:
    """Valida le variabili d'ambiente e costruisce la configurazione.

    Gli spazi ai bordi sono tolti e un valore vuoto equivale a una variabile mancante.
    """
    valori = {nome: ambiente.get(nome, "").strip() for nome in (*OBBLIGATORIE, VARIABILE_LOG)}

    mancanti = [nome for nome in OBBLIGATORIE if not valori[nome]]
    if mancanti:
        raise ErroreConfigurazione(
            f"Variabili di configurazione mancanti: {', '.join(mancanti)}. "
            "Copiare .env.example in .env e compilarlo (Copy-Item .env.example .env)."
        )

    base_url = valori[VARIABILE_URL].rstrip("/")
    indirizzo = urlparse(base_url)
    if indirizzo.scheme not in ("http", "https") or not indirizzo.netloc:
        raise ErroreConfigurazione(
            f"{VARIABILE_URL} non è un indirizzo valido: «{valori[VARIABILE_URL]}». "
            "Serve lo schema, per esempio http://localhost:1234/v1."
        )

    try:
        fuso = ZoneInfo(valori[VARIABILE_FUSO])
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise ErroreConfigurazione(
            f"{VARIABILE_FUSO} non è un fuso orario IANA valido: «{valori[VARIABILE_FUSO]}». "
            "Esempio: Europe/Rome."
        ) from None

    livello_log = (valori[VARIABILE_LOG] or LIVELLO_LOG_PREDEFINITO).upper()
    if livello_log not in LIVELLI_LOG:
        raise ErroreConfigurazione(
            f"{VARIABILE_LOG} non è valido: «{valori[VARIABILE_LOG]}». "
            f"Valori ammessi: {', '.join(LIVELLI_LOG)}."
        )

    return Configurazione(
        base_url=base_url,
        modello=valori[VARIABILE_MODELLO],
        fuso=fuso,
        livello_log=livello_log,
    )


def configura_log(livello: str) -> None:
    """Invia i log su stderr; solo il logger `assistente` segue `livello`, gli altri restano a WARNING."""
    logging.basicConfig(level=logging.WARNING, format=FORMATO_LOG, stream=sys.stderr, force=True)
    logging.getLogger("assistente").setLevel(livello)
