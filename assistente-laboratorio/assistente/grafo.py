"""Grafo LangGraph dell'assistente: stato, nodi e collegamenti."""

import logging
import time
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

logger = logging.getLogger(__name__)

LIMITE_PASSAGGI = 10

PROMPT_DI_SISTEMA = (
    "Sei l'assistente del laboratorio e rispondi sempre in italiano. "
    "Per l'ora, la data o il giorno attuali chiama sempre lo strumento ora_corrente, "
    "anche se nella conversazione c'è già un risultato precedente: quel risultato è superato. "
    "Non dedurre informazioni temporali che il risultato non contiene. "
    "Per l'ora di un'altra città chiama ora_corrente, converti dall'ora locale e indica "
    "nella risposta anche l'ora locale da cui sei partito."
)


class RispostaNonValida(Exception):
    """Il modello ha risposto con un messaggio vuoto o con una richiesta di strumento malformata."""


class Stato(TypedDict):
    """Stato del grafo: la cronologia dei messaggi, in aggiunta a ogni passaggio."""

    messages: Annotated[list[AnyMessage], add_messages]


def costruisci_grafo(modello, strumenti: list[BaseTool]) -> CompiledStateGraph:
    """Costruisce il grafo START -> nodo_llm -> END attorno a `modello`.

    Gli strumenti vengono associati al modello una volta sola, e solo se l'elenco non è vuoto:
    un elenco `tools` vuoto può essere rifiutato dall'API.
    """
    if strumenti:
        modello = modello.bind_tools(strumenti)

    def nodo_llm(stato: Stato) -> dict:
        """Interroga il modello con il prompt di sistema (non salvato) e la cronologia."""
        messaggi = [SystemMessage(PROMPT_DI_SISTEMA), *stato["messages"]]
        logger.info("nodo_llm: chiamata al modello (%d messaggi)", len(messaggi))
        inizio = time.perf_counter()
        risposta = modello.invoke(messaggi)
        logger.info("nodo_llm: risposta ricevuta in %.1f s", time.perf_counter() - inizio)

        if risposta.invalid_tool_calls or (not risposta.tool_calls and not risposta.text.strip()):
            logger.warning(
                "nodo_llm: risposta non valida (testo vuoto o richiesta di strumento malformata)"
            )
            raise RispostaNonValida("il modello non ha prodotto una risposta valida")
        return {"messages": [risposta]}

    costruttore = StateGraph(Stato)
    costruttore.add_node("nodo_llm", nodo_llm)
    costruttore.add_edge(START, "nodo_llm")
    costruttore.add_edge("nodo_llm", END)
    return costruttore.compile()


def esegui_turno(grafo: CompiledStateGraph, cronologia: list[AnyMessage], testo: str) -> list[AnyMessage]:
    """Esegue un turno e restituisce la nuova cronologia; `cronologia` non viene modificata.

    Se il turno fallisce l'eccezione risale a chi chiama, che conserva la cronologia di prima.
    """
    risultato = grafo.invoke(
        {"messages": [*cronologia, HumanMessage(testo)]},
        {"recursion_limit": LIMITE_PASSAGGI},
    )
    return risultato["messages"]
