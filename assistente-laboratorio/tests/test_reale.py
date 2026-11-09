"""Prove con LM Studio attivo: `python -m pytest -m reale -v` (escluse di default)."""

import os
from datetime import datetime
from pathlib import Path

import pytest

from assistente.calendario import crea_strumenti_calendario, leggi_data
from assistente.client_mcp import carica_strumenti_mcp
from assistente.config import carica_configurazione, leggi_file_env
from assistente.convertitore import crea_strumento_convertitore
from assistente.grafo import costruisci_grafo, esegui_turno
from assistente.modello import crea_modello, leggi_modelli_disponibili, verifica_modello
from assistente.note import crea_strumenti_note
from assistente.strumenti import crea_strumento_orologio

pytestmark = pytest.mark.reale

FILE_ENV = Path(__file__).resolve().parent.parent / ".env"


@pytest.fixture(scope="module")
def config():
    """Configurazione di `.env` e dell'ambiente, come in `main`."""
    return carica_configurazione({**leggi_file_env(FILE_ENV), **os.environ})


@pytest.fixture(scope="module")
def grafo(config, servizio_note):
    """Grafo collegato al modello reale, con gli stessi strumenti di `main`."""
    verifica_modello(config.modello, leggi_modelli_disponibili(config.base_url))
    strumenti = [
        crea_strumento_orologio(config.fuso),
        *crea_strumenti_calendario(config.fuso),
        crea_strumento_convertitore(),
        *crea_strumenti_note(servizio_note, config.fuso),
        *carica_strumenti_mcp(),
    ]
    return costruisci_grafo(crea_modello(config), strumenti)


def test_reale_risposta_ordinaria(grafo):
    cronologia = esegui_turno(grafo, [], "Spiegami in una frase cos'è un grafo.")
    assert cronologia[-1].type == "ai" and cronologia[-1].text.strip()
    assert "tool" not in [m.type for m in cronologia]
    assert "tool_call" not in cronologia[-1].text.lower()


def test_reale_cronologia(grafo):
    cronologia = esegui_turno(grafo, [], "Il mio colore preferito è il verde.")
    cronologia = esegui_turno(grafo, cronologia, "Qual è il mio colore preferito?")
    assert "verde" in cronologia[-1].text.lower()


def nomi_strumenti(cronologia):
    """Nomi degli strumenti eseguiti nella cronologia, nell'ordine."""
    return [m.name for m in cronologia if m.type == "tool"]


def test_reale_due_domande_sull_ora(grafo):
    # Il modello può chiamare l'orologio più di una volta nello stesso turno: ne serve almeno una per turno.
    primo = esegui_turno(grafo, [], "Che ore sono?")
    dopo_il_primo = nomi_strumenti(primo)
    assert dopo_il_primo and set(dopo_il_primo) == {"ora_corrente"}
    secondo = esegui_turno(grafo, primo, "E adesso che ore sono?")
    dopo_il_secondo = nomi_strumenti(secondo)
    assert set(dopo_il_secondo) == {"ora_corrente"} and len(dopo_il_secondo) > len(dopo_il_primo)


def test_reale_ora_di_un_altra_citta(grafo):
    cronologia = esegui_turno(grafo, [], "Che ore sono a New York?")
    risultati = [m.content for m in cronologia if m.type == "tool" and m.name == "ora_corrente"]
    assert any(r.endswith("(America/New_York)") for r in risultati)


def test_reale_calcolo(grafo):
    cronologia = esegui_turno(grafo, [], "Quanto fa 12,5 per 8 meno 3?")
    risultati = [m.content for m in cronologia if m.type == "tool" and m.name == "calcola"]
    assert "97" in risultati and "97" in cronologia[-1].text


def test_reale_conversione_lunghezza(grafo):
    cronologia = esegui_turno(grafo, [], "Quanti metri sono 4 cm?")
    risultati = [m.content for m in cronologia if m.type == "tool" and m.name == "converti"]
    assert "4 cm = 0,04 m" in risultati and "0,04" in cronologia[-1].text


def test_reale_conversione_temperatura(grafo):
    cronologia = esegui_turno(grafo, [], "Quanti gradi Fahrenheit sono 20 °C?")
    risultati = [m.content for m in cronologia if m.type == "tool" and m.name == "converti"]
    assert "20 °C = 68 °F" in risultati and "68" in cronologia[-1].text


def test_reale_giorni_al_25_dicembre(grafo, config):
    oggi = datetime.now(config.fuso).date()
    n = (leggi_data("12-25", oggi) - oggi).days
    cronologia = esegui_turno(grafo, [], "Quanti giorni mancano al 25 dicembre?")
    risultati = [m.content for m in cronologia if m.type == "tool" and m.name == "giorni_tra"]
    atteso = "è oggi" if n == 0 else f"mancano {n} giorni"
    assert any(r.endswith(atteso) for r in risultati)
    assert n == 0 or str(n) in cronologia[-1].text


def test_reale_pasqua_2027(grafo):
    cronologia = esegui_turno(grafo, [], "Che giorno è Pasqua nel 2027?")
    risultati = [m.content for m in cronologia if m.type == "tool" and m.name == "pasqua"]
    assert "Pasqua 2027: domenica 28 marzo 2027" in risultati
    assert "28 marzo" in cronologia[-1].text


def test_reale_note(grafo):
    salvataggio = esegui_turno(grafo, [], "Segnati che il microscopio 2 va calibrato.")
    salvate = [m for m in salvataggio if m.type == "tool" and m.name == "salva_nota"]
    assert any(m.status == "success" for m in salvate)
    elenco = esegui_turno(grafo, [], "Che note ho?")
    risultati = [m.content for m in elenco if m.type == "tool" and m.name == "elenca_note"]
    assert any("microscopio 2" in r for r in risultati)
    assert "microscopio" in elenco[-1].text.lower()
