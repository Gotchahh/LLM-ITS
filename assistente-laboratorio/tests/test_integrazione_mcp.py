"""Grafo con il modello finto e il server MCP vero (si avvia davvero: ogni chiamata richiede circa 2 s)."""

from zoneinfo import ZoneInfo

import pytest
from conftest import ModelloFinto
from langchain_core.messages import AIMessage
from langgraph.errors import GraphRecursionError

from assistente.client_mcp import carica_strumenti_mcp
from assistente.grafo import costruisci_grafo, esegui_turno
from assistente.strumenti import crea_strumento_orologio


@pytest.fixture(scope="module")
def strumenti():
    return [crea_strumento_orologio(ZoneInfo("Europe/Rome")), *carica_strumenti_mcp()]


def richiesta_calcolo(id, espressione):
    return AIMessage("", tool_calls=[{"name": "calcola", "args": {"espressione": espressione}, "id": id}])


def test_calcolo_con_il_server_vero(strumenti):
    finto = ModelloFinto([richiesta_calcolo("m1", "12.5*8-3"), AIMessage("Fa 97.")])
    nuova = esegui_turno(costruisci_grafo(finto, strumenti), [], "Quanto fa 12,5 per 8 meno 3?")
    assert (nuova[2].content, nuova[2].status, nuova[2].tool_call_id) == ("97", "success", "m1")
    assert nuova[-1].content == "Fa 97."


def test_errore_controllato_senza_falso_successo(strumenti):
    finto = ModelloFinto([richiesta_calcolo("m2", "1/0"), AIMessage("Non si può dividere per zero.")])
    nuova = esegui_turno(costruisci_grafo(finto, strumenti), [], "Quanto fa 1 diviso 0?")
    assert (nuova[2].content, nuova[2].status, nuova[2].tool_call_id) == \
        ("Errore: divisione per zero", "error", "m2")
    assert len(finto.chiamate) == 2


def test_argomento_con_nome_sbagliato_diventa_un_errore(strumenti, caplog):
    sbagliata = AIMessage("", tool_calls=[{"name": "calcola", "args": {"expression": "2+2"}, "id": "w1"}])
    nuova = esegui_turno(costruisci_grafo(ModelloFinto([sbagliata, AIMessage("ok")]), strumenti), [], "2+2?")
    assert nuova[2].status == "error" and nuova[2].content.startswith("Errore: ")
    assert any("argomenti ignorati" in r.getMessage() for r in caplog.records)


def test_cronologia_su_due_turni_con_lo_strumento_mcp(strumenti):
    finto = ModelloFinto([richiesta_calcolo("t1", "2+2"), AIMessage("Fa 4."), AIMessage("Hai chiesto 2+2.")])
    grafo = costruisci_grafo(finto, strumenti)
    cronologia = esegui_turno(grafo, esegui_turno(grafo, [], "Quanto fa 2+2?"), "Che cosa ti ho chiesto?")
    assert [m.type for m in cronologia] == ["human", "ai", "tool", "ai", "human", "ai"]
    assert cronologia[2].content == "4"


def test_limite_di_passaggi_con_lo_strumento_mcp(strumenti):
    finto = ModelloFinto([richiesta_calcolo(f"l{i}", "1+1") for i in range(20)])
    with pytest.raises(GraphRecursionError):
        esegui_turno(costruisci_grafo(finto, strumenti), [], "?")


def richiesta(id, nome, args):
    return AIMessage("", tool_calls=[{"name": nome, "args": args, "id": id}])


def test_catalogo_con_il_server_vero(strumenti):
    finto = ModelloFinto([
        richiesta("k9", "elenca_apparecchi", {"stato": "in manutenzione"}),
        richiesta("k10", "dettaglio_apparecchio", {"codice": "XYZ-99"}),
        AIMessage("Ecco."),
    ])
    nuova = esegui_turno(costruisci_grafo(finto, strumenti), [], "Che cosa è in manutenzione?")
    elenco, errore = nuova[2], nuova[4]
    assert elenco.tool_call_id == "k9" and elenco.status == "success" and "MIC-02" in elenco.content
    assert errore.tool_call_id == "k10" and errore.status == "error"
    assert errore.content == "Errore: nessun apparecchio con codice «XYZ-99»"
