from langchain_core.messages import HumanMessage

from assistente.grafo import RISPOSTA_FISSA, costruisci_grafo_fisso


def test_grafo_fisso_restituisce_la_risposta_prevista():
    grafo = costruisci_grafo_fisso()
    risultato = grafo.invoke({"messages": [HumanMessage("ciao")]})
    assert [m.type for m in risultato["messages"]] == ["human", "ai"]
    assert risultato["messages"][-1].content == RISPOSTA_FISSA
