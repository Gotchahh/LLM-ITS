import pytest
from conftest import VALIDO

from assistente.config import ErroreConfigurazione, carica_configurazione
from assistente.modello import (
    ErroreServer,
    crea_modello,
    estrai_identificativi,
    leggi_modelli_disponibili,
    verifica_modello,
)


def test_estrai_identificativi():
    corpo = b'{"data": [{"id": "google/gemma-4-e4b"}, {"id": "google/gemma-4-e2b"}], "object": "list"}'
    assert estrai_identificativi(corpo) == ["google/gemma-4-e4b", "google/gemma-4-e2b"]


def test_estrai_identificativi_json_non_valido():
    with pytest.raises(ErroreServer):
        estrai_identificativi(b"<html>")


@pytest.mark.parametrize("corpo", [b"{}", b"[]", b'{"data": 5}', b'{"data": [{"nome": "x"}]}'])
def test_estrai_identificativi_struttura_inattesa(corpo):
    with pytest.raises(ErroreServer):
        estrai_identificativi(corpo)


def test_modello_presente():
    verifica_modello("google/gemma-4-e4b", ["google/gemma-4-e4b"])


def test_modello_assente_elenca_i_disponibili():
    with pytest.raises(ErroreConfigurazione) as e:
        verifica_modello("gemma", ["google/gemma-4-e4b", "google/gemma-4-e2b"])
    assert "google/gemma-4-e4b" in str(e.value) and "google/gemma-4-e2b" in str(e.value)


def test_server_irraggiungibile():
    with pytest.raises(ErroreServer, match="127.0.0.1:9"):
        leggi_modelli_disponibili("http://127.0.0.1:9/v1", timeout=1.0)


def test_crea_modello_usa_la_configurazione():
    m = crea_modello(carica_configurazione(VALIDO))
    assert (m.model_name, m.temperature, m.max_retries) == ("google/gemma-4-e4b", 0, 1)
    assert str(m.openai_api_base).rstrip("/") == "http://localhost:1234/v1"
