"""Test di `main()` senza LM Studio: collegamento dei pezzi e messaggi d'errore all'avvio."""

import sys
import urllib.request
from pathlib import Path

import pytest
from conftest import VALIDO, FlussoDiTesto

import assistente.__main__ as avvio

VARIABILI = (*VALIDO, "LOG_LEVEL")


@pytest.fixture(autouse=True)
def ambiente_pulito(monkeypatch, tmp_path):
    """Cartella senza `.env`, nessuna variabile dell'applicazione e logging di pytest lasciato com'è."""
    monkeypatch.chdir(tmp_path)
    for nome in VARIABILI:
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setattr(avvio, "configura_log", lambda livello: None)


def usa_flussi_finti(monkeypatch, ingresso: bytes = b""):
    """Sostituisce stdin, stdout e stderr con flussi non interattivi in cp1252, come una pipe su Windows.

    Va chiamata dentro il test: pytest rimette i propri flussi all'inizio di ogni fase.
    Restituisce (stdout, stderr); il testo scritto è in `.buffer.getvalue()` dopo `.flush()`.
    """
    uscita, errori = FlussoDiTesto(), FlussoDiTesto()
    monkeypatch.setattr(sys, "stdin", FlussoDiTesto(ingresso))
    monkeypatch.setattr(sys, "stdout", uscita)
    monkeypatch.setattr(sys, "stderr", errori)
    return uscita, errori


def test_main_prepara_i_flussi_non_interattivi_prima_della_chat(monkeypatch):
    uscita, _ = usa_flussi_finti(monkeypatch, "Qual è?\n".encode("utf-8"))
    for nome, valore in VALIDO.items():
        monkeypatch.setenv(nome, valore)
    monkeypatch.setattr(avvio, "leggi_modelli_disponibili", lambda url: [VALIDO["LMSTUDIO_MODEL"]])
    monkeypatch.setattr(avvio, "crea_modello", lambda config: object())
    monkeypatch.setattr(avvio, "costruisci_grafo", lambda modello, strumenti: "grafo")
    ricevuto = []

    def chat_finta(grafo, server, **opzioni):
        ricevuto.append(sys.stdin.readline())
        print("Assistente> \U0001F31E caffè")

    monkeypatch.setattr(avvio, "esegui_chat", chat_finta)
    assert avvio.main() == 0
    uscita.flush()
    assert ricevuto == ["Qual è?\n"]
    assert uscita.buffer.getvalue() == "Assistente> \U0001F31E caffè\n".encode("utf-8")


def esegui_main_con_errore(monkeypatch):
    """Esegue `main()` con flussi finti e restituisce (codice di uscita, testo scritto su stderr)."""
    _, errori = usa_flussi_finti(monkeypatch)
    codice = avvio.main()
    errori.flush()
    return codice, errori.buffer.getvalue().decode("utf-8")


def test_main_file_env_in_utf16_errore_chiaro_e_uscita_1(monkeypatch):
    Path(".env").write_bytes("LMSTUDIO_MODEL=x\n".encode("utf-16"))
    codice, errori = esegui_main_con_errore(monkeypatch)
    assert codice == 1
    assert errori.startswith("Errore: ") and ".env non è in UTF-8" in errori and "Traceback" not in errori


def test_main_url_con_parentesi_errate_errore_chiaro_e_uscita_1(monkeypatch):
    for nome, valore in {**VALIDO, "LMSTUDIO_BASE_URL": "http://[::1/v1"}.items():
        monkeypatch.setenv(nome, valore)
    codice, errori = esegui_main_con_errore(monkeypatch)
    assert codice == 1
    assert errori.startswith("Errore: LMSTUDIO_BASE_URL non è un indirizzo valido") and "Traceback" not in errori


class RispostaFinta:
    """Risposta HTTP minima per `urllib.request.urlopen(...)` usato come gestore di contesto."""

    def __init__(self, corpo: bytes):
        self.corpo = corpo

    def __enter__(self):
        return self

    def __exit__(self, *eccezione):
        return False

    def read(self):
        return self.corpo


def test_main_identificativi_dei_modelli_non_stringa_errore_chiaro_e_uscita_1(monkeypatch):
    for nome, valore in VALIDO.items():
        monkeypatch.setenv(nome, valore)
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda url, timeout: RispostaFinta(b'{"data": [{"id": 1}, {"id": 2}]}'))
    codice, errori = esegui_main_con_errore(monkeypatch)
    assert codice == 1
    assert errori.startswith("Errore: Risposta inattesa da http://localhost:1234/v1/models") \
        and "Traceback" not in errori
