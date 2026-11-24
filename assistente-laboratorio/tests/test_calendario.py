from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from langchain_core.tools import ToolException

from assistente.calendario import (
    crea_strumenti_calendario,
    data_di_pasqua,
    formatta_data,
    giorni_tra,
    giorno_settimana,
    leggi_data,
    pasqua,
    sposta_data,
)

OGGI = date(2026, 11, 3)  # martedì
ROMA = ZoneInfo("Europe/Rome")


def strumenti(adesso=lambda: datetime(2026, 11, 3, 10, 0, tzinfo=UTC)):
    return {s.name: s for s in crea_strumenti_calendario(ROMA, adesso=adesso)}


def test_formatta_data():
    assert formatta_data(date(2026, 12, 25)) == "venerdì 25 dicembre 2026"


@pytest.mark.parametrize("testo, atteso", [
    ("2026-12-25", date(2026, 12, 25)),
    (" 12-25 ", date(2026, 12, 25)),
    ("11-03", date(2026, 11, 3)),
    ("11-02", date(2027, 11, 2)),
    ("02-29", date(2028, 2, 29)),
    ("1789-07-14", date(1789, 7, 14)),
])
def test_leggi_data(testo, atteso):
    assert leggi_data(testo, OGGI) == atteso


@pytest.mark.parametrize("testo, frammenti", [
    ("2026-02-30", ["non valida", "2026-02-30"]),
    ("2026-13-01", ["non valida", "2026-13-01"]),
    ("02-30", ["non valida", "02-30"]),
    ("25 dicembre", ["2026-12-25", "12-25"]),
    ("25/12/2026", ["2026-12-25", "12-25"]),
    ("", ["2026-12-25", "12-25"]),
])
def test_leggi_data_errori(testo, frammenti):
    with pytest.raises(ToolException) as errore:
        leggi_data(testo, OGGI)
    for frammento in frammenti:
        assert frammento in str(errore.value)


@pytest.mark.parametrize("data, partenza, atteso, intero", [
    ("12-25", None, "da martedì 3 novembre 2026 a venerdì 25 dicembre 2026: mancano 52 giorni", True),
    ("2026-01-01", None, "da martedì 3 novembre 2026 a giovedì 1 gennaio 2026: sono passati 306 giorni", True),
    ("2026-11-04", None, ": manca 1 giorno", False),
    ("2026-11-02", None, ": è passato 1 giorno", False),
    ("11-03", None, "martedì 3 novembre 2026: è oggi", True),
    ("2026-06-02", "2026-03-10", ": mancano 84 giorni", False),
    ("2026-03-10", "2026-03-10", ": 0 giorni", False),
    ("2027-03-01", "2027-02-01", ": mancano 28 giorni", False),
])
def test_giorni_tra(data, partenza, atteso, intero):
    risultato = giorni_tra(data, partenza, OGGI)
    if intero:
        assert risultato == atteso
    else:
        assert risultato.endswith(atteso)


@pytest.mark.parametrize("giorni, data, atteso, intero", [
    (30, None, "tra 30 giorni: giovedì 3 dicembre 2026", True),
    (-10, None, "10 giorni fa: sabato 24 ottobre 2026", True),
    (1, None, "tra 1 giorno: mercoledì 4 novembre 2026", True),
    (0, None, "oggi: martedì 3 novembre 2026", True),
    (60, None, "sabato 2 gennaio 2027", False),
    (1, "2028-02-28", "1 giorno dopo lunedì 28 febbraio 2028: martedì 29 febbraio 2028", True),
    (-1, "2027-01-01", "1 giorno prima di venerdì 1 gennaio 2027: giovedì 31 dicembre 2026", True),
])
def test_sposta_data(giorni, data, atteso, intero):
    risultato = sposta_data(giorni, data, OGGI)
    if intero:
        assert risultato == atteso
    else:
        assert risultato.endswith(atteso)


def test_giorno_settimana():
    assert giorno_settimana("1789-07-14", OGGI) == "martedì 14 luglio 1789"
    assert giorno_settimana("12-25", OGGI) == "venerdì 25 dicembre 2026"


@pytest.mark.parametrize("anno, atteso", [
    (1583, date(1583, 4, 10)),
    (2024, date(2024, 3, 31)),
    (2025, date(2025, 4, 20)),
    (2026, date(2026, 4, 5)),
    (2027, date(2027, 3, 28)),
    (2038, date(2038, 4, 25)),
    (2285, date(2285, 3, 22)),
])
def test_data_di_pasqua(anno, atteso):
    assert data_di_pasqua(anno) == atteso


def test_pasqua():
    assert pasqua(2027, OGGI) == "Pasqua 2027: domenica 28 marzo 2027"
    assert pasqua(None, OGGI) == "Pasqua 2026: domenica 5 aprile 2026"


@pytest.mark.parametrize("chiamata, frammento", [
    (lambda: pasqua(1500, OGGI), "1583"),
    (lambda: pasqua(0, OGGI), "1–9999"),
    (lambda: pasqua(10000, OGGI), "1–9999"),
    (lambda: sposta_data(10**7, None, OGGI), "1–9999"),
    (lambda: sposta_data(-10**7, None, OGGI), "1–9999"),
])
def test_errori_di_intervallo(chiamata, frammento):
    with pytest.raises(ToolException) as errore:
        chiamata()
    assert frammento in str(errore.value)


def test_oggi_nel_fuso_configurato():
    vicino_alla_mezzanotte = strumenti(adesso=lambda: datetime(2026, 11, 2, 23, 30, tzinfo=UTC))
    assert vicino_alla_mezzanotte["giorni_tra"].invoke({"data": "12-25"}).endswith("mancano 52 giorni")


def test_strumenti():
    lista = crea_strumenti_calendario(ROMA, adesso=lambda: datetime(2026, 11, 3, 10, 0, tzinfo=UTC))
    assert [s.name for s in lista] == ["giorni_tra", "sposta_data", "giorno_settimana", "pasqua"]
    assert [set(s.args) for s in lista] == [{"data", "partenza"}, {"giorni", "data"}, {"data"}, {"anno"}]
    per_nome = strumenti()
    assert per_nome["sposta_data"].invoke({"giorni": "30"}) == "tra 30 giorni: giovedì 3 dicembre 2026"
    for nome, argomenti, parametro in [("sposta_data", {"giorni": 2.5}, "giorni"), ("giorni_tra", {}, "data")]:
        with pytest.raises(ToolException) as errore:
            per_nome[nome].invoke(argomenti)
        assert parametro in str(errore.value)
        assert "validation" not in str(errore.value).lower()


def test_date_facoltative_vuote_valgono_oggi():
    per_nome = strumenti()
    assert per_nome["sposta_data"].invoke({"giorni": 30, "data": " "}) == "tra 30 giorni: giovedì 3 dicembre 2026"
    assert per_nome["giorni_tra"].invoke({"data": "12-25", "partenza": ""}).endswith("mancano 52 giorni")
