import logging

from conftest import SERVER_FINTO, ModelloFinto, chat
from langchain_core.messages import AIMessage
from langgraph.errors import GraphRecursionError

from assistente.grafo import costruisci_grafo


def test_righe_vuote_e_spazi_ignorati():                              # Review Focus 1
    finto = ModelloFinto([])
    uscita = chat(costruisci_grafo(finto, []), ["", "   ", "\t", "/esci"])
    assert finto.chiamate == [] and uscita[-1] == "Alla prossima!"


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
