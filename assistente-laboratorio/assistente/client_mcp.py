"""Client MCP: legge il catalogo del server della calcolatrice e rende sincroni i suoi strumenti.

È l'unico modulo dell'agente che importa `asyncio` e `langchain_mcp_adapters`: il resto del programma
(grafo, CLI) resta sincrono e vede soltanto strumenti LangChain ordinari.
"""

import asyncio
import logging
import re
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from langchain_core.tools import BaseTool, StructuredTool, ToolException
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = logging.getLogger(__name__)

NOME_SERVER = "calcolatrice"
STRUMENTO_RICHIESTO = "calcola"
ARGOMENTI_SERVER = ("-m", "calcolatrice_mcp")
CARTELLA_PROGETTO = Path(__file__).resolve().parent.parent

PREFISSO_INGLESE = re.compile(r"^Error executing tool \S+: ")


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


def _testo(contenuto) -> str:
    """Converte il contenuto di una risposta MCP (stringa o blocchi di testo) in una stringa."""
    if isinstance(contenuto, str):
        return contenuto
    return "\n".join(
        blocco if isinstance(blocco, str) else blocco["text"]
        for blocco in contenuto
        if isinstance(blocco, str) or blocco.get("type") == "text"
    )


def rendi_sincrono(strumento_mcp: BaseTool) -> BaseTool:
    """Avvolge uno strumento MCP (solo asincrono) in uno strumento sincrono con lo stesso nome e schema.

    Ogni chiamata esegue `asyncio.run` sullo strumento originale. Gli errori restano distinti:
    una `ToolException` del server (validazione) mantiene il testo del server senza il prefisso inglese;
    ogni altra eccezione è un errore di trasporto (`ErroreTrasportoMCP`). `BaseException` (Ctrl+C) passa intatta.
    """
    nome = strumento_mcp.name

    def esegui(**argomenti) -> str:
        inizio = time.perf_counter()
        try:
            contenuto = asyncio.run(strumento_mcp.ainvoke(argomenti))
        except Exception as errore:
            foglia = _prima_foglia(errore)
            if isinstance(foglia, ToolException):
                raise ToolException(PREFISSO_INGLESE.sub("", str(foglia))) from errore
            dettaglio = _dettaglio(errore)
            logger.warning("client_mcp: server MCP %s non raggiungibile: %s", NOME_SERVER, dettaglio)
            raise ErroreTrasportoMCP(f"server MCP {NOME_SERVER} non raggiungibile: {dettaglio}") from errore
        logger.info("client_mcp: %s eseguito in %.1f s", nome, time.perf_counter() - inizio)
        return _testo(contenuto)

    return StructuredTool(
        name=nome,
        description=strumento_mcp.description,
        args_schema=strumento_mcp.args_schema,
        func=esegui,
    )


def carica_strumenti_mcp(argomenti: Sequence[str] = ARGOMENTI_SERVER) -> list[BaseTool]:
    """Avvia il server MCP della calcolatrice, ne legge il catalogo e restituisce gli strumenti sincroni.

    Il server si avvia con l'interprete corrente, dalla cartella del progetto. Se non parte, non espone
    strumenti o non espone `calcola`, solleva `ErroreMCP` con un messaggio in italiano.
    """
    comando = " ".join([Path(sys.executable).name, *argomenti])
    connessione = {
        "transport": "stdio",
        "command": sys.executable,
        "args": list(argomenti),
        "cwd": str(CARTELLA_PROGETTO),
    }
    client = MultiServerMCPClient({NOME_SERVER: connessione}, handle_tool_errors=False)
    inizio = time.perf_counter()
    try:
        strumenti = asyncio.run(client.get_tools())
    except Exception as errore:
        raise ErroreMCP(f"server MCP {NOME_SERVER} non avviato ({comando}): {_dettaglio(errore)}") from errore
    if not strumenti:
        raise ErroreMCP(f"il server MCP {NOME_SERVER} non espone strumenti")
    if STRUMENTO_RICHIESTO not in {s.name for s in strumenti}:
        raise ErroreMCP(f"il server MCP {NOME_SERVER} non espone lo strumento {STRUMENTO_RICHIESTO}")
    elenco = "; ".join(f"{s.name} ({s.description})" for s in strumenti)
    logger.info(
        "client_mcp: catalogo di %s letto in %.1f s: %s", NOME_SERVER, time.perf_counter() - inizio, elenco
    )
    return [rendi_sincrono(s) for s in strumenti]
