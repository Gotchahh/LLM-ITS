import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from conftest import ModelloFinto, chat
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.errors import GraphRecursionError

from assistente.grafo import (
    LIMITE_PASSAGGI,
    PROMPT_DI_SISTEMA,
    RispostaNonValida,
    costruisci_grafo,
    esegui_turno,
)
from assistente.strumenti import crea_strumento_orologio

orologio = crea_strumento_orologio(
    ZoneInfo("Europe/Rome"), adesso=lambda: datetime(2026, 10, 26, 15, 42, 10, tzinfo=UTC))


def chiamata(id, args=None):
    """Risposta del modello che chiede `ora_corrente` con gli argomenti dati."""
    return AIMessage("", tool_calls=[{"name": "ora_corrente", "args": args or {}, "id": id}])


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
    finto = ModelloFinto([chiamata("1"), AIMessage("Sono le 16:42.")])
    nuova = esegui_turno(costruisci_grafo(finto, [orologio]), [], "che ore sono?")
    assert nuova[1].tool_calls[0]["name"] == "ora_corrente" and nuova[-1].content == "Sono le 16:42."


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


def test_percorso_con_strumento(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    finto = ModelloFinto([chiamata("c1"), AIMessage("Sono le 16:42.")])
    nuova = esegui_turno(costruisci_grafo(finto, [orologio]), [], "Che ore sono?")
    assert [m.type for m in nuova] == ["human", "ai", "tool", "ai"]
    assert nuova[2].tool_call_id == "c1"
    assert nuova[2].content == "lunedì 2026-10-26T16:42:10+01:00 (Europe/Rome)"
    assert [m.type for m in finto.chiamate[1]] == ["system", "human", "ai", "tool"]
    assert "instradamento: richiesta strumento ora_corrente {}" in caplog.messages
    assert "nodo_strumenti: ora_corrente -> lunedì 2026-10-26T16:42:10+01:00 (Europe/Rome)" in caplog.messages


def test_argomenti_inattesi_ignorati(caplog):
    finto = ModelloFinto([chiamata("c1", {"timezone": "Asia/Tokyo"}), AIMessage("ok")])
    nuova = esegui_turno(costruisci_grafo(finto, [orologio]), [], "Ora a Tokyo?")
    assert nuova[2].content.endswith("(Europe/Rome)")
    assert any("argomenti ignorati" in r.message and r.levelname == "WARNING" for r in caplog.records)


def test_piu_richieste_nella_stessa_risposta():
    doppia = AIMessage("", tool_calls=[{"name": "ora_corrente", "args": {}, "id": "a"},
                                       {"name": "ora_corrente", "args": {}, "id": "b"}])
    nuova = esegui_turno(costruisci_grafo(ModelloFinto([doppia, AIMessage("ok")]), [orologio]), [], "?")
    assert [m.tool_call_id for m in nuova if m.type == "tool"] == ["a", "b"]


def test_strumento_sconosciuto(caplog):
    sconosciuta = AIMessage("", tool_calls=[{"name": "meteo", "args": {}, "id": "m"}])
    nuova = esegui_turno(costruisci_grafo(ModelloFinto([sconosciuta, AIMessage("ok")]), [orologio]), [], "?")
    assert nuova[2].content == "Errore: strumento sconosciuto meteo"
    assert nuova[2].tool_call_id == "m" and nuova[2].name == "meteo"
    assert any("meteo" in r.message and r.levelname == "WARNING" for r in caplog.records)


def test_limite_di_passaggi():
    finto = ModelloFinto([chiamata(f"c{i}") for i in range(20)])
    with pytest.raises(GraphRecursionError):
        esegui_turno(costruisci_grafo(finto, [orologio]), [], "?")


def test_limite_di_passaggi_in_chat():
    finto = ModelloFinto([chiamata(f"c{i}") for i in range(20)] + [AIMessage("Eccomi")])
    uscita = chat(costruisci_grafo(finto, [orologio]), ["D1", "/esci"])
    assert "Errore: limite di 10 passaggi raggiunto. Turno annullato." in uscita


def test_risposta_con_testo_e_richiesta_va_agli_strumenti():
    mista = AIMessage("Controllo l'orologio.", tool_calls=[{"name": "ora_corrente", "args": {}, "id": "x"}])
    nuova = esegui_turno(costruisci_grafo(ModelloFinto([mista, AIMessage("ok")]), [orologio]), [], "?")
    assert nuova[2].type == "tool"
