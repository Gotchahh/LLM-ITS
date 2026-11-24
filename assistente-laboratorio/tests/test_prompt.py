"""Test di `assistente/prompt.py`: lettura e controllo del comando /prompt, elenco di /prompts, log."""

import logging

import pytest

from assistente.client_mcp import ArgomentoPrompt, DefinizionePrompt, ErroreMCP
from assistente.prompt import (
    ErrorePrompt,
    carica_prompt,
    compila_prompt,
    controlla,
    leggi_comando,
    righe_elenco,
)

ELENCO = [
    DefinizionePrompt("spiega", "Spiega un argomento al livello richiesto.", (
        ArgomentoPrompt("argomento", "concetto da spiegare", True),
        ArgomentoPrompt("livello", "base (predefinito), intermedio o avanzato", False),
    )),
    DefinizionePrompt("riassumi_conversazione", "Riassume la conversazione finora.", (
        ArgomentoPrompt("stile", "sintetico o dettagliato", True),
    )),
]
RIGA_NON_VALIDA = (
    "riga non valida. Scrivi /prompt nome argomento=valore (virgolette doppie per i valori con spazi)."
)


def test_riga_con_virgolette_e_senza():
    assert leggi_comando('spiega argomento="Model Context Protocol" livello=base') == (
        "spiega", {"argomento": "Model Context Protocol", "livello": "base"}
    )


def test_riga_senza_argomenti_e_con_un_argomento():
    assert leggi_comando("riassumi_conversazione") == ("riassumi_conversazione", {})
    assert leggi_comando("riassumi_conversazione stile=sintetico") == (
        "riassumi_conversazione", {"stile": "sintetico"}
    )


def test_spazi_multipli_e_tab_tra_le_coppie():
    assert leggi_comando("  spiega \t argomento=pH   livello=base  ") == (
        "spiega", {"argomento": "pH", "livello": "base"}
    )


@pytest.mark.parametrize(("riga", "valore"), [
    ("spiega argomento=l'entropia", "l'entropia"),
    ('spiega argomento="l\'effetto Doppler"', "l'effetto Doppler"),
])
def test_apostrofi_nei_valori_accettati(riga, valore):                              # Review Focus 1
    assert leggi_comando(riga) == ("spiega", {"argomento": valore})


@pytest.mark.parametrize("riga", [
    "",
    "   ",
    "spiega argomento",
    'spiega argomento="Model Context',
    "spiega argomento=",
    'spiega argomento=""',
    "spiega =x",
    "argomento=x",
    'spiega argomento="a"b',
])
def test_riga_mal_scritta(riga):                                                    # Review Focus 4
    with pytest.raises(ErrorePrompt) as errore:
        leggi_comando(riga)
    assert str(errore.value) == RIGA_NON_VALIDA


def test_argomento_ripetuto():
    with pytest.raises(ErrorePrompt) as errore:
        leggi_comando("spiega argomento=a argomento=b")
    assert str(errore.value) == "l'argomento argomento è ripetuto."


@pytest.mark.parametrize("nome", ["Spiega", "saluta"])
def test_prompt_sconosciuto(nome):                                                  # Review Focus 2
    with pytest.raises(ErrorePrompt) as errore:
        controlla(nome, {"argomento": "x"}, ELENCO)
    assert str(errore.value) == f"il prompt {nome} non esiste. Scrivi /prompts per l'elenco."


def test_obbligatorio_mancante():
    with pytest.raises(ErrorePrompt) as errore:
        controlla("spiega", {"livello": "base"}, ELENCO)
    assert str(errore.value) == (
        "al prompt spiega manca l'argomento obbligatorio argomento. Scrivi /prompts per l'elenco."
    )


def test_argomento_sconosciuto():
    with pytest.raises(ErrorePrompt) as errore:
        controlla("spiega", {"argomento": "x", "colore": "blu"}, ELENCO)
    assert str(errore.value) == "il prompt spiega non ha l'argomento colore. Scrivi /prompts per l'elenco."


def test_facoltativo_omesso_nessun_errore():
    controlla("spiega", {"argomento": "x"}, ELENCO)


def test_righe_dell_elenco():
    assert righe_elenco(ELENCO) == [
        "spiega(argomento, [livello]): Spiega un argomento al livello richiesto.",
        "  argomento: concetto da spiegare; livello: base (predefinito), intermedio o avanzato",
        "riassumi_conversazione(stile): Riassume la conversazione finora.",
        "  stile: sintetico o dettagliato",
    ]


def test_righe_dell_elenco_senza_descrizioni_degli_argomenti():
    elenco = [DefinizionePrompt("p", "Prova.", (ArgomentoPrompt("a", "", True),))]
    assert righe_elenco(elenco) == ["p(a): Prova."]


def test_carica_prompt_restituisce_l_elenco_e_scrive_il_log(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    assert carica_prompt(lambda: ELENCO) == ELENCO
    [riga] = [m for m in caplog.messages if m.startswith("prompt: ")]
    assert riga.startswith("prompt: elenco letto in ")
    assert riga.endswith(" s: spiega(argomento, livello), riassumi_conversazione(stile)")


def test_carica_prompt_con_errore_restituisce_none_e_warning(caplog):
    def fallisce():
        raise ErroreMCP("x")

    assert carica_prompt(fallisce) is None
    avvisi = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert [r.getMessage() for r in avvisi] == ["prompt: elenco non disponibile (x), comandi /prompt disattivati"]


def test_compila_prompt_chiede_il_testo_e_lo_scrive_nel_log(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    chiamate = []

    def richiedi(nome, argomenti):
        chiamate.append((nome, argomenti))
        return "Riga 1\nRiga 2"

    assert compila_prompt("spiega argomento=l'entropia", ELENCO, richiedi) == "Riga 1\nRiga 2"
    assert chiamate == [("spiega", {"argomento": "l'entropia"})]
    assert 'prompt: spiega {"argomento": "l\'entropia"} -> «Riga 1 Riga 2»' in caplog.messages


@pytest.mark.parametrize("resto", ["", "spiega livello=base", "saluta", 'spiega argomento="x'])
def test_compila_prompt_con_richiesta_sbagliata_non_chiama_il_server(resto):
    chiamate = []
    with pytest.raises(ErrorePrompt):
        compila_prompt(resto, ELENCO, lambda nome, argomenti: chiamate.append(nome))
    assert chiamate == []


def test_compila_prompt_lascia_passare_l_errore_del_server():
    def richiedi(nome, argomenti):
        raise ErroreMCP("prompt spiega non letto dal server MCP prompt: livello non valido")

    with pytest.raises(ErroreMCP):
        compila_prompt("spiega argomento=x livello=esperto", ELENCO, richiedi)
