import logging

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.router import MESSAGGI_AL_ROUTER, SCHEMA_ROUTER, leggi_decisione, messaggi_per_il_router
from assistente.router import testo_rifiuto as rifiuto  # un nome che inizia con «test» verrebbe raccolto da pytest


def test_schema():
    assert SCHEMA_ROUTER["required"] == ["categoria", "motivo"]
    assert SCHEMA_ROUTER["properties"]["categoria"]["enum"] == ["conversazione", "fuori_ambito"]


def test_al_router_solo_domande_e_risposte_testuali():
    richiesta = AIMessage("", tool_calls=[{"name": "giorni_tra", "args": {"data": "12-25"}, "id": "t1"}])
    cronologia = [
        HumanMessage("Quanti giorni mancano a Natale?"),
        richiesta,
        ToolMessage("mancano 46 giorni", tool_call_id="t1", name="giorni_tra"),
        AIMessage("Mancano 46 giorni."),
        HumanMessage("e a Capodanno?"),
    ]
    scelti = messaggi_per_il_router(cronologia)
    assert [m.text for m in scelti] == ["Quanti giorni mancano a Natale?", "Mancano 46 giorni.", "e a Capodanno?"]


def test_al_router_solo_gli_ultimi_messaggi():
    cronologia = []
    for i in range(10):
        cronologia += [HumanMessage(f"D{i}"), AIMessage(f"R{i}")]
    cronologia.append(HumanMessage("ultima"))
    scelti = messaggi_per_il_router(cronologia)
    assert len(scelti) == MESSAGGI_AL_ROUTER and scelti[-1].text == "ultima"


def test_leggi_decisione_valida():
    risultato = {"parsed": {"categoria": "fuori_ambito", "motivo": "poesia"}, "parsing_error": None}
    assert leggi_decisione(risultato) == ("fuori_ambito", "poesia")


def test_leggi_decisione_illeggibile(caplog):
    for risultato in [
        {"parsed": {"categoria": "altro", "motivo": "x"}, "parsing_error": None},
        {"parsed": None, "parsing_error": ValueError("JSON rotto")},
        {"parsed": {"categoria": "conversazione"}, "parsing_error": None},
    ]:
        assert leggi_decisione(risultato) == ("conversazione", "decisione del router illeggibile")
    avvisi = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(avvisi) == 3 and all("la domanda passa all'agente" in r.getMessage() for r in avvisi)


def test_testo_rifiuto():
    atteso = "Posso aiutarti solo con domande scientifiche o sul laboratorio: richiesta di una poesia."
    assert rifiuto("richiesta di una poesia") == atteso
    assert rifiuto(" richiesta di una poesia. ") == atteso
