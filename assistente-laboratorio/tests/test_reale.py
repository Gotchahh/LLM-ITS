"""Prove con LM Studio attivo: `python -m pytest -m reale -v` (escluse di default)."""

import os
from pathlib import Path

import pytest

from assistente.config import carica_configurazione, leggi_file_env
from assistente.grafo import costruisci_grafo, esegui_turno
from assistente.modello import crea_modello, leggi_modelli_disponibili, verifica_modello

pytestmark = pytest.mark.reale

FILE_ENV = Path(__file__).resolve().parent.parent / ".env"


@pytest.fixture(scope="module")
def grafo():
    """Grafo collegato al modello reale, con la configurazione di `.env` e dell'ambiente come in `main`."""
    config = carica_configurazione({**leggi_file_env(FILE_ENV), **os.environ})
    verifica_modello(config.modello, leggi_modelli_disponibili(config.base_url))
    return costruisci_grafo(crea_modello(config), [])


def test_reale_risposta_ordinaria(grafo):
    cronologia = esegui_turno(grafo, [], "Spiegami in una frase cos'è un grafo.")
    assert cronologia[-1].type == "ai" and cronologia[-1].text.strip()
    assert "tool" not in [m.type for m in cronologia]


def test_reale_cronologia(grafo):
    cronologia = esegui_turno(grafo, [], "Il mio colore preferito è il verde.")
    cronologia = esegui_turno(grafo, cronologia, "Qual è il mio colore preferito?")
    assert "verde" in cronologia[-1].text.lower()
