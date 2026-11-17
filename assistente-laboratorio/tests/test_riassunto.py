from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.riassunto import (
    con_riassunto,
    messaggi_di_contesto,
    messaggi_per_il_riassunto,
    punto_di_taglio,
    trascrivi,
)


def turno(n):
    """Un turno semplice: domanda e risposta."""
    return [HumanMessage(f"D{n}"), AIMessage(f"R{n}")]


def turno_con_strumento(n):
    """Un turno con una richiesta di strumento e il suo risultato."""
    return [
        HumanMessage(f"D{n}"),
        AIMessage("", tool_calls=[{"name": "ora_corrente", "args": {"fuso": "Europe/Rome"}, "id": f"t{n}"}]),
        ToolMessage("16:42", tool_call_id=f"t{n}", name="ora_corrente"),
        AIMessage(f"R{n}"),
    ]


def test_punto_di_taglio_conserva_gli_ultimi_turni_e_la_domanda():
    messaggi = [*turno(1), *turno(2), *turno(3), *turno(4), HumanMessage("D5")]
    assert punto_di_taglio(messaggi, 2) == 4          # tiene i turni 3 e 4 e la domanda D5
    assert punto_di_taglio(messaggi, 1) == 6          # tiene il turno 4 e la domanda D5


def test_punto_di_taglio_con_turni_due():
    messaggi = [*turno(1), *turno(2), *turno(3), HumanMessage("D4")]
    taglio = punto_di_taglio(messaggi, 2)
    assert messaggi[taglio].text == "D2"
    assert [m.text for m in messaggi[taglio:]] == ["D2", "R2", "D3", "R3", "D4"]


def test_punto_di_taglio_senza_turni_da_tagliare():
    assert punto_di_taglio([*turno(1), *turno(2), HumanMessage("D3")], 2) == 0
    assert punto_di_taglio([HumanMessage("D1")], 1) == 0


def test_punto_di_taglio_non_separa_gli_strumenti():
    messaggi = [*turno_con_strumento(1), *turno_con_strumento(2), HumanMessage("D3")]
    taglio = punto_di_taglio(messaggi, 1)
    assert taglio == 4 and messaggi[taglio].text == "D2"


def test_trascrivi_le_quattro_forme():
    testo = trascrivi(turno_con_strumento(1))
    assert testo.splitlines() == [
        "Utente: D1",
        'Assistente chiede lo strumento ora_corrente {"fuso": "Europe/Rome"}',
        "Strumento ora_corrente: 16:42",
        "Assistente: R1",
    ]


def test_messaggi_per_il_riassunto():
    senza = messaggi_per_il_riassunto("ISTRUZIONI", "", "Utente: D1")
    assert [m.type for m in senza] == ["system", "human"] and senza[0].text == "ISTRUZIONI"
    assert "nessuno" in senza[1].text and "Utente: D1" in senza[1].text
    con = messaggi_per_il_riassunto("ISTRUZIONI", "Si chiama Ottavio.", "Utente: D1")
    assert "Si chiama Ottavio." in con[1].text and "nessuno" not in con[1].text


def test_con_riassunto():
    assert con_riassunto("P", "") == "P"
    testo = con_riassunto("P", "R")
    assert testo.startswith("P\n\n") and testo.endswith("R")


def test_messaggi_di_contesto():
    assert [(m.type, m.text) for m in messaggi_di_contesto("P", "")] == [("system", "P")]
    prompt, riassunto = messaggi_di_contesto("P", "R")
    assert (prompt.type, prompt.text) == ("system", "P")
    assert riassunto.type == "human" and riassunto.text.endswith("R")
