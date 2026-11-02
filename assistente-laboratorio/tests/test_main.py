"""Test di `main()` senza LM Studio: collegamento dei pezzi e messaggi d'errore all'avvio."""

import sys

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

