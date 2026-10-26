"""Grafo LangGraph dell'assistente: stato, nodi e collegamenti."""

from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, AnyMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

RISPOSTA_FISSA = "Il grafo è in esecuzione."


class Stato(TypedDict):
    """Stato del grafo: la cronologia dei messaggi, in aggiunta a ogni passaggio."""

    messages: Annotated[list[AnyMessage], add_messages]


def nodo_risposta(stato: Stato) -> dict:
    """Aggiunge alla conversazione la risposta fissa, senza interrogare alcun modello."""
    return {"messages": [AIMessage(RISPOSTA_FISSA)]}


def costruisci_grafo_fisso() -> CompiledStateGraph:
    """Costruisce il grafo START -> nodo_risposta -> END."""
    costruttore = StateGraph(Stato)
    costruttore.add_node("nodo_risposta", nodo_risposta)
    costruttore.add_edge(START, "nodo_risposta")
    costruttore.add_edge("nodo_risposta", END)
    return costruttore.compile()
