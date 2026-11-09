import logging

from langchain_core.messages import AIMessage, HumanMessage

from assistente.revisore import (
    SCHEMA_REVISORE,
    e_indicazione,
    indicazione,
    leggi_valutazione,
    messaggi_per_il_revisore,
    ultima_domanda,
)


def test_schema():
    assert SCHEMA_REVISORE["title"] == "valutazione_revisore"
    assert SCHEMA_REVISORE["properties"]["coerente"]["type"] == "boolean"
    assert SCHEMA_REVISORE["required"] == ["motivo", "coerente"]
    assert list(SCHEMA_REVISORE["properties"]) == ["motivo", "coerente"]  # il verdetto dopo il motivo


def test_indicazione_marcata():
    messaggio = indicazione("manca il giorno della settimana", "Natale?")
    assert isinstance(messaggio, HumanMessage) and e_indicazione(messaggio)
    assert "manca il giorno della settimana" in messaggio.text and "«Natale?»" in messaggio.text
    assert not e_indicazione(HumanMessage("Natale?"))


def test_ultima_domanda_salta_le_indicazioni():
    cronologia = [HumanMessage("Natale?"), AIMessage("46 giorni"), indicazione("manca il giorno", "Natale?")]
    assert ultima_domanda(cronologia) == "Natale?"


def test_messaggi_per_il_revisore():
    sistema, richiesta = messaggi_per_il_revisore("ISTRUZIONI", "Natale?", "Mancano 46 giorni.")
    assert sistema.type == "system" and sistema.text == "ISTRUZIONI"
    assert richiesta.type == "human" and "Natale?" in richiesta.text and "Mancano 46 giorni." in richiesta.text


def test_leggi_valutazione_valida():
    risultato = {"parsed": {"coerente": False, "motivo": "manca il giorno"}, "parsing_error": None}
    assert leggi_valutazione(risultato) == (False, "manca il giorno")


def test_leggi_valutazione_illeggibile(caplog):
    for risultato in [
        {"parsed": None, "parsing_error": ValueError("JSON rotto")},
        {"parsed": {"coerente": "no", "motivo": "x"}, "parsing_error": None},
        {"parsed": {"coerente": True}, "parsing_error": None},
    ]:
        assert leggi_valutazione(risultato) == (True, "valutazione illeggibile")
    avvisi = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert avvisi == ["revisore: valutazione illeggibile, la risposta è approvata"] * 3
