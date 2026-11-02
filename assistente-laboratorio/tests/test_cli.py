import io
import logging

import pytest
from conftest import SERVER_FINTO, FlussoDiTesto, ModelloFinto, chat
from langchain_core.messages import AIMessage
from langgraph.errors import GraphRecursionError

from assistente.cli import IndicatoreAttesa, crea_indicatore_attesa, prepara_terminale
from assistente.grafo import costruisci_grafo


def test_righe_vuote_e_spazi_ignorati():                              # Review Focus 1
    finto = ModelloFinto([])
    uscita = chat(costruisci_grafo(finto, []), ["", "   ", "\t", "/esci"])
    assert finto.chiamate == [] and uscita[-1] == "Alla prossima!"


def test_bom_iniziale_dell_input_da_pipe_non_rompe_riga_vuota_e_comando():
    finto = ModelloFinto([])
    uscita = chat(costruisci_grafo(finto, []), ["\ufeff   ", "\ufeff/esci"])
    assert finto.chiamate == [] and uscita == ["Alla prossima!"]


def test_piu_bom_iniziali_non_rompono_riga_vuota_e_comando():
    # La pipe di PowerShell 5.1 può anteporre due BOM (uno dell'encoding di $OutputEncoding, uno della console).
    finto = ModelloFinto([])
    uscita = chat(costruisci_grafo(finto, []), ["\ufeff\ufeff   ", "\ufeff\ufeff/esci"])
    assert finto.chiamate == [] and uscita == ["Alla prossima!"]


def test_bom_iniziale_non_arriva_al_modello():
    finto = ModelloFinto([AIMessage("Ciao!")])
    chat(costruisci_grafo(finto, []), ["\ufeffciao", "/esci"])
    assert finto.chiamate[0][1].type == "human" and finto.chiamate[0][1].content == "ciao"


def test_comandi_normalizzati_e_sconosciuti():
    finto = ModelloFinto([])
    uscita = chat(costruisci_grafo(finto, []), ["/aiuto", "  /ESCI  "])
    assert "Comando sconosciuto. Comandi disponibili: /esci, /log" in uscita and finto.chiamate == []


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
    # Due righe in ingresso: se Ctrl+C venisse ignorato, la chat leggerebbe D2 e chiamerebbe il modello.
    finto = ModelloFinto([KeyboardInterrupt(), AIMessage("R2")])
    uscita = chat(costruisci_grafo(finto, []), ["D1", "D2"])
    assert uscita == ["Alla prossima!"]
    assert len(finto.chiamate) == 1


def test_fine_input():
    assert chat(costruisci_grafo(ModelloFinto([]), []), [])[-1] == "Alla prossima!"


class TerminaleFinto(io.StringIO):
    """Stream di testo che si dichiara un terminale."""

    def isatty(self):
        return True


def test_attesa_mostrata_e_nascosta_prima_della_risposta():
    finto = ModelloFinto([AIMessage("R1")])
    uscita = chat(costruisci_grafo(finto, []), ["D1", "/esci"], con_attesa=True, livello_log="WARNING")
    assert uscita == ["[mostra]", "[nascondi]", "Assistente> R1", "Alla prossima!"]


def test_attesa_nascosta_prima_dell_errore():
    finto = ModelloFinto([ConnectionError("Connection refused")])
    uscita = chat(costruisci_grafo(finto, []), ["D1"], con_attesa=True, livello_log="WARNING")
    assert uscita[:2] == ["[mostra]", "[nascondi]"] and uscita[2].startswith("Errore: ")


def test_attesa_nascosta_prima_del_saluto_dopo_ctrl_c():
    finto = ModelloFinto([KeyboardInterrupt(), AIMessage("R2")])
    uscita = chat(costruisci_grafo(finto, []), ["D1", "D2"], con_attesa=True, livello_log="WARNING")
    assert uscita == ["[mostra]", "[nascondi]", "Alla prossima!"]
    assert len(finto.chiamate) == 1


def test_righe_vuote_e_comandi_senza_attesa():
    righe = ["", "   ", "/aiuto", "/esci"]
    uscita = chat(costruisci_grafo(ModelloFinto([]), []), righe, con_attesa=True, livello_log="WARNING")
    assert uscita == ["Comando sconosciuto. Comandi disponibili: /esci, /log", "Alla prossima!"]


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


@pytest.mark.parametrize("ingresso, uscita, atteso", [
    (io.StringIO(), TerminaleFinto(), False),
    (TerminaleFinto(), io.StringIO(), False),
    (TerminaleFinto(), TerminaleFinto(), True),
])
def test_scelta_dell_indicatore(ingresso, uscita, atteso):
    assert isinstance(crea_indicatore_attesa(ingresso, uscita), IndicatoreAttesa) is atteso


def test_ingresso_non_interattivo_letto_come_utf8():
    # Windows decodificherebbe una pipe con la codifica ANSI (cp1252): «è» diventerebbe «Ã¨».
    ingresso = FlussoDiTesto("Qual è il colore?\n".encode("utf-8"))
    prepara_terminale(ingresso)
    assert ingresso.readline() == "Qual è il colore?\n"


def test_bom_utf8_dell_ingresso_arriva_come_un_solo_carattere_da_togliere():
    # Letto come cp1252 il BOM sarebbe «ï»¿», che la chat non riconosce e non toglie.
    ingresso = FlussoDiTesto(b"\xef\xbb\xbf/esci\n")
    prepara_terminale(ingresso)
    assert ingresso.readline() == "\ufeff/esci\n"


def test_byte_non_utf8_nell_ingresso_non_interrompono_la_lettura():
    ingresso = FlussoDiTesto(b"caff\xe8\nsecondo\n")
    prepara_terminale(ingresso)
    assert ingresso.readlines() == ["caff\ufffd\n", "secondo\n"]


def test_uscita_non_interattiva_scrive_utf8_anche_fuori_da_cp1252():
    uscita = FlussoDiTesto()
    prepara_terminale(uscita)
    print("Assistente> sole \U0001F31E, caffè", file=uscita, flush=True)
    assert uscita.buffer.getvalue() == "Assistente> sole \U0001F31E, caffè\n".encode("utf-8")


def test_carattere_non_codificabile_nell_uscita_diventa_punto_interrogativo():
    uscita = FlussoDiTesto()
    prepara_terminale(uscita)
    print("a\ud83db", file=uscita, flush=True)        # surrogato isolato: non codificabile nemmeno in UTF-8
    assert uscita.buffer.getvalue() == b"a?b\n"


def test_terminale_interattivo_lasciato_com_e():
    terminale = FlussoDiTesto(interattivo=True)
    prepara_terminale(terminale)
    assert (terminale.encoding, terminale.errors) == ("cp1252", "strict")


def test_ogni_flusso_e_valutato_da_solo():
    ingresso_terminale = FlussoDiTesto(interattivo=True)
    uscita_pipe = FlussoDiTesto()
    prepara_terminale(ingresso_terminale, uscita_pipe)
    assert ingresso_terminale.encoding == "cp1252" and uscita_pipe.encoding == "utf-8"


NASCOSTI = "Log nascosti: solo dialogo. Scrivi /log per mostrarli."
VISIBILI = "Log visibili. Scrivi /log per nasconderli."


def test_log_alterna_con_messaggi_e_senza_chiamare_il_modello():
    finto = ModelloFinto([])
    uscita = chat(costruisci_grafo(finto, []), ["/log", "  /LOG  ", "/log on", "/esci"])
    assert uscita == [NASCOSTI, VISIBILI, "Comando sconosciuto. Comandi disponibili: /esci, /log",
                      "Alla prossima!"]
    assert finto.chiamate == []


def test_log_partendo_dalla_modalita_silenziosa():
    uscita = chat(costruisci_grafo(ModelloFinto([]), []), ["/log"], livello_log="WARNING")
    assert uscita == [VISIBILI, "Alla prossima!"]


def test_log_nasconde_e_rimostra_i_passaggi_nella_stessa_chat(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    finto = ModelloFinto([AIMessage("R1"), AIMessage("R2"), AIMessage("R3")])
    chat(costruisci_grafo(finto, []), ["D1", "/log", "D2", "/log", "D3"])
    chiamate = [r.getMessage() for r in caplog.records if r.getMessage().startswith("nodo_llm: chiamata")]
    # D2 non lascia log; D3 riceve 6 messaggi: il comando /log non è entrato nella cronologia
    assert chiamate == ["nodo_llm: chiamata al modello (2 messaggi)",
                        "nodo_llm: chiamata al modello (6 messaggi)"]


def test_attesa_compare_dopo_log_che_nasconde():
    finto = ModelloFinto([AIMessage("R1"), AIMessage("R2")])
    uscita = chat(costruisci_grafo(finto, []), ["D1", "/log", "D2"], con_attesa=True)
    assert uscita == ["Assistente> R1", NASCOSTI, "[mostra]", "[nascondi]", "Assistente> R2",
                      "Alla prossima!"]


def test_attesa_sparisce_dopo_log_che_mostra():
    finto = ModelloFinto([AIMessage("R1"), AIMessage("R2")])
    uscita = chat(costruisci_grafo(finto, []), ["D1", "/log", "D2"], con_attesa=True, livello_log="WARNING")
    assert uscita == ["[mostra]", "[nascondi]", "Assistente> R1", VISIBILI, "Assistente> R2",
                      "Alla prossima!"]
