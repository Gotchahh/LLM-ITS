import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from conftest import ModelloFinto, chat, decisione, porta_libera, valutazione
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool, ToolException, tool
from langgraph.errors import GraphRecursionError

from assistente.grafo import (
    LIMITE_PASSAGGI,
    PROMPT_DI_SISTEMA,
    RispostaNonValida,
    costruisci_grafo,
    esegui_turno,
    esegui_turno_con_riassunto,
)
from assistente.calendario import crea_strumenti_calendario
from assistente.convertitore import crea_strumento_convertitore
from assistente.note import crea_strumenti_note
from assistente.strumenti import crea_strumento_orologio

orologio = crea_strumento_orologio(
    ZoneInfo("Europe/Rome"), adesso=lambda: datetime(2026, 10, 26, 15, 42, 10, tzinfo=UTC))


def chiamata(id, args=None):
    """Risposta del modello che chiede `ora_corrente` con gli argomenti dati."""
    return AIMessage("", tool_calls=[{"name": "ora_corrente", "args": args or {}, "id": id}])


@tool
def strumento_di_prova() -> str:
    """Strumento inutile, serve solo ai test."""
    return "ok"


def test_turno_senza_strumenti_chiama_il_modello_una_volta():
    finto = ModelloFinto([AIMessage("Ciao!")])
    nuova = esegui_turno(costruisci_grafo(finto, []), [], "ciao")
    assert [m.type for m in nuova] == ["human", "ai"] and nuova[-1].content == "Ciao!"
    assert len(finto.chiamate) == 1
    assert finto.chiamate[0][0].type == "system" and finto.chiamate[0][0].content == PROMPT_DI_SISTEMA


def test_due_turni_conservano_la_cronologia_senza_duplicati():
    finto = ModelloFinto([AIMessage("R1"), AIMessage("R2")])
    grafo = costruisci_grafo(finto, [])
    cronologia = esegui_turno(grafo, esegui_turno(grafo, [], "D1"), "D2")
    assert [(m.type, m.content) for m in cronologia] == [
        ("human", "D1"), ("ai", "R1"), ("human", "D2"), ("ai", "R2")]
    assert [m.type for m in finto.chiamate[1]] == ["system", "human", "ai", "human"]


def test_il_prompt_di_sistema_non_entra_nella_cronologia():
    nuova = esegui_turno(costruisci_grafo(ModelloFinto([AIMessage("Ciao!")]), []), [], "ciao")
    assert "system" not in [m.type for m in nuova]


def test_errore_del_modello_lascia_la_cronologia_invariata():
    grafo = costruisci_grafo(ModelloFinto([AIMessage("R1"), RuntimeError("giù")]), [])
    cronologia = esegui_turno(grafo, [], "D1")
    copia = list(cronologia)
    with pytest.raises(RuntimeError):
        esegui_turno(grafo, cronologia, "D2")
    assert cronologia == copia


@pytest.mark.parametrize("risposta", [AIMessage(""), AIMessage("   "),
    AIMessage("", invalid_tool_calls=[{"name": "ora_corrente", "args": "{", "id": "x", "error": "json"}])])
def test_risposta_non_valida(risposta):
    with pytest.raises(RispostaNonValida):
        esegui_turno(costruisci_grafo(ModelloFinto([risposta]), []), [], "ciao")


def test_risposta_non_valida_registra_un_avviso(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    with pytest.raises(RispostaNonValida):
        esegui_turno(costruisci_grafo(ModelloFinto([AIMessage("  ")]), []), [], "ciao")
    assert [r.levelname for r in caplog.records if r.name.startswith("assistente")][-1] == "WARNING"


def test_risposta_con_richiesta_di_strumento_e_testo_vuoto_e_valida():
    finto = ModelloFinto([chiamata("1"), AIMessage("Sono le 16:42.")])
    nuova = esegui_turno(costruisci_grafo(finto, [orologio]), [], "che ore sono?")
    assert nuova[1].tool_calls[0]["name"] == "ora_corrente" and nuova[-1].content == "Sono le 16:42."


def test_senza_strumenti_il_modello_non_viene_associato():
    finto = ModelloFinto([])
    costruisci_grafo(finto, [])
    assert finto.strumenti_associati == []


def test_con_strumenti_il_modello_viene_associato_una_volta():
    finto = ModelloFinto([AIMessage("R1"), AIMessage("R2")])
    grafo = costruisci_grafo(finto, [strumento_di_prova])
    esegui_turno(grafo, esegui_turno(grafo, [], "D1"), "D2")
    assert finto.strumenti_associati == [[strumento_di_prova]]


def test_il_nodo_llm_registra_chiamata_e_risposta(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    esegui_turno(costruisci_grafo(ModelloFinto([AIMessage("Ciao!")]), []), [], "ciao")
    messaggi = [r.getMessage() for r in caplog.records if r.name.startswith("assistente")]
    assert messaggi[0] == "nodo_llm: chiamata al modello (2 messaggi)"
    assert messaggi[1].startswith("nodo_llm: risposta ricevuta in ") and messaggi[1].endswith(" s")


def test_il_turno_e_invocato_con_il_limite_di_passaggi():
    class GrafoSpia:
        def invoke(self, stato, config):
            self.config = config
            return {"messages": stato["messages"]}

    spia = GrafoSpia()
    esegui_turno(spia, [], "ciao")
    assert LIMITE_PASSAGGI == 21 and spia.config == {"recursion_limit": LIMITE_PASSAGGI}


def test_percorso_con_strumento(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    finto = ModelloFinto([chiamata("c1"), AIMessage("Sono le 16:42.")])
    nuova = esegui_turno(costruisci_grafo(finto, [orologio]), [], "Che ore sono?")
    assert [m.type for m in nuova] == ["human", "ai", "tool", "ai"]
    assert nuova[2].tool_call_id == "c1"
    assert nuova[2].content == "lunedì 2026-10-26T16:42:10+01:00 (Europe/Rome)"
    assert [m.type for m in finto.chiamate[1]] == ["system", "human", "ai", "tool"]
    assert "instradamento: richiesta strumento ora_corrente {}" in caplog.messages
    assert "nodo_strumenti: ora_corrente -> lunedì 2026-10-26T16:42:10+01:00 (Europe/Rome)" in caplog.messages


def test_richiesta_con_fuso_arriva_allo_strumento(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    finto = ModelloFinto([chiamata("c1", {"fuso": "America/New_York"}), AIMessage("ok")])
    nuova = esegui_turno(costruisci_grafo(finto, [orologio]), [], "Che ore sono a New York?")
    assert nuova[2].content == "lunedì 2026-10-26T11:42:10-04:00 (America/New_York)"
    assert 'instradamento: richiesta strumento ora_corrente {"fuso": "America/New_York"}' in caplog.messages
    assert [r for r in caplog.records if r.levelname == "WARNING"] == []


def test_argomenti_inattesi_ignorati(caplog):
    finto = ModelloFinto([chiamata("c1", {"timezone": "Asia/Tokyo"}), AIMessage("ok")])
    nuova = esegui_turno(costruisci_grafo(finto, [orologio]), [], "Ora a Tokyo?")
    assert nuova[2].content.endswith("(Europe/Rome)")
    assert any("argomenti ignorati" in r.message and r.levelname == "WARNING" for r in caplog.records)


def test_piu_richieste_nella_stessa_risposta():
    doppia = AIMessage("", tool_calls=[{"name": "ora_corrente", "args": {}, "id": "a"},
                                       {"name": "ora_corrente", "args": {}, "id": "b"}])
    nuova = esegui_turno(costruisci_grafo(ModelloFinto([doppia, AIMessage("ok")]), [orologio]), [], "?")
    assert [m.tool_call_id for m in nuova if m.type == "tool"] == ["a", "b"]


def test_strumento_sconosciuto(caplog):
    sconosciuta = AIMessage("", tool_calls=[{"name": "meteo", "args": {}, "id": "m"}])
    nuova = esegui_turno(costruisci_grafo(ModelloFinto([sconosciuta, AIMessage("ok")]), [orologio]), [], "?")
    assert nuova[2].content == "Errore: strumento sconosciuto meteo"
    assert nuova[2].tool_call_id == "m" and nuova[2].name == "meteo"
    assert any("meteo" in r.message and r.levelname == "WARNING" for r in caplog.records)


def test_limite_di_passaggi():
    finto = ModelloFinto([chiamata(f"c{i}") for i in range(20)])
    with pytest.raises(GraphRecursionError):
        esegui_turno(costruisci_grafo(finto, [orologio]), [], "?")


def test_limite_di_passaggi_in_chat():
    finto = ModelloFinto([chiamata(f"c{i}") for i in range(20)] + [AIMessage("Eccomi")])
    uscita = chat(costruisci_grafo(finto, [orologio]), ["D1", "/esci"])
    assert f"Errore: limite di {LIMITE_PASSAGGI} passaggi raggiunto. Turno annullato." in uscita


def test_risposta_con_testo_e_richiesta_va_agli_strumenti():
    mista = AIMessage("Controllo l'orologio.", tool_calls=[{"name": "ora_corrente", "args": {}, "id": "x"}])
    nuova = esegui_turno(costruisci_grafo(ModelloFinto([mista, AIMessage("ok")]), [orologio]), [], "?")
    assert nuova[2].type == "tool"


def solleva_tool_exception(espressione: str) -> str:
    raise ToolException("divisione per zero")


calcola_finta = StructuredTool.from_function(func=solleva_tool_exception, name="calcola", description="prova")


def richiesta_calcolo(id, espressione="1/0"):
    return AIMessage("", tool_calls=[{"name": "calcola", "args": {"espressione": espressione}, "id": id}])


def test_errore_dello_strumento_diventa_tool_message_d_errore(caplog):
    finto = ModelloFinto([richiesta_calcolo("k1"), AIMessage("Non si può dividere per zero.")])
    nuova = esegui_turno(costruisci_grafo(finto, [calcola_finta]), [], "Quanto fa 1/0?")
    assert [m.type for m in nuova] == ["human", "ai", "tool", "ai"]
    assert (nuova[2].content, nuova[2].status, nuova[2].tool_call_id, nuova[2].name) == \
        ("Errore: divisione per zero", "error", "k1", "calcola")
    assert len(finto.chiamate) == 2 and finto.chiamate[1][-1].type == "tool"
    assert "nodo_strumenti: errore dello strumento calcola: divisione per zero" in \
        [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]


def test_le_altre_eccezioni_dello_strumento_annullano_il_turno():
    def rotto(espressione: str) -> str:
        raise RuntimeError("difetto")
    strumento = StructuredTool.from_function(func=rotto, name="calcola", description="prova")
    with pytest.raises(RuntimeError):
        esegui_turno(costruisci_grafo(ModelloFinto([richiesta_calcolo("k1")]), [strumento]), [], "?")


def test_un_errore_non_blocca_le_altre_richieste():
    doppia = AIMessage("", tool_calls=[{"name": "calcola", "args": {"espressione": "1/0"}, "id": "a"},
                                       {"name": "ora_corrente", "args": {}, "id": "b"}])
    finto = ModelloFinto([doppia, AIMessage("ok")])
    nuova = esegui_turno(costruisci_grafo(finto, [calcola_finta, orologio]), [], "?")
    risposte = [m for m in nuova if m.type == "tool"]
    assert [(m.tool_call_id, m.status) for m in risposte] == [("a", "error"), ("b", "success")]
    assert risposte[1].content == "lunedì 2026-10-26T16:42:10+01:00 (Europe/Rome)"


def test_il_prompt_chiede_la_calcolatrice_e_conserva_l_orologio():
    assert "chiama lo strumento calcola" in PROMPT_DI_SISTEMA
    assert "senza inventare un risultato" in PROMPT_DI_SISTEMA
    assert "chiama sempre lo strumento ora_corrente" in PROMPT_DI_SISTEMA


def test_il_prompt_chiede_il_convertitore():
    assert "chiama lo strumento converti" in PROMPT_DI_SISTEMA
    assert "chiama lo strumento calcola" in PROMPT_DI_SISTEMA
    assert "chiama sempre lo strumento ora_corrente" in PROMPT_DI_SISTEMA
    assert "senza inventare un risultato" in PROMPT_DI_SISTEMA


def richiesta_conversione(id, args):
    return AIMessage("", tool_calls=[{"name": "converti", "args": args, "id": id}])


def test_percorso_con_il_convertitore(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    finto = ModelloFinto([
        richiesta_conversione("v1", {"valore": 25, "da": "m", "a": "km"}),
        AIMessage("25 metri sono 0,025 km."),
    ])
    nuova = esegui_turno(costruisci_grafo(finto, [crea_strumento_convertitore()]), [], "Quanti km sono 25 metri?")
    assert [m.type for m in nuova] == ["human", "ai", "tool", "ai"]
    assert nuova[2].tool_call_id == "v1"
    assert nuova[2].content == "25 m = 0,025 km" and nuova[2].status == "success"
    assert "nodo_strumenti: converti -> 25 m = 0,025 km" in caplog.messages


@pytest.mark.parametrize("args, atteso", [
    ({"valore": 5, "da": "kg", "a": "m"}, "peso"),
    ({"valore": "tanti", "da": "m", "a": "km"}, "numero"),
])
def test_conversione_impossibile_diventa_errore(args, atteso):
    finto = ModelloFinto([richiesta_conversione("v2", args), AIMessage("Non si può.")])
    nuova = esegui_turno(costruisci_grafo(finto, [crea_strumento_convertitore()]), [], "converti")
    assert nuova[2].tool_call_id == "v2" and nuova[2].status == "error"
    assert nuova[2].content.startswith("Errore: ") and atteso in nuova[2].content


def test_il_prompt_chiede_gli_strumenti_del_calendario():
    for testo in ["giorni_tra", "sposta_data", "giorno_settimana", "pasqua", "AAAA-MM-GG"]:
        assert testo in PROMPT_DI_SISTEMA
    assert "chiama lo strumento converti" in PROMPT_DI_SISTEMA
    assert "chiama lo strumento calcola" in PROMPT_DI_SISTEMA
    assert "chiama sempre lo strumento ora_corrente" in PROMPT_DI_SISTEMA


def strumenti_del_calendario():
    return crea_strumenti_calendario(ZoneInfo("Europe/Rome"), adesso=lambda: datetime(2026, 11, 3, 10, 0, tzinfo=UTC))


def richiesta_calendario(id, nome, args):
    return AIMessage("", tool_calls=[{"name": nome, "args": args, "id": id}])


def test_percorso_con_il_calendario(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    finto = ModelloFinto([
        richiesta_calendario("d1", "giorni_tra", {"data": "12-25"}),
        AIMessage("Mancano 52 giorni."),
    ])
    nuova = esegui_turno(costruisci_grafo(finto, strumenti_del_calendario()), [], "Quanti giorni a Natale?")
    assert [m.type for m in nuova] == ["human", "ai", "tool", "ai"]
    assert nuova[2].tool_call_id == "d1" and nuova[2].status == "success"
    assert nuova[2].content.endswith("mancano 52 giorni")
    assert any(m.startswith("nodo_strumenti: giorni_tra -> ") for m in caplog.messages)


@pytest.mark.parametrize("nome, args, atteso", [
    ("pasqua", {"anno": 1500}, "1583"),
    ("giorni_tra", {"data": "2026-02-30"}, "non valida"),
    ("sposta_data", {"giorni": 2.5}, "giorni"),
])
def test_errori_del_calendario_diventano_tool_message_d_errore(nome, args, atteso):
    finto = ModelloFinto([richiesta_calendario("d2", nome, args), AIMessage("Non si può.")])
    nuova = esegui_turno(costruisci_grafo(finto, strumenti_del_calendario()), [], "?")
    assert nuova[2].tool_call_id == "d2" and nuova[2].status == "error"
    assert nuova[2].content.startswith("Errore: ") and atteso in nuova[2].content


def test_il_prompt_chiede_gli_strumenti_delle_note():
    for testo in ["salva_nota", "elenca_note", "cancella_nota", "giorni_tra"]:
        assert testo in PROMPT_DI_SISTEMA
    assert "chiama lo strumento converti" in PROMPT_DI_SISTEMA
    assert "chiama lo strumento calcola" in PROMPT_DI_SISTEMA
    assert "chiama sempre lo strumento ora_corrente" in PROMPT_DI_SISTEMA


def richiesta_nota(id):
    return AIMessage("", tool_calls=[{"name": "salva_nota", "args": {"testo": "calibrare il microscopio 2"}, "id": id}])


def test_percorso_con_le_note(servizio_note, caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    finto = ModelloFinto([richiesta_nota("n1"), AIMessage("Fatto.")])
    strumenti = crea_strumenti_note(servizio_note, ZoneInfo("Europe/Rome"))
    nuova = esegui_turno(costruisci_grafo(finto, strumenti), [], "Segnati il microscopio")
    assert nuova[2].tool_call_id == "n1" and nuova[2].status == "success" and "salvata" in nuova[2].content
    assert any(m.startswith("nodo_strumenti: salva_nota -> ") for m in caplog.messages)


def test_servizio_note_spento_diventa_errore():
    finto = ModelloFinto([richiesta_nota("n2"), AIMessage("Non posso.")])
    strumenti = crea_strumenti_note(f"http://127.0.0.1:{porta_libera()}", ZoneInfo("Europe/Rome"))
    nuova = esegui_turno(costruisci_grafo(finto, strumenti), [], "Segnati il microscopio")
    assert nuova[2].status == "error" and "non raggiungibile" in nuova[2].content


def test_il_prompt_chiede_il_catalogo():
    for testo in ["cerca_apparecchi", "dettaglio_apparecchio", "elenca_apparecchi", "giorni_tra", "salva_nota"]:
        assert testo in PROMPT_DI_SISTEMA
    assert "chiama lo strumento converti" in PROMPT_DI_SISTEMA
    assert "chiama lo strumento calcola" in PROMPT_DI_SISTEMA
    assert "chiama sempre lo strumento ora_corrente" in PROMPT_DI_SISTEMA


AMBITO = "Ambito di prova: scienze e laboratorio."


def test_in_ambito_passa_all_agente(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    finto = ModelloFinto([AIMessage("Ciao!")], decisioni=[decisione("conversazione", "saluto")])
    nuova = esegui_turno(costruisci_grafo(finto, [], AMBITO), [], "ciao")
    assert [m.type for m in nuova] == ["human", "ai"] and nuova[-1].text == "Ciao!"
    assert any(m.startswith("router: conversazione (saluto) in ") for m in caplog.messages)
    assert len(finto.chiamate) == 1
    assert finto.opzioni_router == [{"method": "json_schema", "include_raw": True}]


def test_fuori_ambito_rifiuta_senza_agente(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    finto = ModelloFinto([], decisioni=[decisione("fuori_ambito", "richiesta di una poesia")])
    nuova = esegui_turno(costruisci_grafo(finto, [crea_strumento_convertitore()], AMBITO), [], "una poesia")
    assert [m.type for m in nuova] == ["human", "ai"]
    assert nuova[-1].text == "Posso aiutarti solo con domande scientifiche o sul laboratorio: richiesta di una poesia."
    assert finto.chiamate == []
    assert any(m.startswith("router: fuori ambito (richiesta di una poesia) in ") for m in caplog.messages)
    assert "nodo_rifiuto: domanda fuori ambito" in caplog.messages
    assert not any(m.startswith(("nodo_llm", "nodo_strumenti")) for m in caplog.messages)


def test_decisione_illeggibile_passa_all_agente():
    illeggibile = {"raw": None, "parsed": None, "parsing_error": ValueError("JSON rotto")}
    finto = ModelloFinto([AIMessage("Risposta")], decisioni=[illeggibile])
    nuova = esegui_turno(costruisci_grafo(finto, [], AMBITO), [], "?")
    assert nuova[-1].text == "Risposta"


def test_eccezione_del_router_passa_all_agente(caplog):
    finto = ModelloFinto([AIMessage("Risposta")], decisioni=[RuntimeError("limite di lunghezza")])
    nuova = esegui_turno(costruisci_grafo(finto, [], AMBITO), [], "?")
    assert nuova[-1].text == "Risposta"
    assert any(r.levelno == logging.WARNING and "router: errore (RuntimeError), la domanda passa" in r.getMessage()
               for r in caplog.records)


def test_turno_dopo_un_rifiuto():
    finto = ModelloFinto([AIMessage("Il pH misura l'acidità.")], decisioni=[
        decisione("fuori_ambito", "sport"), decisione("conversazione", "chimica")])
    grafo = costruisci_grafo(finto, [], AMBITO)
    cronologia = esegui_turno(grafo, [], "chi vince il campionato?")
    cronologia = esegui_turno(grafo, cronologia, "cos'è il pH?")
    assert [m.type for m in cronologia] == ["human", "ai", "human", "ai"]
    assert cronologia[-1].text == "Il pH misura l'acidità."


def test_il_router_riceve_l_ambito_e_non_i_messaggi_degli_strumenti():
    finto = ModelloFinto([chiamata("c1"), AIMessage("Sono le 16:42."), AIMessage("Prego!")],
                         decisioni=[decisione("conversazione", "ora"), decisione("conversazione", "grazie")])
    grafo = costruisci_grafo(finto, [orologio], AMBITO)
    cronologia = esegui_turno(grafo, [], "Che ore sono?")
    esegui_turno(grafo, cronologia, "grazie")
    secondo = finto.chiamate_router[1]
    assert secondo[0].type == "system" and AMBITO in secondo[0].text
    assert [m.type for m in secondo[1:]] == ["human", "ai", "human"]


def test_senza_ambito_nessun_router():
    finto = ModelloFinto([AIMessage("Ciao!")])
    esegui_turno(costruisci_grafo(finto, []), [], "ciao")
    assert finto.chiamate_router == [] and finto.opzioni_router == []


def test_quattro_giri_di_strumenti_con_il_router():
    finto = ModelloFinto([chiamata(f"c{i}") for i in range(4)] + [AIMessage("Fatto")],
                         decisioni=[decisione("conversazione", "ora")])
    nuova = esegui_turno(costruisci_grafo(finto, [orologio], AMBITO), [], "?")
    assert nuova[-1].text == "Fatto"


def test_modello_router_separato():
    agente = ModelloFinto([AIMessage("Ciao!")])
    router = ModelloFinto([], decisioni=[decisione("conversazione", "saluto")])
    esegui_turno(costruisci_grafo(agente, [], AMBITO, router), [], "ciao")
    assert len(router.chiamate_router) == 1 and agente.chiamate_router == []


REVISORE = "Istruzioni del revisore di prova."
DOMANDA = "Quanti giorni mancano a Natale e che giorno della settimana sarà?"


def test_revisore_approva_subito(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    finto = ModelloFinto([AIMessage("Mancano 46 giorni, venerdì.")], valutazioni=[valutazione(True, "completa")])
    nuova = esegui_turno(costruisci_grafo(finto, [], revisore=REVISORE), [], DOMANDA)
    assert [m.type for m in nuova] == ["human", "ai"] and len(finto.chiamate) == 1
    assert len(finto.chiamate_revisore) == 1 and finto.chiamate_revisore[0][0].text == REVISORE
    assert any(m.startswith("revisore: coerente (completa) in ") for m in caplog.messages)


def test_revisore_rifiuta_una_volta(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    finto = ModelloFinto([AIMessage("Mancano 46 giorni."), AIMessage("Mancano 46 giorni; sarà venerdì.")],
                         valutazioni=[valutazione(False, "manca il giorno della settimana"), valutazione(True, "ok")])
    nuova = esegui_turno(costruisci_grafo(finto, [], revisore=REVISORE), [], DOMANDA)
    assert [m.type for m in nuova] == ["human", "ai"] and nuova[-1].text == "Mancano 46 giorni; sarà venerdì."
    secondo = finto.chiamate[1]
    assert "manca il giorno della settimana" in secondo[-1].text and DOMANDA in secondo[-1].text
    assert any("revisione 1 di 2" in m for m in caplog.messages)
    assert "nodo_pulizia: rimossi 2 messaggi di revisione" in caplog.messages


def test_revisore_rifiuta_sempre(caplog):
    finto = ModelloFinto([AIMessage(f"Bozza {i}") for i in range(3)],
                         valutazioni=[valutazione(False, "incompleta")] * 3)
    nuova = esegui_turno(costruisci_grafo(finto, [], revisore=REVISORE), [], DOMANDA)
    assert len(finto.chiamate) == 3 and len(finto.chiamate_revisore) == 3
    assert [m.type for m in nuova] == ["human", "ai"] and nuova[-1].text == "Bozza 2"
    assert any(r.levelno == logging.WARNING and "limite di revisioni raggiunto" in r.getMessage() for r in caplog.records)


def test_revisioni_max_zero():
    finto = ModelloFinto([AIMessage("Bozza")], valutazioni=[valutazione(False, "incompleta")])
    nuova = esegui_turno(costruisci_grafo(finto, [], revisore=REVISORE, revisioni_max=0), [], DOMANDA)
    assert nuova[-1].text == "Bozza" and len(finto.chiamate) == 1 and len(finto.chiamate_revisore) == 1


@pytest.mark.parametrize("voce, avviso", [
    (RuntimeError("limite di lunghezza"), "revisore: errore (RuntimeError), la risposta è approvata"),
    ({"raw": None, "parsed": None, "parsing_error": ValueError("x")}, "revisore: valutazione illeggibile, la risposta è approvata"),
])
def test_errore_e_valutazione_illeggibile_approvano(caplog, voce, avviso):
    finto = ModelloFinto([AIMessage("Risposta")], valutazioni=[voce])
    nuova = esegui_turno(costruisci_grafo(finto, [], revisore=REVISORE), [], DOMANDA)
    assert nuova[-1].text == "Risposta" and len(finto.chiamate) == 1
    assert avviso in [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


def test_revisione_dopo_gli_strumenti():
    finto = ModelloFinto([chiamata("c1"), AIMessage("Sono le 16:42."), AIMessage("Sono le 16:42 di lunedì.")],
                         valutazioni=[valutazione(False, "manca il giorno"), valutazione(True, "ok")])
    nuova = esegui_turno(costruisci_grafo(finto, [orologio], revisore=REVISORE), [], "Che ore sono e che giorno è?")
    assert [m.type for m in nuova] == ["human", "ai", "tool", "ai"]
    assert nuova[1].tool_calls and nuova[2].tool_call_id == "c1" and nuova[-1].text == "Sono le 16:42 di lunedì."


def test_due_turni_con_revisione():
    finto = ModelloFinto([AIMessage("R1 bozza"), AIMessage("R1"), AIMessage("R2")],
                         valutazioni=[valutazione(False, "incompleta"), valutazione(True, "ok"), valutazione(True, "ok")])
    grafo = costruisci_grafo(finto, [], revisore=REVISORE)
    cronologia = esegui_turno(grafo, [], "D1")
    cronologia = esegui_turno(grafo, cronologia, "D2")
    assert [m.text for m in cronologia] == ["D1", "R1", "D2", "R2"]
    assert "D2" in finto.chiamate_revisore[-1][1].text
    assert [m.text for m in finto.chiamate[-1]][1:] == ["D1", "R1", "D2"]


def test_rifiuto_del_router_senza_revisore():
    finto = ModelloFinto([], decisioni=[decisione("fuori_ambito", "poesia")])
    esegui_turno(costruisci_grafo(finto, [], AMBITO, revisore=REVISORE), [], "una poesia")
    assert finto.chiamate_revisore == [] and finto.chiamate == []


def test_senza_revisore_nessuna_revisione():
    finto = ModelloFinto([AIMessage("Ciao!")])
    esegui_turno(costruisci_grafo(finto, []), [], "ciao")
    assert finto.chiamate_revisore == []


RIASSUMI = "RIASSUMI"


def turni_precedenti(n):
    """`n` turni semplici già conclusi: D1, R1, D2, R2, ..."""
    return [m for i in range(1, n + 1) for m in (HumanMessage(f"D{i}"), AIMessage(f"R{i}"))]


def grafo_con_riassunto(agente, riassunto, strumenti=(), soglia=20, turni=2, **altri):
    return costruisci_grafo(agente, list(strumenti), modello_router=riassunto, riassunto_istruzioni=RIASSUMI,
                            riassunto_soglia=soglia, riassunto_turni=turni, **altri)


def test_riassunto_sotto_la_soglia_non_chiama_il_modello(caplog):
    caplog.set_level(logging.DEBUG, logger="assistente")
    riassunto = ModelloFinto([])
    vecchia = turni_precedenti(3)
    nuova, testo = esegui_turno_con_riassunto(
        grafo_con_riassunto(ModelloFinto([AIMessage("R4")]), riassunto), vecchia, "", "D4")
    assert riassunto.chiamate == [] and testo == ""
    assert [m.text for m in nuova] == ["D1", "R1", "D2", "R2", "D3", "R3", "D4", "R4"]
    assert "riassunto: 7 messaggi, sotto la soglia di 20" in caplog.messages


def test_riassunto_sopra_la_soglia(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    riassunto = ModelloFinto([AIMessage("  L'utente ha fatto tre domande.  ")])
    agente = ModelloFinto([AIMessage("R5")])
    nuova, testo = esegui_turno_con_riassunto(
        grafo_con_riassunto(agente, riassunto, soglia=6, turni=1), turni_precedenti(4), "", "D5")
    assert len(riassunto.chiamate) == 1
    sistema, richiesta = riassunto.chiamate[0]
    assert sistema.text == RIASSUMI
    assert "Utente: D3" in richiesta.text and "Assistente: R3" in richiesta.text and "D4" not in richiesta.text
    assert [m.text for m in nuova] == ["D4", "R4", "D5", "R5"]
    assert testo == "L'utente ha fatto tre domande."
    assert any(m.startswith("riassunto: 9 messaggi -> 3 in ") for m in caplog.messages)
    # Il riassunto arriva all'agente in un secondo messaggio di sistema, dopo il prompt invariato: con tutti gli
    # strumenti gemma lo ignorava dentro il prompt (prova del 17/11/2026).
    sistema_agente, riassunto_agente = agente.chiamate[0][:2]
    assert sistema_agente.text == PROMPT_DI_SISTEMA
    assert riassunto_agente.type == "system" and riassunto_agente.text.endswith("L'utente ha fatto tre domande.")


def test_riassunto_sostituisce_il_precedente():                               # Review Focus 2
    riassunto = ModelloFinto([AIMessage("Si chiama Ottavio; ha chiesto l'ora.")])
    _, testo = esegui_turno_con_riassunto(
        grafo_con_riassunto(ModelloFinto([AIMessage("R5")]), riassunto, soglia=6, turni=1),
        turni_precedenti(4), "Si chiama Ottavio.", "D5")
    assert "Si chiama Ottavio." in riassunto.chiamate[0][1].text
    assert testo == "Si chiama Ottavio; ha chiesto l'ora."


def turno_con_strumento(n):
    return [
        HumanMessage(f"D{n}"),
        AIMessage("", tool_calls=[{"name": "ora_corrente", "args": {}, "id": f"t{n}"}]),
        ToolMessage("16:42", tool_call_id=f"t{n}", name="ora_corrente"),
        AIMessage(f"R{n}"),
    ]


def test_riassunto_con_strumenti_non_lascia_orfani():                          # Review Focus 4
    vecchia = [*turno_con_strumento(1), *turno_con_strumento(2), *turno_con_strumento(3)]
    agente = ModelloFinto([chiamata("t4"), AIMessage("R4")])
    nuova, _ = esegui_turno_con_riassunto(
        grafo_con_riassunto(agente, ModelloFinto([AIMessage("Riassunto")]), [orologio], soglia=6, turni=1),
        vecchia, "", "D4")
    assert [m.text for m in nuova if m.type == "human"] == ["D3", "D4"]
    richieste = {c["id"] for m in nuova if m.type == "ai" for c in m.tool_calls}
    risposte = {m.tool_call_id for m in nuova if m.type == "tool"}
    assert richieste == risposte == {"t3", "t4"}


def test_riassunto_sopra_la_soglia_senza_turni_da_tagliare(caplog):
    caplog.set_level(logging.DEBUG, logger="assistente")
    riassunto = ModelloFinto([])
    esegui_turno_con_riassunto(
        grafo_con_riassunto(ModelloFinto([AIMessage("R2")]), riassunto, soglia=2, turni=2),
        turno_con_strumento(1), "", "D2")
    assert riassunto.chiamate == []
    assert "riassunto: 5 messaggi, nessun turno da riassumere" in caplog.messages


@pytest.mark.parametrize("voce, avviso", [
    (RuntimeError("giù"), "riassunto: errore (RuntimeError), cronologia invariata"),
    (AIMessage("  "), "riassunto: risposta vuota, cronologia invariata"),
])
def test_riassunto_errore_o_vuoto_lascia_tutto_invariato(caplog, voce, avviso):
    nuova, testo = esegui_turno_con_riassunto(
        grafo_con_riassunto(ModelloFinto([AIMessage("R5")]), ModelloFinto([voce]), soglia=6, turni=1),
        turni_precedenti(4), "Precedente.", "D5")
    assert len(nuova) == 10 and nuova[-1].text == "R5" and testo == "Precedente."
    assert avviso in [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


def test_agente_e_router_ricevono_il_riassunto_il_revisore_no():
    ausiliario = ModelloFinto([], decisioni=[decisione("conversazione", "nome")],
                              valutazioni=[valutazione(True, "ok")])
    agente = ModelloFinto([AIMessage("Ti chiami Ottavio.")])
    esegui_turno_con_riassunto(
        grafo_con_riassunto(agente, ausiliario, ambito=AMBITO, revisore=REVISORE),
        [], "Si chiama Ottavio.", "Come mi chiamo?")
    assert agente.chiamate[0][0].text == PROMPT_DI_SISTEMA and "Ottavio" in agente.chiamate[0][1].text
    assert AMBITO in ausiliario.chiamate_router[0][0].text and "Ottavio" in ausiliario.chiamate_router[0][0].text
    assert not any("Si chiama Ottavio." in m.text for m in ausiliario.chiamate_revisore[0])


def test_turno_rifiutato_viene_riassunto():                                    # Review Focus 3
    ausiliario = ModelloFinto([AIMessage("Ha chiesto una poesia, rifiutata.")],
                              decisioni=[decisione("fuori_ambito", "poesia"), decisione("conversazione", "ok"),
                                         decisione("conversazione", "ok")])
    agente = ModelloFinto([AIMessage("R2"), AIMessage("R3")])
    grafo = grafo_con_riassunto(agente, ausiliario, soglia=4, turni=1, ambito=AMBITO)
    cronologia, testo = esegui_turno_con_riassunto(grafo, [], "", "una poesia")
    cronologia, testo = esegui_turno_con_riassunto(grafo, cronologia, testo, "D2")
    cronologia, testo = esegui_turno_con_riassunto(grafo, cronologia, testo, "D3")
    assert "Utente: una poesia" in ausiliario.chiamate[0][1].text
    assert [m.text for m in cronologia] == ["D2", "R2", "D3", "R3"]
    assert testo == "Ha chiesto una poesia, rifiutata."


def test_senza_istruzioni_nessun_nodo_riassunto():
    assert "nodo_riassunto" not in costruisci_grafo(ModelloFinto([]), []).get_graph().nodes
    assert "nodo_riassunto" in grafo_con_riassunto(ModelloFinto([]), ModelloFinto([])).get_graph().nodes


def test_esegui_turno_resta_compatibile():
    nuova = esegui_turno(grafo_con_riassunto(ModelloFinto([AIMessage("R1")]), ModelloFinto([])), [], "D1")
    assert [m.text for m in nuova] == ["D1", "R1"]


def test_modello_riassunto_separato_dal_router():
    router = ModelloFinto([], decisioni=[decisione("conversazione", "ok")])
    riassunto = ModelloFinto([AIMessage("Riassunto")])
    _, testo = esegui_turno_con_riassunto(
        costruisci_grafo(ModelloFinto([AIMessage("R5")]), [], AMBITO, router, riassunto_istruzioni=RIASSUMI,
                         riassunto_soglia=6, riassunto_turni=1, modello_riassunto=riassunto),
        turni_precedenti(4), "", "D5")
    assert testo == "Riassunto" and len(riassunto.chiamate) == 1 and router.chiamate == []


def test_senza_riassunto_un_solo_messaggio_di_sistema_all_agente():
    agente = ModelloFinto([AIMessage("R1")])
    esegui_turno_con_riassunto(grafo_con_riassunto(agente, ModelloFinto([])), [], "", "D1")
    assert [m.type for m in agente.chiamate[0]] == ["system", "human"]
