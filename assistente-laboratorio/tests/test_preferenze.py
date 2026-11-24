"""Test delle preferenze dell'utente: controlli campo per campo, predefiniti, righe di log e blocco del prompt."""

import json
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from assistente.client_mcp import ErroreMCP
from assistente.preferenze import (
    Preferenze,
    blocco_preferenze,
    carica_preferenze,
    leggi_preferenze,
    predefinite,
)

ROMA = ZoneInfo("Europe/Rome")
NEW_YORK = ZoneInfo("America/New_York")
FILE_DEL_PROGETTO = Path(__file__).resolve().parent.parent / "preferenze.json"


@pytest.fixture
def avvisi(caplog):
    """I messaggi WARNING del modulo, in ordine."""
    caplog.set_level(logging.INFO, logger="assistente")
    return lambda: [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


def test_predefinite():
    assert predefinite(ROMA) == Preferenze("italiano", ROMA, None)


def test_file_del_progetto(avvisi):
    testo = FILE_DEL_PROGETTO.read_text(encoding="utf-8")
    assert leggi_preferenze(testo, NEW_YORK) == Preferenze("italiano", ROMA, "sintetico")
    assert avvisi() == []


def test_valori_presi_e_campi_in_piu_ignorati(avvisi):
    testo = json.dumps({"lingua": "inglese", "fuso": "America/New_York", "stile": "dettagliato", "colore": "blu"})
    assert leggi_preferenze(testo, ROMA) == Preferenze("inglese", NEW_YORK, "dettagliato")
    assert avvisi() == []


def test_spazi_e_maiuscole(avvisi):                                                  # Review Focus 2
    testo = json.dumps({"lingua": " English ", "fuso": " America/New_York ", "stile": " Dettagliato "})
    assert leggi_preferenze(testo, ROMA) == Preferenze("English", NEW_YORK, "dettagliato")
    assert avvisi() == []


VALIDE = {"lingua": "inglese", "fuso": "America/New_York", "stile": "dettagliato"}


@pytest.mark.parametrize("campo, valore, predefinito", [
    ("lingua", "", "italiano"), ("lingua", "   ", "italiano"), ("lingua", 3, "italiano"), ("lingua", None, "italiano"),
    ("fuso", 5, "Europe/Rome"), ("fuso", None, "Europe/Rome"), ("fuso", "Marte/Base", "Europe/Rome"),
    ("fuso", "../etc", "Europe/Rome"), ("fuso", "", "Europe/Rome"), ("fuso", "Europe", "Europe/Rome"),
    ("stile", "breve", "nessuno stile"), ("stile", 1, "nessuno stile"),
])
def test_campo_non_valido_predefinito_e_avviso(avvisi, campo, valore, predefinito):    # Review Focus 3
    letti = leggi_preferenze(json.dumps({**VALIDE, campo: valore}), ROMA)
    attese = {"lingua": "inglese", "fuso": NEW_YORK, "stile": "dettagliato"}
    attese[campo] = {"lingua": "italiano", "fuso": ROMA, "stile": None}[campo]
    assert letti == Preferenze(**attese)
    assert avvisi() == [
        f"preferenze: {campo} non valido («{json.dumps(valore, ensure_ascii=False)}»), si usa {predefinito}"
    ]


def test_oggetto_vuoto_tutti_mancanti(avvisi):
    assert leggi_preferenze("{}", ROMA) == predefinite(ROMA)
    assert avvisi() == [
        "preferenze: lingua mancante, si usa italiano",
        "preferenze: fuso mancante, si usa Europe/Rome",
        "preferenze: stile mancante, si usa nessuno stile",
    ]


@pytest.mark.parametrize("testo", ["non json", "", "[]", "\"italiano\"", "42", "null"])
def test_testo_che_non_e_un_oggetto_json(testo):                                     # Review Focus 4
    with pytest.raises(ValueError):
        leggi_preferenze(testo, ROMA)


def test_carica_scrive_la_riga_della_lettura(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    testo = FILE_DEL_PROGETTO.read_text(encoding="utf-8")
    assert carica_preferenze(lambda: testo, ROMA) == Preferenze("italiano", ROMA, "sintetico")
    riga = next(m for m in caplog.messages if m.startswith("preferenze: resource utente://preferenze letta in "))
    assert riga.endswith(" s: lingua=italiano, fuso=Europe/Rome, stile=sintetico")


def test_carica_senza_stile_lo_scrive_come_nessuno(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    carica_preferenze(lambda: '{"lingua": "italiano", "fuso": "Europe/Rome"}', ROMA)
    assert any(m.endswith("stile=nessuno") for m in caplog.messages)


def solleva_errore_mcp():
    raise ErroreMCP("resource utente://preferenze non letta (python.exe -m preferenze_mcp): Connection closed")


@pytest.mark.parametrize("leggi, motivo", [
    (solleva_errore_mcp, "Connection closed"),
    (lambda: "[]", "oggetto"),
    (lambda: "non json", "JSON"),
], ids=["server", "non oggetto", "non json"])
def test_carica_resource_non_disponibile(avvisi, leggi, motivo):
    assert carica_preferenze(leggi, NEW_YORK) == predefinite(NEW_YORK)
    [avviso] = avvisi()
    assert avviso.startswith("preferenze: resource non disponibile (") and avviso.endswith("), valori predefiniti")
    assert motivo in avviso


def test_blocco_completo():
    assert blocco_preferenze(Preferenze("inglese", NEW_YORK, None)) == (
        "Preferenze dell'utente: rispondi sempre in inglese. L'utente vive nel fuso orario America/New_York: "
        "ogni volta che chiami ora_corrente senza che l'utente abbia nominato un'altra città, passa sempre "
        "l'argomento fuso=\"America/New_York\" (non ometterlo)."
    )


@pytest.mark.parametrize("stile, frase", [
    ("sintetico", "Stile: risposte brevi ed essenziali, senza tralasciare nulla di ciò che la domanda chiede."),
    ("dettagliato",
     "Stile: risposte dettagliate, con spiegazioni ed esempi quando aiutano, senza uscire dalla domanda."),
])
def test_blocco_con_lo_stile(stile, frase):
    senza = blocco_preferenze(Preferenze("italiano", ROMA, None))
    assert blocco_preferenze(Preferenze("italiano", ROMA, stile)) == f"{senza} {frase}"
    assert "Stile:" not in senza
