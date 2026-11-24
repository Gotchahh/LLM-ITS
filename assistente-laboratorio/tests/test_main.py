"""Test di `main()` senza LM Studio: collegamento dei pezzi e messaggi d'errore all'avvio."""

import sys
import urllib.request
from pathlib import Path

import pytest
from conftest import VALIDO, FlussoDiTesto
from langchain_core.tools import StructuredTool

import assistente.__main__ as avvio
from assistente.client_mcp import ArgomentoPrompt, DefinizionePrompt, ErroreMCP

ELENCO_PROMPT = [DefinizionePrompt("spiega", "Spiega.", (ArgomentoPrompt("argomento", "", True),))]


@pytest.fixture(autouse=True)
def ambito_del_progetto(monkeypatch):
    """I test di `main` girano anche in cartelle temporanee: l'ambito è quello del progetto."""
    monkeypatch.setenv("AMBITO_FILE", str(Path(__file__).resolve().parent.parent / "ambito.txt"))
    monkeypatch.setenv("REVISORE_FILE", str(Path(__file__).resolve().parent.parent / "revisore.txt"))
    monkeypatch.setenv("RIASSUNTO_FILE", str(Path(__file__).resolve().parent.parent / "riassunto.txt"))


@pytest.fixture(autouse=True)
def servizio_note_presente(monkeypatch):
    """Nessuna connessione vera al servizio delle note (su Windows un rifiuto costa circa 2 s)."""
    monkeypatch.setattr(avvio, "servizio_raggiungibile", lambda url: True)

VARIABILI = (*VALIDO, "LOG_LEVEL")


@pytest.fixture(autouse=True)
def ambiente_pulito(monkeypatch, tmp_path):
    """Cartella senza `.env`, nessuna variabile dell'applicazione e logging di pytest lasciato com'è."""
    monkeypatch.chdir(tmp_path)
    for nome in VARIABILI:
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setattr(avvio, "configura_log", lambda livello: None)
    monkeypatch.setattr(avvio, "carica_strumenti_mcp", lambda: [])
    monkeypatch.setattr(avvio, "leggi_preferenze_mcp", lambda: '{"lingua": "inglese", "fuso": "America/New_York"}')
    monkeypatch.setattr(avvio, "leggi_elenco_prompt", lambda: ELENCO_PROMPT)


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
    monkeypatch.setattr(avvio, "costruisci_grafo", lambda *argomenti, **opzioni: "grafo")
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


def test_main_errore_mcp_all_avvio_uscita_1(monkeypatch):
    for nome, valore in VALIDO.items():
        monkeypatch.setenv(nome, valore)
    monkeypatch.setattr(avvio, "leggi_modelli_disponibili", lambda url: [VALIDO["LMSTUDIO_MODEL"]])
    def discovery_fallita():
        raise ErroreMCP("server MCP calcolatrice non avviato (python -m calcolatrice_mcp): Connection closed")
    monkeypatch.setattr(avvio, "carica_strumenti_mcp", discovery_fallita)
    codice, errori = esegui_main_con_errore(monkeypatch)
    assert codice == 1
    assert errori.startswith("Errore: server MCP calcolatrice non avviato") and "Traceback" not in errori


def test_main_passa_al_grafo_l_orologio_e_gli_strumenti_mcp(monkeypatch):
    usa_flussi_finti(monkeypatch)
    for nome, valore in VALIDO.items():
        monkeypatch.setenv(nome, valore)
    monkeypatch.setattr(avvio, "leggi_modelli_disponibili", lambda url: [VALIDO["LMSTUDIO_MODEL"]])
    monkeypatch.setattr(avvio, "crea_modello", lambda config: object())
    calcola_finta = StructuredTool.from_function(func=lambda espressione: "4", name="calcola", description="prova")
    monkeypatch.setattr(avvio, "carica_strumenti_mcp", lambda: [calcola_finta])
    ricevuti = []
    monkeypatch.setattr(avvio, "costruisci_grafo",
                        lambda modello, strumenti, *altri, **opzioni: ricevuti.append(strumenti) or "grafo")
    monkeypatch.setattr(avvio, "esegui_chat", lambda grafo, server, **opzioni: None)
    assert avvio.main() == 0
    assert [s.name for s in ricevuti[0]] == [
        "ora_corrente", "giorni_tra", "sposta_data", "giorno_settimana", "pasqua", "converti",
        "salva_nota", "elenca_note", "cancella_nota", "calcola",
    ]


def test_main_con_servizio_note_spento_avvisa_e_parte(monkeypatch, caplog):
    usa_flussi_finti(monkeypatch)
    for nome, valore in VALIDO.items():
        monkeypatch.setenv(nome, valore)
    monkeypatch.setattr(avvio, "leggi_modelli_disponibili", lambda url: [VALIDO["LMSTUDIO_MODEL"]])
    monkeypatch.setattr(avvio, "crea_modello", lambda config: object())
    monkeypatch.setattr(avvio, "carica_strumenti_mcp", lambda: [])
    monkeypatch.setattr(avvio, "costruisci_grafo", lambda *argomenti, **opzioni: "grafo")
    avviata = []
    monkeypatch.setattr(avvio, "esegui_chat", lambda grafo, server, **opzioni: avviata.append(True))
    monkeypatch.setattr(avvio, "servizio_raggiungibile", lambda url: False)
    assert avvio.main() == 0
    assert avviata == [True]
    assert any("servizio note non raggiungibile" in m for m in caplog.messages)


def test_main_passa_al_grafo_l_ambito_e_il_modello_del_router(monkeypatch):
    usa_flussi_finti(monkeypatch)
    for nome, valore in VALIDO.items():
        monkeypatch.setenv(nome, valore)
    monkeypatch.setattr(avvio, "leggi_modelli_disponibili", lambda url: [VALIDO["LMSTUDIO_MODEL"]])
    monkeypatch.setattr(avvio, "crea_modello", lambda config: "agente")
    monkeypatch.setattr(avvio, "crea_modello_router", lambda config: "router")
    monkeypatch.setattr(avvio, "crea_modello_riassunto", lambda config: "riassunto")
    monkeypatch.setattr(avvio, "carica_strumenti_mcp", lambda: [])
    ricevuti = []
    monkeypatch.setattr(avvio, "costruisci_grafo",
                        lambda modello, strumenti, ambito, router, revisore, revisioni, **riassunto:
                        ricevuti.append((modello, ambito, router, revisore, revisioni, riassunto)) or "grafo")
    monkeypatch.setattr(avvio, "esegui_chat", lambda grafo, server, **opzioni: None)
    assert avvio.main() == 0
    modello, ambito, router, revisore, revisioni, riassunto = ricevuti[0]
    assert (modello, router, revisioni) == ("agente", "router", 2) and "laboratorio" in ambito
    assert "coerente" in revisore
    assert "nome" in riassunto["riassunto_istruzioni"]
    assert (riassunto["riassunto_soglia"], riassunto["riassunto_turni"]) == (20, 2)
    assert riassunto["modello_riassunto"] == "riassunto"


def test_main_ambito_mancante_uscita_1(monkeypatch, tmp_path):
    for nome, valore in VALIDO.items():
        monkeypatch.setenv(nome, valore)
    monkeypatch.setenv("AMBITO_FILE", str(tmp_path / "manca.txt"))
    monkeypatch.setattr(avvio, "leggi_modelli_disponibili", lambda url: [VALIDO["LMSTUDIO_MODEL"]])
    monkeypatch.setattr(avvio, "carica_strumenti_mcp", lambda: [])
    codice, errori = esegui_main_con_errore(monkeypatch)
    assert codice == 1 and errori.startswith("Errore: ") and "AMBITO_FILE" in errori and "Traceback" not in errori


def test_main_revisioni_max_non_valido_uscita_1(monkeypatch):
    for nome, valore in VALIDO.items():
        monkeypatch.setenv(nome, valore)
    monkeypatch.setenv("REVISIONI_MAX", "due")
    codice, errori = esegui_main_con_errore(monkeypatch)
    assert codice == 1 and errori.startswith("Errore: REVISIONI_MAX") and "Traceback" not in errori


def test_main_riassunto_mancante_uscita_1(monkeypatch, tmp_path):
    for nome, valore in VALIDO.items():
        monkeypatch.setenv(nome, valore)
    monkeypatch.setenv("RIASSUNTO_FILE", str(tmp_path / "manca.txt"))
    monkeypatch.setattr(avvio, "leggi_modelli_disponibili", lambda url: [VALIDO["LMSTUDIO_MODEL"]])
    codice, errori = esegui_main_con_errore(monkeypatch)
    assert codice == 1 and errori.startswith("Errore: ") and "RIASSUNTO_FILE" in errori and "Traceback" not in errori


def test_main_riassunto_soglia_non_valida_uscita_1(monkeypatch):
    for nome, valore in VALIDO.items():
        monkeypatch.setenv(nome, valore)
    monkeypatch.setenv("RIASSUNTO_SOGLIA", "0")
    codice, errori = esegui_main_con_errore(monkeypatch)
    assert codice == 1 and errori.startswith("Errore: RIASSUNTO_SOGLIA") and "Traceback" not in errori


def main_con_grafo_catturato(monkeypatch):
    """Esegue `main()` con il modello e la chat finti e restituisce (codice, opzioni passate a `costruisci_grafo`)."""
    usa_flussi_finti(monkeypatch)
    monkeypatch.setattr(avvio, "leggi_modelli_disponibili", lambda url: [VALIDO["LMSTUDIO_MODEL"]])
    monkeypatch.setattr(avvio, "crea_modello", lambda config: object())
    ricevute = []
    monkeypatch.setattr(avvio, "costruisci_grafo", lambda *argomenti, **opzioni: ricevute.append(opzioni) or "grafo")
    monkeypatch.setattr(avvio, "esegui_chat", lambda grafo, server, **opzioni: None)
    codice = avvio.main()
    return codice, ricevute[0]


def test_main_passa_al_grafo_le_preferenze_lette(monkeypatch):
    for nome, valore in VALIDO.items():
        monkeypatch.setenv(nome, valore)
    codice, opzioni = main_con_grafo_catturato(monkeypatch)
    assert codice == 0
    assert "rispondi sempre in inglese" in opzioni["preferenze"] and "America/New_York" in opzioni["preferenze"]


def test_main_preferenze_illeggibili_parte_con_i_predefiniti(monkeypatch, caplog):
    for nome, valore in {**VALIDO, "APP_TIMEZONE": "Asia/Tokyo"}.items():
        monkeypatch.setenv(nome, valore)

    def lettura_fallita():
        raise ErroreMCP("resource utente://preferenze non letta (python.exe -m preferenze_mcp): Connection closed")

    monkeypatch.setattr(avvio, "leggi_preferenze_mcp", lettura_fallita)
    codice, opzioni = main_con_grafo_catturato(monkeypatch)
    assert codice == 0
    assert "rispondi sempre in italiano" in opzioni["preferenze"] and "Asia/Tokyo" in opzioni["preferenze"]
    assert "Stile:" not in opzioni["preferenze"]
    assert any(m.startswith("preferenze: resource non disponibile (") for m in caplog.messages)


def main_con_chat_catturata(monkeypatch):
    """Esegue `main()` con il modello e il grafo finti e restituisce (codice, opzioni passate a `esegui_chat`)."""
    for nome, valore in VALIDO.items():
        monkeypatch.setenv(nome, valore)
    usa_flussi_finti(monkeypatch)
    monkeypatch.setattr(avvio, "leggi_modelli_disponibili", lambda url: [VALIDO["LMSTUDIO_MODEL"]])
    monkeypatch.setattr(avvio, "crea_modello", lambda config: object())
    monkeypatch.setattr(avvio, "costruisci_grafo", lambda *argomenti, **opzioni: "grafo")
    ricevute = []
    monkeypatch.setattr(avvio, "esegui_chat", lambda grafo, server, **opzioni: ricevute.append(opzioni))
    codice = avvio.main()
    return codice, ricevute[0]


def test_main_passa_alla_chat_l_elenco_e_la_richiesta_dei_prompt(monkeypatch):
    codice, opzioni = main_con_chat_catturata(monkeypatch)
    assert codice == 0
    assert opzioni["elenco_prompt"] == ELENCO_PROMPT and opzioni["richiedi_prompt"] is avvio.richiedi_prompt


def test_main_elenco_dei_prompt_illeggibile_la_chat_parte_senza_prompt(monkeypatch, caplog):
    def lettura_fallita():
        raise ErroreMCP("elenco dei prompt non letto dal server MCP prompt (python.exe -m prompt_mcp): x")

    monkeypatch.setattr(avvio, "leggi_elenco_prompt", lettura_fallita)
    codice, opzioni = main_con_chat_catturata(monkeypatch)
    assert codice == 0 and opzioni["elenco_prompt"] is None
    assert any(m.startswith("prompt: elenco non disponibile (") for m in caplog.messages)
