import _thread
import asyncio
import logging
import threading

import pytest
from langchain_core.tools import StructuredTool, ToolException

from assistente import client_mcp
from assistente.client_mcp import (
    CALCOLATRICE,
    ErroreMCP,
    ErroreTrasportoMCP,
    ServerMCP,
    carica_server_mcp,
    carica_strumenti_mcp,
    rendi_sincrono,
)

TUTTI = ["calcola", "cerca_apparecchi", "dettaglio_apparecchio", "elenca_apparecchi"]


def test_discovery_restituisce_strumenti_sincroni(caplog):
    caplog.set_level(logging.INFO, logger="assistente")
    strumenti = carica_strumenti_mcp()
    assert [s.name for s in strumenti] == TUTTI
    assert "resto della divisione" in strumenti[0].description and "espressione" in strumenti[0].args
    riga = next(m for m in caplog.messages if m.startswith("client_mcp: catalogo di calcolatrice letto in "))
    assert "calcola (" in riga
    riga = next(m for m in caplog.messages if m.startswith("client_mcp: catalogo di catalogo letto in "))
    assert "cerca_apparecchi (" in riga


SCHEMA = {"type": "object", "properties": {"espressione": {"type": "string"}}, "required": ["espressione"]}


@pytest.fixture(scope="module")
def calcola():
    return carica_server_mcp(CALCOLATRICE)[0]


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
        carica_server_mcp(ServerMCP("calcolatrice", tuple(argomenti), ("calcola",)))
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


async def attesa_che_trasforma_la_cancellazione():
    """Come anyio/mcp a sessione aperta: la cancellazione del task diventa un'eccezione ordinaria."""
    try:
        await asyncio.sleep(5)
    except asyncio.CancelledError:
        raise RuntimeError("BrokenResourceError simulato") from None


def ctrl_c_tra(secondi):
    """Simula Ctrl+C: `interrupt_main` usa lo stesso gestore di SIGINT di un Ctrl+C vero."""
    timer = threading.Timer(secondi, _thread.interrupt_main)
    timer.start()
    return timer


def test_ctrl_c_durante_la_chiamata_non_diventa_un_errore_di_trasporto():
    async def calcolo_lento(**argomenti):
        await attesa_che_trasforma_la_cancellazione()
    strumento = StructuredTool(name="calcola", description="prova", args_schema=SCHEMA, coroutine=calcolo_lento)
    timer = ctrl_c_tra(0.2)
    with pytest.raises(KeyboardInterrupt):
        rendi_sincrono(strumento).invoke({"espressione": "1"})
    timer.join()


def test_ctrl_c_durante_la_discovery_non_diventa_un_errore_mcp(monkeypatch):
    class ClientLento:
        def __init__(self, *argomenti, **opzioni):
            pass

        async def get_tools(self):
            await attesa_che_trasforma_la_cancellazione()

    monkeypatch.setattr(client_mcp, "MultiServerMCPClient", ClientLento)
    timer = ctrl_c_tra(0.2)
    with pytest.raises(KeyboardInterrupt):
        carica_strumenti_mcp()
    timer.join()


def test_discovery_da_un_altra_cartella(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert [s.name for s in carica_strumenti_mcp()] == TUTTI


def test_server_mancante_nomina_il_server():
    mancante = ServerMCP("catalogo", ("-m", "modulo_che_non_esiste"), ("cerca_apparecchi",))
    with pytest.raises(ErroreMCP) as errore:
        carica_strumenti_mcp((CALCOLATRICE, mancante))
    assert str(errore.value).startswith("server MCP catalogo non avviato")


def test_errore_di_trasporto_nomina_il_server():
    with pytest.raises(ErroreTrasportoMCP) as errore:
        rendi_sincrono(strumento_che_solleva(OSError("pipe chiusa")), server="catalogo").invoke({"espressione": "1"})
    assert str(errore.value) == "server MCP catalogo non raggiungibile: pipe chiusa"
