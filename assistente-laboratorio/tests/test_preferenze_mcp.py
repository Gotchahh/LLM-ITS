"""Test del server MCP delle preferenze: avvio reale su stdio, resource elencata e letta, nessuno strumento, errori."""

import asyncio
import json
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import McpError

RADICE = Path(__file__).resolve().parent.parent
URI = "utente://preferenze"


def col_server(operazione, *argomenti, errori=sys.stderr):
    """Avvia `python -m preferenze_mcp [argomenti]`, apre una sessione e restituisce `await operazione(sessione)`.

    Lo stderr del server va in `errori`.
    """
    async def esegui():
        parametri = StdioServerParameters(
            command=sys.executable, args=["-m", "preferenze_mcp", *argomenti], cwd=RADICE
        )
        async with stdio_client(parametri, errlog=errori) as (lettura, scrittura):
            async with ClientSession(lettura, scrittura) as sessione:
                await sessione.initialize()
                return await operazione(sessione)
    return asyncio.run(esegui())


async def leggi_la_resource(sessione):
    risultato = await sessione.read_resource(URI)
    return risultato.contents[0].text


def test_una_sola_resource_e_nessuno_strumento():
    async def elenchi(sessione):
        return await sessione.list_resources(), await sessione.list_tools()

    resource, strumenti = col_server(elenchi)
    assert [(str(r.uri), r.name, r.mimeType) for r in resource.resources] == [
        (URI, "preferenze", "application/json")
    ]
    assert strumenti.tools == []


def test_senza_argomento_legge_il_file_del_progetto():
    testo = col_server(leggi_la_resource)
    assert testo == (RADICE / "preferenze.json").read_text(encoding="utf-8")
    assert json.loads(testo) == {"lingua": "italiano", "fuso": "Europe/Rome", "stile": "sintetico"}


def test_file_con_bom_letto_senza_bom(tmp_path):                                 # Review Focus 1
    file = tmp_path / "preferenze.json"
    file.write_bytes("\ufeff{\"lingua\": \"inglese\"}".encode("utf-8"))
    assert col_server(leggi_la_resource, str(file)) == "{\"lingua\": \"inglese\"}"


def test_il_file_si_rilegge_a_ogni_lettura(tmp_path):
    file = tmp_path / "preferenze.json"
    file.write_text("{\"stile\": \"sintetico\"}", encoding="utf-8")

    async def due_letture(sessione):
        prima = await leggi_la_resource(sessione)
        file.write_text("{\"stile\": \"dettagliato\"}", encoding="utf-8")
        return prima, await leggi_la_resource(sessione)

    assert col_server(due_letture, str(file)) == ("{\"stile\": \"sintetico\"}", "{\"stile\": \"dettagliato\"}")


def test_file_mancante_errore_e_server_ancora_in_piedi(tmp_path):
    async def lettura_fallita(sessione):
        with pytest.raises(McpError):
            await sessione.read_resource(URI)
        return await sessione.list_resources()

    resource = col_server(lettura_fallita, str(tmp_path / "manca.json"))
    assert [str(r.uri) for r in resource.resources] == [URI]


def test_file_mancante_nessun_traceback_sullo_stderr(tmp_path):
    """Lo stderr del server finisce nel terminale della chat: l'errore lo riporta l'host, in una riga di log."""
    async def lettura_fallita(sessione):
        with pytest.raises(McpError):
            await sessione.read_resource(URI)

    stderr = tmp_path / "stderr.txt"
    with stderr.open("w", encoding="utf-8") as errori:
        col_server(lettura_fallita, str(tmp_path / "manca.json"), errori=errori)
    assert stderr.read_text(encoding="utf-8") == ""
