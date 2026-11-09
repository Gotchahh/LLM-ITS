"""Client MCP: legge il catalogo dei server MCP (calcolatrice e catalogo) e rende sincroni i loro strumenti.

È l'unico modulo dell'agente che importa `asyncio` e `langchain_mcp_adapters`: il resto del programma
(grafo, CLI) resta sincrono e vede soltanto strumenti LangChain ordinari.
"""

import asyncio
import logging
import re
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from langchain_core.tools import BaseTool, StructuredTool, ToolException
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)

CARTELLA_PROGETTO = Path(__file__).resolve().parent.parent

PREFISSO_INGLESE = re.compile(r"^Error executing tool \S+: ")


@dataclass(frozen=True)
class ServerMCP:
    """Un server MCP su stdio: nome, argomenti dell'interprete e strumenti che deve esporre."""

    nome: str
    argomenti: tuple[str, ...]
    richiesti: tuple[str, ...]


CALCOLATRICE = ServerMCP("calcolatrice", ("-m", "calcolatrice_mcp"), ("calcola",))
CATALOGO = ServerMCP(
    "catalogo", ("-m", "catalogo_mcp"), ("cerca_apparecchi", "dettaglio_apparecchio", "elenca_apparecchi")
)
SERVER_MCP = (CALCOLATRICE, CATALOGO)


class ErroreMCP(Exception):
    """Il server MCP non si avvia o non espone lo strumento richiesto."""


class ErroreTrasportoMCP(ToolException):
    """Il server MCP non è raggiungibile durante una chiamata (non è un errore di validazione)."""


def _prima_foglia(errore: BaseException) -> BaseException:
    """Dentro un gruppo di eccezioni (anyio ne produce) scende, ricorsivamente, alla prima eccezione."""
    while isinstance(errore, BaseExceptionGroup):
        errore = errore.exceptions[0]
    return errore


def _dettaglio(errore: BaseException) -> str:
    """Testo della prima foglia di `errore` o, se vuoto, il nome del suo tipo."""
    foglia = _prima_foglia(errore)
    return str(foglia) or type(foglia).__name__


def _esegui(attesa):
    """Esegue una coroutine con `asyncio.run` senza perdere un Ctrl+C.

    Con Ctrl+C `asyncio.run` cancella il task, e rilancia `KeyboardInterrupt` solo se il task termina con
    `CancelledError`; a sessione aperta, anyio e mcp trasformano invece la cancellazione in un'eccezione
    ordinaria (un gruppo con `BrokenResourceError`). Qui la si riporta a `CancelledError`.
    """
    async def principale():
        try:
            return await attesa
        except Exception:
            compito = asyncio.current_task()
            if compito is not None and compito.cancelling():
                raise asyncio.CancelledError from None
            raise

    return asyncio.run(principale())


def _testo(contenuto) -> str:
    """Converte il contenuto di una risposta MCP (stringa o blocchi di testo) in una stringa."""
    if isinstance(contenuto, str):
        return contenuto
    return "\n".join(
        blocco if isinstance(blocco, str) else blocco["text"]
        for blocco in contenuto
        if isinstance(blocco, str) or blocco.get("type") == "text"
    )


def rendi_sincrono(strumento_mcp: BaseTool, server: str = CALCOLATRICE.nome) -> BaseTool:
    """Avvolge uno strumento MCP (solo asincrono) in uno strumento sincrono con lo stesso nome e schema.

    Ogni chiamata esegue `asyncio.run` sullo strumento originale. Gli errori restano distinti:
    una `ToolException` del server (validazione) mantiene il testo del server senza il prefisso inglese;
    ogni altra eccezione è un errore di trasporto (`ErroreTrasportoMCP`). `BaseException` (Ctrl+C) passa intatta.
    """
    nome = strumento_mcp.name

    def esegui(**argomenti) -> str:
        inizio = time.perf_counter()
        try:
            contenuto = _esegui(strumento_mcp.ainvoke(argomenti))
        except Exception as errore:
            foglia = _prima_foglia(errore)
            if isinstance(foglia, ToolException):
                raise ToolException(PREFISSO_INGLESE.sub("", str(foglia))) from errore
            dettaglio = _dettaglio(errore)
            logger.warning("client_mcp: server MCP %s non raggiungibile: %s", server, dettaglio)
            raise ErroreTrasportoMCP(f"server MCP {server} non raggiungibile: {dettaglio}") from errore
        logger.info("client_mcp: %s eseguito in %.1f s", nome, time.perf_counter() - inizio)
        return _testo(contenuto)

    return StructuredTool(
        name=nome,
        description=strumento_mcp.description,
        args_schema=strumento_mcp.args_schema,
        func=esegui,
    )


def carica_server_mcp(server: ServerMCP) -> list[BaseTool]:
    """Avvia un server MCP, ne legge il catalogo e restituisce gli strumenti sincroni.

    Il server si avvia con l'interprete corrente, dalla cartella del progetto. Se non parte, non espone
    strumenti o non espone uno degli strumenti richiesti, solleva `ErroreMCP` con un messaggio in italiano.
    """
    comando = " ".join([Path(sys.executable).name, *server.argomenti])
    connessione = {
        "transport": "stdio",
        "command": sys.executable,
        "args": list(server.argomenti),
        "cwd": str(CARTELLA_PROGETTO),
    }
    client = MultiServerMCPClient({server.nome: connessione}, handle_tool_errors=False)
    inizio = time.perf_counter()
    try:
        strumenti = _esegui(client.get_tools())
    except Exception as errore:
        raise ErroreMCP(f"server MCP {server.nome} non avviato ({comando}): {_dettaglio(errore)}") from errore
    if not strumenti:
        raise ErroreMCP(f"il server MCP {server.nome} non espone strumenti")
    nomi = {s.name for s in strumenti}
    for richiesto in server.richiesti:
        if richiesto not in nomi:
            raise ErroreMCP(f"il server MCP {server.nome} non espone lo strumento {richiesto}")
    elenco = "; ".join(f"{s.name} ({s.description})" for s in strumenti)
    logger.info(
        "client_mcp: catalogo di %s letto in %.1f s: %s", server.nome, time.perf_counter() - inizio, elenco
    )
    return [rendi_sincrono(s, server.nome) for s in strumenti]


def carica_strumenti_mcp(elenco: Sequence[ServerMCP] = SERVER_MCP) -> list[BaseTool]:
    """Gli strumenti sincroni di tutti i server dell'elenco, nell'ordine; il primo server che fallisce ferma tutto."""
    return [strumento for server in elenco for strumento in carica_server_mcp(server)]
