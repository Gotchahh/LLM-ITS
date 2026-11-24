"""Router dell'ambito: schema della decisione, messaggi da classificare, lettura della decisione, rifiuto.

Il prompt del router è il testo dell'ambito (file di configurazione, vedi `config.leggi_ambito`).
"""

import logging

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage

logger = logging.getLogger(__name__)

CATEGORIE = ("conversazione", "fuori_ambito")
MESSAGGI_AL_ROUTER = 6
MOTIVO_ILLEGGIBILE = "decisione del router illeggibile"
INIZIO_RIFIUTO = "Posso aiutarti solo con domande scientifiche o sul laboratorio"

SCHEMA_ROUTER = {
    "title": "decisione_router",
    "description": "Classificazione dell'ultima domanda dell'utente",
    "type": "object",
    "properties": {
        "categoria": {"type": "string", "enum": list(CATEGORIE)},
        "motivo": {"type": "string", "description": "al massimo 8 parole, in italiano"},
    },
    "required": ["categoria", "motivo"],
}


def messaggi_per_il_router(cronologia: list[AnyMessage]) -> list[AnyMessage]:
    """Gli ultimi messaggi utili a classificare: domande e risposte testuali, senza richieste e risultati di strumenti."""
    testuali = [
        m for m in cronologia
        if isinstance(m, HumanMessage) or (isinstance(m, AIMessage) and not m.tool_calls and m.text.strip())
    ]
    return testuali[-MESSAGGI_AL_ROUTER:]


def leggi_decisione(risultato: dict) -> tuple[str, str]:
    """(categoria, motivo) dall'output strutturato; se non è conforme, la domanda passa all'agente."""
    decisione = risultato.get("parsed")
    if (
        risultato.get("parsing_error") is None
        and isinstance(decisione, dict)
        and decisione.get("categoria") in CATEGORIE
        and isinstance(decisione.get("motivo"), str)
    ):
        return decisione["categoria"], decisione["motivo"].strip()
    logger.warning("router: decisione illeggibile, la domanda passa all'agente")
    return "conversazione", MOTIVO_ILLEGGIBILE


def testo_rifiuto(motivo: str) -> str:
    """«Posso aiutarti solo con domande scientifiche o sul laboratorio: <motivo>.»"""
    return f"{INIZIO_RIFIUTO}: {motivo.strip().rstrip('.')}."
