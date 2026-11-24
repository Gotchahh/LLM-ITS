"""Preferenze dell'utente lette dalla resource MCP: controlli campo per campo, predefiniti e blocco del prompt.

Il server passa il testo senza controllarlo; qui ogni campo mancante o non valido prende il suo predefinito con un
WARNING, e un testo inutilizzabile (o un server che non risponde) dà tutti i predefiniti: l'avvio non si ferma mai.
"""

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from assistente.client_mcp import URI_PREFERENZE, ErroreMCP

logger = logging.getLogger(__name__)

LINGUA_PREDEFINITA = "italiano"
STILI = {
    "sintetico": "Stile: risposte brevi ed essenziali, senza tralasciare nulla di ciò che la domanda chiede.",
    "dettagliato": "Stile: risposte dettagliate, con spiegazioni ed esempi quando aiutano, senza uscire dalla domanda.",
}


@dataclass(frozen=True)
class Preferenze:
    """Preferenze controllate: lingua delle risposte, fuso orario predefinito, stile (`None`: nessuna istruzione)."""

    lingua: str
    fuso: ZoneInfo
    stile: str | None


def predefinite(fuso: ZoneInfo) -> Preferenze:
    """Le preferenze usate quando la resource manca: italiano, il fuso del programma, nessuno stile."""
    return Preferenze(LINGUA_PREDEFINITA, fuso, None)


def _lingua(valore: object) -> str | None:
    if isinstance(valore, str) and valore.strip():
        return valore.strip()
    return None


def _fuso(valore: object) -> ZoneInfo | None:
    if not isinstance(valore, str) or not valore.strip():
        return None
    try:
        return ZoneInfo(valore.strip())
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return None


def _stile(valore: object) -> str | None:
    if isinstance(valore, str) and valore.strip().lower() in STILI:
        return valore.strip().lower()
    return None


def leggi_preferenze(testo: str, fuso_predefinito: ZoneInfo) -> Preferenze:
    """Preferenze dal testo JSON della resource; campo mancante o non valido → predefinito con un WARNING.

    Solleva `ValueError` con il motivo se il testo non è JSON o non è un oggetto. I campi in più si ignorano.
    """
    try:
        dati = json.loads(testo)
    except json.JSONDecodeError as errore:
        raise ValueError(f"JSON non valido: {errore.msg}") from None
    if not isinstance(dati, dict):
        raise ValueError("il JSON non è un oggetto")
    base = predefinite(fuso_predefinito)
    campi = (
        ("lingua", _lingua, base.lingua, base.lingua),
        ("fuso", _fuso, base.fuso, base.fuso.key),
        ("stile", _stile, base.stile, "nessuno stile"),
    )
    valori = {}
    for campo, controlla, predefinito, descrizione in campi:
        if campo not in dati:
            logger.warning("preferenze: %s mancante, si usa %s", campo, descrizione)
            valori[campo] = predefinito
            continue
        valore = controlla(dati[campo])
        if valore is None:
            logger.warning(
                "preferenze: %s non valido («%s»), si usa %s",
                campo,
                json.dumps(dati[campo], ensure_ascii=False),
                descrizione,
            )
            valore = predefinito
        valori[campo] = valore
    return Preferenze(**valori)


def carica_preferenze(leggi: Callable[[], str], fuso_predefinito: ZoneInfo) -> Preferenze:
    """Legge la resource con `leggi` e ne controlla il testo; scrive la riga della lettura nel log.

    Server che non risponde, resource illeggibile o testo inutilizzabile: WARNING e preferenze predefinite.
    """
    inizio = time.perf_counter()
    try:
        preferenze = leggi_preferenze(leggi(), fuso_predefinito)
    except (ErroreMCP, ValueError) as errore:
        logger.warning("preferenze: resource non disponibile (%s), valori predefiniti", errore)
        return predefinite(fuso_predefinito)
    logger.info(
        "preferenze: resource %s letta in %.1f s: lingua=%s, fuso=%s, stile=%s",
        URI_PREFERENZE,
        time.perf_counter() - inizio,
        preferenze.lingua,
        preferenze.fuso.key,
        preferenze.stile or "nessuno",
    )
    return preferenze


def blocco_preferenze(preferenze: Preferenze) -> str:
    """Le frasi da mettere in cima al prompt dell'agente: lingua, fuso predefinito e, se c'è, stile."""
    fuso = preferenze.fuso.key
    # Prove del 18/11/2026 con gemma: «chiama ora_corrente con fuso X» veniva ignorato (fuso omesso, come dice la
    # descrizione dello strumento); «passa sempre l'argomento fuso="X" (non ometterlo)» viene seguito, e con una
    # città nominata il modello usa ancora il fuso di quella città.
    blocco = (
        f"Preferenze dell'utente: rispondi sempre in {preferenze.lingua}. "
        f"L'utente vive nel fuso orario {fuso}: ogni volta che chiami ora_corrente senza che l'utente abbia "
        f"nominato un'altra città, passa sempre l'argomento fuso=\"{fuso}\" (non ometterlo)."
    )
    if preferenze.stile is not None:
        blocco += " " + STILI[preferenze.stile]
    return blocco
