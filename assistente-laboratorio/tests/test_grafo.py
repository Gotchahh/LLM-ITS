import logging

import pytest
from conftest import ModelloFinto
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from assistente.grafo import (
    LIMITE_PASSAGGI,
    PROMPT_DI_SISTEMA,
    RispostaNonValida,
    costruisci_grafo,
    esegui_turno,
)


@tool
def strumento_di_prova() -> str:
    """Strumento inutile, serve solo ai test."""
    return "ok"


def test_turno_senza_strumenti_chiama_il_modello_una_volta():
    finto = ModelloFinto([AIMessage("Ciao!")])
    nuova = esegui_turno(costruisci_grafo(finto, []), [], "ciao")
    assert [m.type for m in nuova] == ["human", "ai"] and nuova[-1].content == "Ciao!"
    assert len(finto.chiamate) == 1
    assert finto.chiamate[0][0].type == "system" and finto.chiamate[0][0].content == PROMPT_DI_SISTEMA


def test_due_turni_conservano_la_cronologia_senza_duplicati():
    finto = ModelloFinto([AIMessage("R1"), AIMessage("R2")])
    grafo = costruisci_grafo(finto, [])
    cronologia = esegui_turno(grafo, esegui_turno(grafo, [], "D1"), "D2")
    assert [(m.type, m.content) for m in cronologia] == [
        ("human", "D1"), ("ai", "R1"), ("human", "D2"), ("ai", "R2")]
    assert [m.type for m in finto.chiamate[1]] == ["system", "human", "ai", "human"]


def test_il_prompt_di_sistema_non_entra_nella_cronologia():
    nuova = esegui_turno(costruisci_grafo(ModelloFinto([AIMessage("Ciao!")]), []), [], "ciao")
    assert "system" not in [m.type for m in nuova]


def test_errore_del_modello_lascia_la_cronologia_invariata():
    grafo = costruisci_grafo(ModelloFinto([AIMessage("R1"), RuntimeError("giù")]), [])
    cronologia = esegui_turno(grafo, [], "D1")
    copia = list(cronologia)
    with pytest.raises(RuntimeError):
        esegui_turno(grafo, cronologia, "D2")
    assert cronologia == copia


@pytest.mark.parametrize("risposta", [AIMessage(""), AIMessage("   "),
    AIMessage("", invalid_tool_calls=[{"name": "ora_corrente", "args": "{", "id": "x", "error": "json"}])])
def test_risposta_non_valida(risposta):
    with pytest.raises(RispostaNonValida):
        esegui_turno(costruisci_grafo(ModelloFinto([risposta]), []), [], "ciao")


def test_risposta_non_valida_registra_un_avviso(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    with pytest.raises(RispostaNonValida):
        esegui_turno(costruisci_grafo(ModelloFinto([AIMessage("  ")]), []), [], "ciao")
    assert [r.levelname for r in caplog.records if r.name.startswith("assistente")][-1] == "WARNING"


def test_risposta_con_richiesta_di_strumento_e_testo_vuoto_e_valida():
    richiesta = AIMessage("", tool_calls=[{"name": "ora_corrente", "args": {}, "id": "1"}])
    nuova = esegui_turno(costruisci_grafo(ModelloFinto([richiesta]), []), [], "che ore sono?")
    assert nuova[-1].tool_calls[0]["name"] == "ora_corrente"


def test_senza_strumenti_il_modello_non_viene_associato():
    finto = ModelloFinto([])
    costruisci_grafo(finto, [])
    assert finto.strumenti_associati == []


def test_con_strumenti_il_modello_viene_associato_una_volta():
    finto = ModelloFinto([AIMessage("R1"), AIMessage("R2")])
    grafo = costruisci_grafo(finto, [strumento_di_prova])
    esegui_turno(grafo, esegui_turno(grafo, [], "D1"), "D2")
    assert finto.strumenti_associati == [[strumento_di_prova]]


def test_il_nodo_llm_registra_chiamata_e_risposta(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    esegui_turno(costruisci_grafo(ModelloFinto([AIMessage("Ciao!")]), []), [], "ciao")
    messaggi = [r.getMessage() for r in caplog.records if r.name.startswith("assistente")]
    assert messaggi[0] == "nodo_llm: chiamata al modello (2 messaggi)"
    assert messaggi[1].startswith("nodo_llm: risposta ricevuta in ") and messaggi[1].endswith(" s")


def test_il_turno_e_invocato_con_il_limite_di_passaggi():
    class GrafoSpia:
        def invoke(self, stato, config):
            self.config = config
            return {"messages": stato["messages"]}

    spia = GrafoSpia()
    esegui_turno(spia, [], "ciao")
    assert LIMITE_PASSAGGI == 10 and spia.config == {"recursion_limit": LIMITE_PASSAGGI}
