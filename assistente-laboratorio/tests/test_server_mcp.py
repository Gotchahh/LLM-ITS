"""Test del server MCP della calcolatrice: avvio reale su stdio, catalogo, invocazione ed errori."""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

RADICE = Path(__file__).resolve().parent.parent


def col_server(operazione):
    """Avvia `python -m calcolatrice_mcp`, apre una sessione e restituisce `await operazione(sessione)`."""
    async def esegui():
        parametri = StdioServerParameters(command=sys.executable, args=["-m", "calcolatrice_mcp"], cwd=RADICE)
        async with stdio_client(parametri) as (lettura, scrittura):
            async with ClientSession(lettura, scrittura) as sessione:
                await sessione.initialize()
                return await operazione(sessione)
    return asyncio.run(esegui())


def test_catalogo_contiene_solo_calcola():
    strumenti = col_server(lambda s: s.list_tools()).tools
    assert [s.name for s in strumenti] == ["calcola"]
    assert "resto della divisione" in strumenti[0].description
    schema = strumenti[0].inputSchema
    assert schema["properties"]["espressione"]["type"] == "string" and schema["required"] == ["espressione"]


def test_invocazione_diretta():
    risultato = col_server(lambda s: s.call_tool("calcola", {"espressione": "2+3*4"}))
    assert not risultato.isError and risultato.content[0].text == "14"


def test_errore_controllato_senza_numero():
    risultato = col_server(lambda s: s.call_tool("calcola", {"espressione": "1/0"}))
    assert risultato.isError and risultato.content[0].text.endswith("divisione per zero")


def test_numero_invece_di_testo_e_un_errore():
    risultato = col_server(lambda s: s.call_tool("calcola", {"espressione": 5}))
    assert risultato.isError
