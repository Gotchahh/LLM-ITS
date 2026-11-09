"""Grafo LangGraph dell'assistente: stato, nodi e collegamenti."""

import json
import logging
import time
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, ToolException
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
    "Per l'ora di un'altra città chiama ora_corrente con il fuso IANA di quella città "
    "(per esempio America/New_York) e usa il risultato così com'è, senza convertire da te. "
    "Per qualsiasi calcolo aritmetico chiama lo strumento calcola con l'espressione "
    "(numeri con il punto decimale, ** per le potenze) invece di calcolare da te, "
    "e usa il risultato così com'è; se lo strumento restituisce un errore, "
    "dillo senza inventare un risultato. "
    "Per ogni conversione tra unità di lunghezza, peso o temperatura chiama lo strumento converti "
    "invece di calcolare da te o con calcola, e usa il risultato così com'è; "
    "se lo strumento restituisce un errore, di' che la conversione non si può fare e perché. "
    "Per i giorni mancanti o trascorsi fino a una data o tra due date chiama giorni_tra, "
    "per la data tra N giorni o di N giorni fa chiama sposta_data, "
    "per il giorno della settimana di una data chiama giorno_settimana "
    "e per la data di Pasqua chiama pasqua, passando le date come AAAA-MM-GG "
    "oppure MM-GG se l'anno non è indicato; non calcolare da te, usa il risultato così com'è e, "
    "se lo strumento restituisce un errore, di' che non si può fare e perché. "
    "Per salvare, elencare, cercare o cancellare note chiama salva_nota, elenca_note o cancella_nota; "
    "per cancellare una nota indicata per argomento chiama prima elenca_note per trovarne il numero. "
    "Non dire mai che una nota è salvata o cancellata senza il risultato dello strumento e, "
    "se lo strumento restituisce un errore, di' che non si può fare e perché. "
    "Per domande sugli apparecchi del laboratorio (dove si trovano, stato, calibrazione, "
    "che cosa c'è in una stanza) chiama cerca_apparecchi, dettaglio_apparecchio o elenca_apparecchi "
    "e rispondi solo con quello che restituiscono; se lo strumento dà un errore o nessun risultato, "
    "dillo senza inventare apparecchi."
)


class RispostaNonValida(Exception):
    """Il modello ha risposto con un messaggio vuoto o con una richiesta di strumento malformata."""


class Stato(TypedDict):
    """Stato del grafo: la cronologia dei messaggi, in aggiunta a ogni passaggio."""

    messages: Annotated[list[AnyMessage], add_messages]


def instrada(stato: Stato) -> str:
    """Arco condizionale dopo `nodo_llm`: "nodo_strumenti" se il modello chiede strumenti, altrimenti END."""
    richieste = stato["messages"][-1].tool_calls
    if not richieste:
        logger.info("instradamento: nessuno strumento -> fine")
        return END
    for richiesta in richieste:
        logger.info(
            "instradamento: richiesta strumento %s %s",
            richiesta["name"],
            json.dumps(richiesta["args"], ensure_ascii=False),
        )
    return "nodo_strumenti"


def costruisci_grafo(modello, strumenti: list[BaseTool]) -> CompiledStateGraph:
    """Costruisce il grafo attorno a `modello` e agli `strumenti`.

    START -> nodo_llm -> (instrada) -> nodo_strumenti | END, e nodo_strumenti -> nodo_llm.
    Gli strumenti vengono associati al modello una volta sola, e solo se l'elenco non è vuoto:
    un elenco `tools` vuoto può essere rifiutato dall'API.
    """
    if strumenti:
        modello = modello.bind_tools(strumenti)
    per_nome = {strumento.name: strumento for strumento in strumenti}

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

    def nodo_strumenti(stato: Stato) -> dict:
        """Esegue ogni richiesta dell'ultimo messaggio e risponde con un ToolMessage per ciascuna.

        Una `ToolException` diventa un ToolMessage con stato "error" e il turno prosegue;
        ogni altra eccezione risale e annulla il turno.
        """
        risposte = []
        for richiesta in stato["messages"][-1].tool_calls:
            nome = richiesta["name"]
            strumento = per_nome.get(nome)
            esito = "success"
            if strumento is None:
                logger.warning("nodo_strumenti: strumento sconosciuto %s", nome)
                risultato = f"Errore: strumento sconosciuto {nome}"
            else:
                argomenti = {k: v for k, v in richiesta["args"].items() if k in strumento.args}
                ignorati = {k: v for k, v in richiesta["args"].items() if k not in strumento.args}
                if ignorati:
                    logger.warning(
                        "nodo_strumenti: argomenti ignorati per %s: %s",
                        nome,
                        json.dumps(ignorati, ensure_ascii=False),
                    )
                try:
                    risultato = strumento.invoke(argomenti)
                    logger.info("nodo_strumenti: %s -> %s", nome, risultato)
                except ToolException as errore:
                    risultato = f"Errore: {errore}"
                    esito = "error"
                    logger.warning("nodo_strumenti: errore dello strumento %s: %s", nome, errore)
            risposte.append(
                ToolMessage(content=risultato, tool_call_id=richiesta["id"], name=nome, status=esito)
            )
        return {"messages": risposte}

    costruttore = StateGraph(Stato)
    costruttore.add_node("nodo_llm", nodo_llm)
    costruttore.add_node("nodo_strumenti", nodo_strumenti)
    costruttore.add_edge(START, "nodo_llm")
    costruttore.add_conditional_edges("nodo_llm", instrada, ["nodo_strumenti", END])
    costruttore.add_edge("nodo_strumenti", "nodo_llm")
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
