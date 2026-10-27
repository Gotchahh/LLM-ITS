import logging

import pytest

from assistente.config import (
    ErroreConfigurazione,
    carica_configurazione,
    configura_log,
    leggi_file_env,
)

VALIDO = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "google/gemma-4-e4b",
          "APP_TIMEZONE": "Europe/Rome"}


@pytest.fixture
def log_isolati():
    """Salva e ripristina handler e livelli della radice e del logger `assistente`."""
    radice = logging.getLogger()
    app = logging.getLogger("assistente")
    handler_radice, livello_radice = radice.handlers[:], radice.level
    handler_app, livello_app = app.handlers[:], app.level
    yield
    radice.handlers[:] = handler_radice
    radice.setLevel(livello_radice)
    app.handlers[:] = handler_app
    app.setLevel(livello_app)


def test_configurazione_valida():
    c = carica_configurazione(VALIDO)
    assert (c.base_url, c.modello, c.fuso.key, c.livello_log) == (
        "http://localhost:1234/v1", "google/gemma-4-e4b", "Europe/Rome", "INFO")


def test_ambiente_vuoto_nomina_variabili_e_file_di_esempio():          # Review Focus 3
    with pytest.raises(ErroreConfigurazione) as e:
        carica_configurazione({})
    for atteso in ("LMSTUDIO_BASE_URL", "LMSTUDIO_MODEL", "APP_TIMEZONE", ".env.example"):
        assert atteso in str(e.value)


def test_modello_vuoto_e_mancante():
    with pytest.raises(ErroreConfigurazione, match="LMSTUDIO_MODEL"):
        carica_configurazione({**VALIDO, "LMSTUDIO_MODEL": "  "})


def test_url_senza_schema_rifiutato():
    with pytest.raises(ErroreConfigurazione, match="LMSTUDIO_BASE_URL"):
        carica_configurazione({**VALIDO, "LMSTUDIO_BASE_URL": "localhost:1234/v1"})


def test_url_con_barra_finale_normalizzato():                          # Review Focus 4
    assert carica_configurazione({**VALIDO, "LMSTUDIO_BASE_URL": "http://localhost:1234/v1/"}).base_url \
        == "http://localhost:1234/v1"


def test_fuso_non_valido():
    with pytest.raises(ErroreConfigurazione, match="APP_TIMEZONE"):
        carica_configurazione({**VALIDO, "APP_TIMEZONE": "Roma"})


def test_livello_log_minuscolo_accettato():                            # Review Focus 5
    assert carica_configurazione({**VALIDO, "LOG_LEVEL": "info"}).livello_log == "INFO"


def test_livello_log_non_valido():
    with pytest.raises(ErroreConfigurazione, match="LOG_LEVEL"):
        carica_configurazione({**VALIDO, "LOG_LEVEL": "TANTO"})


def test_file_env_con_bom_e_crlf(tmp_path):
    f = tmp_path / ".env"
    f.write_bytes("﻿LMSTUDIO_MODEL=google/gemma-4-e4b\r\nAPP_TIMEZONE=Europe/Rome\r\n".encode("utf-8"))
    assert leggi_file_env(f) == {"LMSTUDIO_MODEL": "google/gemma-4-e4b", "APP_TIMEZONE": "Europe/Rome"}


def test_file_env_assente(tmp_path):
    assert leggi_file_env(tmp_path / "manca.env") == {}


def test_log_esterni_restano_a_warning(log_isolati):
    configura_log("INFO")
    assert logging.getLogger("assistente.grafo").isEnabledFor(logging.INFO)
    assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)


def test_modalita_silenziosa(log_isolati):
    configura_log("WARNING")
    assert not logging.getLogger("assistente.grafo").isEnabledFor(logging.INFO)
