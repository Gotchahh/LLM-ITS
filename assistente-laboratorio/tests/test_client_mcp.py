import logging

import pytest
from langchain_core.tools import StructuredTool, ToolException

from assistente.client_mcp import ErroreMCP, ErroreTrasportoMCP, carica_strumenti_mcp, rendi_sincrono


def test_discovery_restituisce_strumenti_sincroni(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    strumenti = carica_strumenti_mcp()
    assert [s.name for s in strumenti] == ["calcola"]
    assert "resto della divisione" in strumenti[0].description and "espressione" in strumenti[0].args
    riga = next(m for m in caplog.messages if m.startswith("client_mcp: catalogo di calcolatrice letto in "))
    assert "calcola (" in riga


SCHEMA = {"type": "object", "properties": {"espressione": {"type": "string"}}, "required": ["espressione"]}


@pytest.fixture(scope="module")
def calcola():
    return carica_strumenti_mcp()[0]


def strumento_che_solleva(errore):
    async def solleva(**argomenti):
        raise errore
    return StructuredTool(name="calcola", description="prova", args_schema=SCHEMA, coroutine=solleva)


def test_invocazione_sincrona(calcola, caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    assert calcola.invoke({"espressione": "2+2"}) == "4"
    assert any(m.startswith("client_mcp: calcola eseguito in ") for m in caplog.messages)


def test_errore_di_validazione_senza_prefisso_inglese(calcola):
    with pytest.raises(ToolException) as errore:
        calcola.invoke({"espressione": "1/0"})
    assert str(errore.value) == "divisione per zero" and not isinstance(errore.value, ErroreTrasportoMCP)


def test_argomento_mancante_e_un_errore_di_validazione(calcola):
    with pytest.raises(ToolException) as errore:
        calcola.invoke({})
    assert not isinstance(errore.value, ErroreTrasportoMCP)


@pytest.mark.parametrize("argomenti, inizio", [
    (["-m", "modulo_che_non_esiste"], "server MCP calcolatrice non avviato (python"),
    (["-c", "from mcp.server.fastmcp import FastMCP; FastMCP('vuoto').run()"],
     "il server MCP calcolatrice non espone strumenti"),
    (["-c", "from mcp.server.fastmcp import FastMCP; s = FastMCP('altro'); "
            "s.add_tool(lambda: 'ok', name='altro', description='altro'); s.run()"],
     "il server MCP calcolatrice non espone lo strumento calcola"),
])
def test_discovery_fallita(argomenti, inizio):
    with pytest.raises(ErroreMCP) as errore:
        carica_strumenti_mcp(argomenti)
    assert str(errore.value).startswith(inizio)


def test_errore_di_trasporto(caplog):
    with pytest.raises(ErroreTrasportoMCP) as errore:
        rendi_sincrono(strumento_che_solleva(OSError("pipe chiusa"))).invoke({"espressione": "1"})
    assert str(errore.value) == "server MCP calcolatrice non raggiungibile: pipe chiusa"
    assert any(r.levelname == "WARNING" and "non raggiungibile" in r.getMessage() for r in caplog.records)


def test_tool_exception_dentro_un_gruppo_resta_validazione():
    gruppo = ExceptionGroup("gruppo", [ToolException("Error executing tool calcola: divisione per zero")])
    with pytest.raises(ToolException) as errore:
        rendi_sincrono(strumento_che_solleva(gruppo)).invoke({"espressione": "1/0"})
    assert str(errore.value) == "divisione per zero" and not isinstance(errore.value, ErroreTrasportoMCP)


def test_ctrl_c_non_diventa_un_errore_di_trasporto():
    with pytest.raises(KeyboardInterrupt):
        rendi_sincrono(strumento_che_solleva(KeyboardInterrupt())).invoke({"espressione": "1"})


def test_discovery_da_un_altra_cartella(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert [s.name for s in carica_strumenti_mcp()] == ["calcola"]
