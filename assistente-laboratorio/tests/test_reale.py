"""Prove con LM Studio attivo: `python -m pytest -m reale -v` (escluse di default)."""

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from assistente.calendario import crea_strumenti_calendario, leggi_data
from assistente.client_mcp import carica_strumenti_mcp, leggi_preferenze_mcp
from assistente.config import carica_configurazione, leggi_ambito, leggi_file_env, leggi_revisore, leggi_riassunto
from assistente.convertitore import crea_strumento_convertitore
from assistente.grafo import costruisci_grafo, esegui_turno, esegui_turno_con_riassunto
from assistente.modello import crea_modello, crea_modello_riassunto, crea_modello_router, leggi_modelli_disponibili, verifica_modello
from assistente.riassunto import messaggi_per_il_riassunto
from assistente.revisore import SCHEMA_REVISORE, e_indicazione, leggi_valutazione, messaggi_per_il_revisore
from assistente.router import INIZIO_RIFIUTO
from assistente.note import crea_strumenti_note
from assistente.preferenze import Preferenze, blocco_preferenze, carica_preferenze
from assistente.strumenti import crea_strumento_orologio

pytestmark = pytest.mark.reale

RADICE = Path(__file__).resolve().parent.parent
FILE_ENV = RADICE / ".env"


@pytest.fixture(scope="module")
def config():
    """Configurazione di `.env` e dell'ambiente, come in `main`."""
    return carica_configurazione({**leggi_file_env(FILE_ENV), **os.environ})


def preferenze_del_file(config):
    """Il blocco delle preferenze come in `main`: file versionato letto dal server MCP vero."""
    return blocco_preferenze(carica_preferenze(leggi_preferenze_mcp, config.fuso))


def crea_grafo(config, servizio_note, soglia, turni, preferenze=None):
    """Grafo collegato al modello reale, con gli stessi strumenti e nodi di `main`, il riassunto dato e le
    preferenze date (predefinite: quelle del file, come in `main`)."""
    verifica_modello(config.modello, leggi_modelli_disponibili(config.base_url))
    strumenti = [
        crea_strumento_orologio(config.fuso),
        *crea_strumenti_calendario(config.fuso),
        crea_strumento_convertitore(),
        *crea_strumenti_note(servizio_note, config.fuso),
        *carica_strumenti_mcp(),
    ]
    ambito = leggi_ambito(RADICE / "ambito.txt")
    revisore = leggi_revisore(RADICE / "revisore.txt")
    return costruisci_grafo(
        crea_modello(config), strumenti, ambito, crea_modello_router(config), revisore, config.revisioni_max,
        riassunto_istruzioni=leggi_riassunto(RADICE / "riassunto.txt"),
        riassunto_soglia=soglia,
        riassunto_turni=turni,
        modello_riassunto=crea_modello_riassunto(config),
        preferenze=preferenze if preferenze is not None else preferenze_del_file(config),
    )


@pytest.fixture(scope="module")
def grafo(config, servizio_note):
    """Grafo come quello di `main` (le prove brevi restano sotto la soglia del riassunto)."""
    return crea_grafo(config, servizio_note, config.riassunto_soglia, config.riassunto_turni)


def test_reale_risposta_ordinaria(grafo):
    cronologia = esegui_turno(grafo, [], "Spiegami in una frase cos'è un grafo.")
    assert cronologia[-1].type == "ai" and cronologia[-1].text.strip()
    assert "tool" not in [m.type for m in cronologia]
    assert "tool_call" not in cronologia[-1].text.lower()


def test_reale_cronologia(grafo):
    cronologia = esegui_turno(grafo, [], "Il mio colore preferito è il verde.")
    cronologia = esegui_turno(grafo, cronologia, "Qual è il mio colore preferito?")
    assert "verde" in cronologia[-1].text.lower()


def nomi_strumenti(cronologia):
    """Nomi degli strumenti eseguiti nella cronologia, nell'ordine."""
    return [m.name for m in cronologia if m.type == "tool"]


def test_reale_due_domande_sull_ora(grafo):
    # Il modello può chiamare l'orologio più di una volta nello stesso turno: ne serve almeno una per turno.
    primo = esegui_turno(grafo, [], "Che ore sono?")
    dopo_il_primo = nomi_strumenti(primo)
    assert dopo_il_primo and set(dopo_il_primo) == {"ora_corrente"}
    secondo = esegui_turno(grafo, primo, "E adesso che ore sono?")
    dopo_il_secondo = nomi_strumenti(secondo)
    assert set(dopo_il_secondo) == {"ora_corrente"} and len(dopo_il_secondo) > len(dopo_il_primo)


def test_reale_ora_di_un_altra_citta(grafo):
    cronologia = esegui_turno(grafo, [], "Che ore sono a New York?")
    risultati = [m.content for m in cronologia if m.type == "tool" and m.name == "ora_corrente"]
    assert any(r.endswith("(America/New_York)") for r in risultati)


def test_reale_calcolo(grafo):
    cronologia = esegui_turno(grafo, [], "Quanto fa 12,5 per 8 meno 3?")
    risultati = [m.content for m in cronologia if m.type == "tool" and m.name == "calcola"]
    assert "97" in risultati and "97" in cronologia[-1].text


def test_reale_conversione_lunghezza(grafo):
    cronologia = esegui_turno(grafo, [], "Quanti metri sono 4 cm?")
    risultati = [m.content for m in cronologia if m.type == "tool" and m.name == "converti"]
    assert "4 cm = 0,04 m" in risultati and "0,04" in cronologia[-1].text


def test_reale_conversione_temperatura(grafo):
    cronologia = esegui_turno(grafo, [], "Quanti gradi Fahrenheit sono 20 °C?")
    risultati = [m.content for m in cronologia if m.type == "tool" and m.name == "converti"]
    assert "20 °C = 68 °F" in risultati and "68" in cronologia[-1].text


def test_reale_giorni_al_25_dicembre(grafo, config):
    oggi = datetime.now(config.fuso).date()
    n = (leggi_data("12-25", oggi) - oggi).days
    cronologia = esegui_turno(grafo, [], "Quanti giorni mancano al 25 dicembre?")
    risultati = [m.content for m in cronologia if m.type == "tool" and m.name == "giorni_tra"]
    atteso = "è oggi" if n == 0 else f"mancano {n} giorni"
    assert any(r.endswith(atteso) for r in risultati)
    assert n == 0 or str(n) in cronologia[-1].text


def test_reale_pasqua_2027(grafo):
    cronologia = esegui_turno(grafo, [], "Che giorno è Pasqua nel 2027?")
    risultati = [m.content for m in cronologia if m.type == "tool" and m.name == "pasqua"]
    assert "Pasqua 2027: domenica 28 marzo 2027" in risultati
    assert "28 marzo" in cronologia[-1].text


def test_reale_note(grafo):
    salvataggio = esegui_turno(grafo, [], "Segnati che il microscopio 2 va calibrato.")
    salvate = [m for m in salvataggio if m.type == "tool" and m.name == "salva_nota"]
    assert any(m.status == "success" for m in salvate)
    elenco = esegui_turno(grafo, [], "Che note ho?")
    risultati = [m.content for m in elenco if m.type == "tool" and m.name == "elenca_note"]
    assert any("microscopio 2" in r for r in risultati)
    assert "microscopio" in elenco[-1].text.lower()


def test_reale_dove_la_centrifuga(grafo):
    cronologia = esegui_turno(grafo, [], "Dov'è la centrifuga?")
    risultati = [m.content for m in cronologia if m.type == "tool" and m.name == "cerca_apparecchi"]
    assert any("A03" in r for r in risultati)
    assert "A03" in cronologia[-1].text


def test_reale_in_manutenzione(grafo):
    cronologia = esegui_turno(grafo, [], "Quali apparecchi sono in manutenzione?")
    risultati = [m.content for m in cronologia if m.type == "tool" and m.name == "elenca_apparecchi"]
    assert any("MIC-02" in r and "PHM-01" in r for r in risultati)
    risposta = cronologia[-1].text
    assert "MIC-02" in risposta or "Microscopio ottico 2" in risposta
    assert "PHM-01" in risposta or "pHmetro" in risposta


def test_reale_fuori_ambito(grafo, caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    cronologia = esegui_turno(grafo, [], "Scrivimi una poesia sul mare.")
    assert [m.type for m in cronologia] == ["human", "ai"] and cronologia[-1].text.startswith(INIZIO_RIFIUTO)
    assert any(m.startswith("router: fuori ambito") for m in caplog.messages)
    assert not any(m.startswith("nodo_llm:") for m in caplog.messages)


def test_reale_domanda_scientifica(grafo, caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    cronologia = esegui_turno(grafo, [], "Cos'è il pH?")
    assert not cronologia[-1].text.startswith(INIZIO_RIFIUTO) and cronologia[-1].text.strip()
    assert any(m.startswith("nodo_llm:") for m in caplog.messages)


DOMANDA_IN_DUE_PARTI = "Quanti giorni mancano a Natale e che giorno della settimana sarà?"


def test_reale_revisore_rifiuta_risposta_parziale(config):
    revisore = crea_modello_router(config).with_structured_output(
        SCHEMA_REVISORE, method="json_schema", include_raw=True
    )
    messaggi = messaggi_per_il_revisore(
        leggi_revisore(RADICE / "revisore.txt"), DOMANDA_IN_DUE_PARTI, "Mancano 46 giorni a Natale."
    )
    coerente, motivo = leggi_valutazione(revisore.invoke(messaggi))
    assert coerente is False and motivo


def test_reale_domanda_in_due_parti(grafo, config, caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    oggi = datetime.now(config.fuso).date()
    n = (leggi_data("12-25", oggi) - oggi).days
    cronologia = esegui_turno(grafo, [], DOMANDA_IN_DUE_PARTI)
    risposta = cronologia[-1].text
    assert str(n) in risposta and "venerdì" in risposta.lower()
    assert not any(e_indicazione(m) for m in cronologia)
    assert any(m.startswith("revisore: ") for m in caplog.messages)


def test_reale_risposta_approvata(grafo, caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    cronologia = esegui_turno(grafo, [], "Quanto fa 12,5 per 8 meno 3?")
    assert "97" in cronologia[-1].text
    assert any(m.startswith("revisore: coerente") for m in caplog.messages)
    assert not any(m.startswith("revisore: non coerente") for m in caplog.messages)


TRASCRIZIONE_CON_NOME = (
    "Utente: Ciao, mi chiamo Ottavio e lavoro nel laboratorio di chimica.\n"
    "Assistente: Piacere, Ottavio! Come posso aiutarti?\n"
    "Utente: Che ore sono?\n"
    'Assistente chiede lo strumento ora_corrente {"fuso": "Europe/Rome"}\n'
    "Strumento ora_corrente: 2026-11-17T15:42:10+01:00 (Europe/Rome)\n"
    "Assistente: Sono le 15:42."
)


def test_reale_riassunto_conserva_il_nome(config):
    messaggi = messaggi_per_il_riassunto(leggi_riassunto(RADICE / "riassunto.txt"), "", TRASCRIZIONE_CON_NOME)
    testo = crea_modello_riassunto(config).invoke(messaggi).text
    assert "Ottavio" in testo
    assert not re.search(r"\d{1,2}:\d{2}", testo)


def test_reale_nome_dopo_la_compressione(config, servizio_note, caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    grafo = crea_grafo(config, servizio_note, soglia=4, turni=1)
    cronologia, riassunto = [], ""
    for domanda in ("Ciao, mi chiamo Ottavio.", "Quanto fa 12 per 7?", "Quanti centimetri sono 3 pollici?",
                    "Come mi chiamo?"):
        cronologia, riassunto = esegui_turno_con_riassunto(grafo, cronologia, riassunto, domanda)
    assert any(re.match(r"riassunto: \d+ messaggi -> \d+ in ", m) for m in caplog.messages)
    assert "Ciao, mi chiamo Ottavio." not in [m.text for m in cronologia if m.type == "human"]
    assert "Ottavio" in cronologia[-1].text


def test_reale_riassunto_conserva_il_nome_di_una_presentazione_breve(config):
    # Caso della prova del 17/11/2026: con una presentazione breve gemma scriveva «si è presentato dicendo il suo
    # nome», senza il nome.
    trascrizione = (
        "Utente: Ciao, mi chiamo Ottavio.\n"
        "Assistente: Ciao Ottavio! È un piacere conoscerti. Come posso assisterti oggi nel laboratorio?"
    )
    messaggi = messaggi_per_il_riassunto(leggi_riassunto(RADICE / "riassunto.txt"), "", trascrizione)
    assert "Ottavio" in crea_modello_riassunto(config).invoke(messaggi).text


ROMA = ZoneInfo("Europe/Rome")
DOMANDA_CENTRIFUGA = "Spiegami in due frasi a che cosa serve una centrifuga."


def grafo_con_preferenze(config, servizio_note, preferenze):
    return crea_grafo(config, servizio_note, config.riassunto_soglia, config.riassunto_turni,
                      preferenze=blocco_preferenze(preferenze))


def parole(testo):
    return re.findall(r"\w+", testo.lower())


def test_reale_preferenze_fuso(config, servizio_note):
    grafo = grafo_con_preferenze(config, servizio_note, Preferenze("italiano", ZoneInfo("America/New_York"), "sintetico"))
    cronologia = esegui_turno(grafo, [], "Che ore sono?")
    richieste = [r for m in cronologia if m.type == "ai" for r in m.tool_calls if r["name"] == "ora_corrente"]
    assert richieste and all(r["args"].get("fuso") == "America/New_York" for r in richieste)
    risultato = next(m.content for m in cronologia if m.type == "tool" and m.name == "ora_corrente")
    ore, minuti = re.search(r"T(\d{2}):(\d{2})", risultato).groups()
    assert re.search(rf"\b0?{int(ore)}[:.]{minuti}\b", cronologia[-1].text)


def test_reale_preferenze_lingua(config, servizio_note, caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    grafo = grafo_con_preferenze(config, servizio_note, Preferenze("inglese", ROMA, "sintetico"))
    cronologia = esegui_turno(grafo, [], DOMANDA_CENTRIFUGA)
    risposta = parole(cronologia[-1].text)
    assert len({"the", "and", "is", "to"} & set(risposta)) >= 2
    assert not {"il", "che", "è", "una"} & set(risposta)
    assert not any(e_indicazione(m) for m in cronologia)
    assert any(m.startswith("revisore: coerente") for m in caplog.messages)


def test_reale_preferenze_stile(config, servizio_note):
    lunghezze = {}
    for stile in ("sintetico", "dettagliato"):
        grafo = grafo_con_preferenze(config, servizio_note, Preferenze("italiano", ROMA, stile))
        lunghezze[stile] = len(parole(esegui_turno(grafo, [], DOMANDA_CENTRIFUGA)[-1].text))
    assert lunghezze["dettagliato"] > lunghezze["sintetico"], lunghezze
