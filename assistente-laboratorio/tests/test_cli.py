import io
import logging

import pytest
from conftest import SERVER_FINTO, ModelloFinto, chat
from langchain_core.messages import AIMessage
from langgraph.errors import GraphRecursionError

from assistente.cli import IndicatoreAttesa, crea_indicatore_attesa
from assistente.grafo import costruisci_grafo


def test_righe_vuote_e_spazi_ignorati():                              # Review Focus 1
    finto = ModelloFinto([])
    uscita = chat(costruisci_grafo(finto, []), ["", "   ", "\t", "/esci"])
    assert finto.chiamate == [] and uscita[-1] == "Alla prossima!"


def test_bom_iniziale_dell_input_da_pipe_non_rompe_riga_vuota_e_comando():
    finto = ModelloFinto([])
    uscita = chat(costruisci_grafo(finto, []), ["\ufeff   ", "\ufeff/esci"])
    assert finto.chiamate == [] and uscita == ["Alla prossima!"]


def test_bom_iniziale_non_arriva_al_modello():
    finto = ModelloFinto([AIMessage("Ciao!")])
    chat(costruisci_grafo(finto, []), ["\ufeffciao", "/esci"])
    assert finto.chiamate[0][1].type == "human" and finto.chiamate[0][1].content == "ciao"


def test_comandi_normalizzati_e_sconosciuti():
    finto = ModelloFinto([])
    uscita = chat(costruisci_grafo(finto, []), ["/aiuto", "  /ESCI  "])
    assert "Comando sconosciuto. Comandi disponibili: /esci" in uscita and finto.chiamate == []


def test_esci_termina_senza_chiamare_il_modello():
    finto = ModelloFinto([])
    uscita = chat(costruisci_grafo(finto, []), ["/esci", "non letta"])
    assert uscita == ["Alla prossima!"] and finto.chiamate == []


def test_la_chat_stampa_la_risposta_e_conserva_la_cronologia_tra_i_turni():
    finto = ModelloFinto([AIMessage("R1"), AIMessage("R2")])
    uscita = chat(costruisci_grafo(finto, []), ["D1", "D2", "/esci"])
    assert uscita == ["Assistente> R1", "Assistente> R2", "Alla prossima!"]
    assert [m.type for m in finto.chiamate[1]] == ["system", "human", "ai", "human"]


def test_errore_di_connessione_turno_annullato_e_chat_prosegue():
    finto = ModelloFinto([ConnectionError("Connection refused"), AIMessage("Eccomi")])
    uscita = chat(costruisci_grafo(finto, []), ["D1", "D2", "/esci"])
    assert any(r.startswith("Errore: nessuna risposta valida da LM Studio (http://server/v1)") for r in uscita)
    assert "Assistente> Eccomi" in uscita
    assert [m.type for m in finto.chiamate[1]] == ["system", "human"]   # D1 non è rimasta in cronologia


def test_messaggio_dell_errore_generico_con_classe_e_dettaglio():
    finto = ModelloFinto([TimeoutError("Request timed out")])
    uscita = chat(costruisci_grafo(finto, []), ["D1"])
    assert uscita[0] == (f"Errore: nessuna risposta valida da LM Studio ({SERVER_FINTO}): "
                         "TimeoutError: Request timed out. Turno annullato.")


def test_errore_generico_con_traceback_nel_log_di_debug(caplog):
    caplog.set_level(logging.DEBUG, logger="assistente")
    chat(costruisci_grafo(ModelloFinto([ConnectionError("Connection refused")]), []), ["D1"])
    con_traceback = [r for r in caplog.records if r.name.startswith("assistente") and r.exc_info]
    assert [r.levelname for r in con_traceback] == ["DEBUG"]
    assert isinstance(con_traceback[0].exc_info[1], ConnectionError)


def test_limite_di_passaggi_raggiunto():
    finto = ModelloFinto([GraphRecursionError("troppi passaggi")])
    uscita = chat(costruisci_grafo(finto, []), ["D1"])
    assert uscita[0] == "Errore: limite di 10 passaggi raggiunto. Turno annullato."


def test_risposta_non_valida_del_modello():
    uscita = chat(costruisci_grafo(ModelloFinto([AIMessage("")]), []), ["D1"])
    assert uscita[0] == "Errore: il modello non ha prodotto una risposta valida. Turno annullato."


def test_ctrl_c_durante_il_turno():                                    # Review Focus 2
    uscita = chat(costruisci_grafo(ModelloFinto([KeyboardInterrupt()]), []), ["D1"])
    assert uscita[-1] == "Alla prossima!"


def test_fine_input():
    assert chat(costruisci_grafo(ModelloFinto([]), []), [])[-1] == "Alla prossima!"


class TerminaleFinto(io.StringIO):
    """Stream di testo che si dichiara un terminale."""

    def isatty(self):
        return True


def test_attesa_mostrata_e_nascosta_prima_della_risposta():
    uscita = chat(costruisci_grafo(ModelloFinto([AIMessage("R1")]), []), ["D1", "/esci"], con_attesa=True)
    assert uscita == ["[mostra]", "[nascondi]", "Assistente> R1", "Alla prossima!"]


def test_attesa_nascosta_prima_dell_errore():
    finto = ModelloFinto([ConnectionError("Connection refused")])
    uscita = chat(costruisci_grafo(finto, []), ["D1"], con_attesa=True)
    assert uscita[:2] == ["[mostra]", "[nascondi]"] and uscita[2].startswith("Errore: ")


def test_attesa_nascosta_prima_del_saluto_dopo_ctrl_c():
    uscita = chat(costruisci_grafo(ModelloFinto([KeyboardInterrupt()]), []), ["D1"], con_attesa=True)
    assert uscita == ["[mostra]", "[nascondi]", "Alla prossima!"]


def test_righe_vuote_e_comandi_senza_attesa():
    uscita = chat(costruisci_grafo(ModelloFinto([]), []), ["", "   ", "/aiuto", "/esci"], con_attesa=True)
    assert uscita == ["Comando sconosciuto. Comandi disponibili: /esci", "Alla prossima!"]


def test_indicatore_scrive_e_cancella_esattamente():
    uscita = io.StringIO()
    indicatore = IndicatoreAttesa(uscita)
    indicatore.mostra()
    assert uscita.getvalue() == "Ragionando..."
    indicatore.nascondi()
    indicatore.nascondi()                     # già nascosta: non scrive altro
    assert uscita.getvalue() == "Ragionando..." + "\b" * 13 + " " * 13 + "\b" * 13


def test_indicatore_non_mostrato_non_cancella_nulla():
    uscita = io.StringIO()
    IndicatoreAttesa(uscita).nascondi()
    assert uscita.getvalue() == ""


@pytest.mark.parametrize("livello, ingresso, uscita, atteso", [
    ("INFO", TerminaleFinto(), TerminaleFinto(), False),
    ("DEBUG", TerminaleFinto(), TerminaleFinto(), False),
    ("WARNING", io.StringIO(), TerminaleFinto(), False),
    ("WARNING", TerminaleFinto(), io.StringIO(), False),
    ("WARNING", TerminaleFinto(), TerminaleFinto(), True),
    ("ERROR", TerminaleFinto(), TerminaleFinto(), True),
])
def test_scelta_dell_indicatore(livello, ingresso, uscita, atteso):
    assert isinstance(crea_indicatore_attesa(livello, ingresso, uscita), IndicatoreAttesa) is atteso
