"""Test del server MCP del catalogo: avvio reale su stdio, catalogo, invocazione ed errori."""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

RADICE = Path(__file__).resolve().parent.parent


def col_server(operazione):
    """Avvia `python -m catalogo_mcp`, apre una sessione e restituisce `await operazione(sessione)`."""
    async def esegui():
        parametri = StdioServerParameters(command=sys.executable, args=["-m", "catalogo_mcp"], cwd=RADICE)
        async with stdio_client(parametri) as (lettura, scrittura):
            async with ClientSession(lettura, scrittura) as sessione:
                await sessione.initialize()
                return await operazione(sessione)
    return asyncio.run(esegui())


def test_catalogo_dei_tre_strumenti():
    nomi = [s.name for s in col_server(lambda s: s.list_tools()).tools]
    assert nomi == ["cerca_apparecchi", "dettaglio_apparecchio", "elenca_apparecchi"]


def test_invocazioni():
    async def tre(sessione):
        return (
            await sessione.call_tool("cerca_apparecchi", {"testo": "centrifuga"}),
            await sessione.call_tool("dettaglio_apparecchio", {"codice": "XYZ-99"}),
            await sessione.call_tool("elenca_apparecchi", {}),
        )
    cerca, dettaglio, elenco = col_server(tre)
    assert not cerca.isError and "CEN-01" in cerca.content[0].text
    assert dettaglio.isError and "nessun apparecchio" in dettaglio.content[0].text
    assert not elenco.isError and len(elenco.content[0].text.split("\n")) == 10
