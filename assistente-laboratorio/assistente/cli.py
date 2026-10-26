"""Interfaccia da terminale: ciclo di lettura, invocazione del grafo e stampa."""

from langchain_core.messages import HumanMessage


def esegui_chat(grafo, leggi=input, scrivi=print) -> None:
    """Legge le righe dell'utente e stampa le risposte del grafo.

    Termina con `/esci` oppure quando l'input finisce.
    """
    while True:
        try:
            riga = leggi("Tu> ")
        except EOFError:
            break
        if riga.strip().lower() == "/esci":
            break
        risultato = grafo.invoke({"messages": [HumanMessage(riga)]})
        scrivi(f"Assistente> {risultato['messages'][-1].content}")
    scrivi("Alla prossima!")
