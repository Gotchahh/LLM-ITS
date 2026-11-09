from zoneinfo import ZoneInfo

import pytest
from conftest import porta_libera
from langchain_core.tools import ToolException

from assistente.note import crea_strumenti_note, formatta_nota, servizio_raggiungibile

ROMA = ZoneInfo("Europe/Rome")


def strumenti(url):
    return {s.name: s for s in crea_strumenti_note(url, ROMA)}


def errore_di(strumento, argomenti):
    with pytest.raises(ToolException) as errore:
        strumento.invoke(argomenti)
    return str(errore.value)


def test_strumenti(servizio_note):
    lista = crea_strumenti_note(servizio_note, ROMA)
    assert [s.name for s in lista] == ["salva_nota", "elenca_note", "cancella_nota"]
    assert [set(s.args) for s in lista] == [{"testo"}, {"cerca"}, {"numero"}]


def test_salva_elenca_cancella(servizio_note):
    s = strumenti(servizio_note)
    salvata = s["salva_nota"].invoke({"testo": "calibrare il microscopio 2"})
    assert salvata.startswith("nota ") and salvata.endswith("salvata: «calibrare il microscopio 2»")
    numero = salvata.split()[1]
    assert "calibrare il microscopio 2" in s["elenca_note"].invoke({"cerca": "MICROSCOPIO"})
    assert s["cancella_nota"].invoke({"numero": int(numero)}) == f"nota {numero} cancellata: «calibrare il microscopio 2»"
    assert "nessuna nota con numero" in errore_di(s["cancella_nota"], {"numero": int(numero)})


def test_elenco_vuoto_e_ricerca_senza_risultati(servizio_note):
    s = strumenti(servizio_note)
    assert s["elenca_note"].invoke({"cerca": "xyz"}) == "nessuna nota contiene «xyz»"
    assert s["elenca_note"].invoke({"cerca": " "}) == s["elenca_note"].invoke({})


def test_oltre_20(servizio_note):
    s = strumenti(servizio_note)
    for i in range(25):
        s["salva_nota"].invoke({"testo": f"campione {i}"})
    elenco = s["elenca_note"].invoke({"cerca": "campione"})
    assert elenco.startswith("25 note: ") and elenco.endswith("(mostrate le 20 più recenti su 25)")
    assert elenco.count("n. ") == 20


def test_una_nota_al_singolare(servizio_note):
    s = strumenti(servizio_note)
    s["salva_nota"].invoke({"testo": "unica centrifuga"})
    assert s["elenca_note"].invoke({"cerca": "centrifuga"}).startswith("1 nota: n. ")


def test_data_nel_fuso():
    nota = {"numero": 3, "testo": "prova", "creata": "2026-11-09T09:15:00+00:00"}
    assert formatta_nota(nota, ROMA) == "n. 3 (9/11/2026 10:15) prova"


def test_testo_non_valido(servizio_note):
    assert "500" in errore_di(strumenti(servizio_note)["salva_nota"], {"testo": "   "})


def test_argomenti_sbagliati(servizio_note):
    messaggio = errore_di(strumenti(servizio_note)["cancella_nota"], {"numero": "tre"})
    assert "numero" in messaggio and "validation" not in messaggio.lower()


def test_servizio_spento(servizio_note):
    spento = f"http://127.0.0.1:{porta_libera()}"
    messaggio = errore_di(strumenti(spento)["elenca_note"], {})
    assert "non raggiungibile" in messaggio and "python -m note_api" in messaggio
    assert servizio_raggiungibile(spento) is False
    assert servizio_raggiungibile(servizio_note) is True
