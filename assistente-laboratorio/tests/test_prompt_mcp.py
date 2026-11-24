"""Test del server MCP dei prompt: avvio reale su stdio, elenco, testo compilato, valori rifiutati, nessuno strumento."""

import asyncio
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import McpError

RADICE = Path(__file__).resolve().parent.parent

SPIEGA_BASE = (
    "Spiegami «Model Context Protocol» a livello base: "
    "usa parole semplici e un esempio concreto, senza formule."
)
RIASSUNTO_DETTAGLIATO = (
    "Riassumi la conversazione che abbiamo avuto finora, in modo dettagliato: "
    "gli argomenti trattati, i risultati ottenuti e le decisioni prese, nell'ordine."
)


def col_server(operazione):
    """Avvia `python -m prompt_mcp`, apre una sessione e restituisce `await operazione(sessione)`."""
    async def esegui():
        parametri = StdioServerParameters(command=sys.executable, args=["-m", "prompt_mcp"], cwd=RADICE)
        async with stdio_client(parametri) as (lettura, scrittura):
            async with ClientSession(lettura, scrittura) as sessione:
                await sessione.initialize()
                return await operazione(sessione)
    return asyncio.run(esegui())


def messaggi_del_prompt(nome, argomenti):
    """Il risultato di `prompts/get`: lista di (ruolo, testo) dei messaggi."""
    async def leggi(sessione):
        risultato = await sessione.get_prompt(nome, argomenti)
        return [(m.role, m.content.text) for m in risultato.messages]
    return col_server(leggi)


def test_elenco_con_due_prompt_descrizioni_e_argomenti():
    elenco = col_server(lambda sessione: sessione.list_prompts()).prompts
    assert [(p.name, p.description) for p in elenco] == [
        ("spiega", "Spiega un argomento al livello richiesto."),
        ("riassumi_conversazione", "Riassume la conversazione finora."),
    ]
    argomenti = {p.name: [(a.name, a.description, a.required) for a in p.arguments] for p in elenco}
    assert argomenti == {
        "spiega": [
            ("argomento", "concetto da spiegare", True),
            ("livello", "base (predefinito), intermedio o avanzato", False),
        ],
        "riassumi_conversazione": [("stile", "sintetico o dettagliato", True)],
    }


def test_nessuno_strumento_ne_resource():
    async def elenchi(sessione):
        return await sessione.list_tools(), await sessione.list_resources()

    strumenti, resource = col_server(elenchi)
    assert strumenti.tools == [] and resource.resources == []


def test_spiega_un_solo_messaggio_utente_con_il_testo_del_livello():
    assert messaggi_del_prompt("spiega", {"argomento": "Model Context Protocol", "livello": "base"}) == [
        ("user", SPIEGA_BASE)
    ]


def test_spiega_senza_livello_usa_base():
    [(_, testo)] = messaggi_del_prompt("spiega", {"argomento": "pH"})
    assert testo.startswith("Spiegami «pH» a livello base: ")


@pytest.mark.parametrize(("valore", "atteso"), [("Base", "base"), (" intermedio ", "intermedio")])
def test_livello_con_maiuscole_o_spazi_accettato(valore, atteso):                  # Review Focus 2
    [(_, testo)] = messaggi_del_prompt("spiega", {"argomento": "pH", "livello": valore})
    assert f"a livello {atteso}: " in testo


def test_livelli_intermedio_e_avanzato_hanno_indicazioni_diverse():
    [(_, intermedio)] = messaggi_del_prompt("spiega", {"argomento": "pH", "livello": "intermedio"})
    [(_, avanzato)] = messaggi_del_prompt("spiega", {"argomento": "pH", "livello": "avanzato"})
    assert intermedio.endswith("usa i termini tecnici principali spiegandoli, con un esempio.")
    assert avanzato.endswith("usa il linguaggio tecnico, con i dettagli, le formule se servono e i limiti.")


def test_riassumi_conversazione_dettagliato():
    assert messaggi_del_prompt("riassumi_conversazione", {"stile": "dettagliato"}) == [
        ("user", RIASSUNTO_DETTAGLIATO)
    ]


def test_riassumi_conversazione_sintetico():
    [(_, testo)] = messaggi_del_prompt("riassumi_conversazione", {"stile": "sintetico"})
    assert testo == ("Riassumi la conversazione che abbiamo avuto finora, in modo sintetico: "
                     "pochi punti brevi con gli argomenti principali.")


@pytest.mark.parametrize(("nome", "argomenti", "messaggio"), [
    ("spiega", {"argomento": "pH", "livello": "esperto"},
     "livello non valido («esperto»): usa base, intermedio o avanzato"),
    ("riassumi_conversazione", {"stile": "breve"}, "stile non valido («breve»): usa sintetico o dettagliato"),
])
def test_valore_non_ammesso_errore_in_italiano_e_server_ancora_attivo(nome, argomenti, messaggio):
    async def prova(sessione):
        with pytest.raises(McpError) as errore:
            await sessione.get_prompt(nome, argomenti)
        elenco = await sessione.list_prompts()
        return str(errore.value), len(elenco.prompts)

    testo, quanti = col_server(prova)
    assert messaggio in testo and quanti == 2
