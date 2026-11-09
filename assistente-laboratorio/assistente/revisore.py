"""Revisore della risposta: schema della valutazione, messaggi per il revisore, indicazione per l'agente.

Le istruzioni del revisore sono un file di configurazione (vedi `config.leggi_revisore`).
"""

import logging
from uuid import uuid4

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

MARCA_INDICAZIONE = "indicazione_revisore"
MOTIVO_ILLEGGIBILE = "valutazione illeggibile"

SCHEMA_REVISORE = {
    "title": "valutazione_revisore",
    "description": "Valutazione della risposta proposta rispetto alla domanda dell'utente",
    "type": "object",
    "properties": {
        "coerente": {"type": "boolean"},
        "motivo": {"type": "string", "description": "al massimo 12 parole, in italiano"},
    },
    "required": ["coerente", "motivo"],
}


def e_indicazione(messaggio: AnyMessage) -> bool:
    """Vero se il messaggio è un'indicazione del revisore per l'agente (da togliere a fine turno)."""
    return bool(messaggio.additional_kwargs.get(MARCA_INDICAZIONE))


def ultima_domanda(cronologia: list[AnyMessage]) -> str:
    """Testo dell'ultima domanda dell'utente, saltando le indicazioni del revisore."""
    for messaggio in reversed(cronologia):
        if isinstance(messaggio, HumanMessage) and not e_indicazione(messaggio):
            return messaggio.text
    return ""


def messaggi_per_il_revisore(istruzioni: str, domanda: str, risposta: str) -> list[AnyMessage]:
    """Prompt del revisore: le istruzioni e un solo messaggio con domanda e risposta proposta."""
    return [
        SystemMessage(istruzioni),
        HumanMessage(f"Domanda dell'utente:\n{domanda}\n\nRisposta proposta:\n{risposta}"),
    ]


def leggi_valutazione(risultato: dict) -> tuple[bool, str]:
    """(coerente, motivo) dall'output strutturato; se non è conforme, la risposta è approvata."""
    valutazione = risultato.get("parsed")
    if (
        risultato.get("parsing_error") is None
        and isinstance(valutazione, dict)
        and isinstance(valutazione.get("coerente"), bool)
        and isinstance(valutazione.get("motivo"), str)
    ):
        return valutazione["coerente"], valutazione["motivo"].strip()
    logger.warning("revisore: valutazione illeggibile, la risposta è approvata")
    return True, MOTIVO_ILLEGGIBILE


def indicazione(motivo: str, domanda: str) -> HumanMessage:
    """Indicazione per l'agente con il motivo del rifiuto, marcata e con un identificativo per poterla togliere."""
    testo = (
        f"Revisione: la risposta precedente non va bene: {motivo.strip().rstrip('.')}. "
        f"Riscrivi la risposta alla domanda dell'utente: «{domanda}»."
    )
    return HumanMessage(testo, id=str(uuid4()), additional_kwargs={MARCA_INDICAZIONE: True})
