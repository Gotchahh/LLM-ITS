"""Client MCP: legge il catalogo dei server MCP (calcolatrice e catalogo) e rende sincroni i loro strumenti;
legge anche la resource delle preferenze dell'utente, che l'host usa come contesto e non diventa uno strumento,
e i prompt del server dei prompt (elenco all'avvio, testo compilato a ogni `/prompt`), che sceglie l'utente.

È l'unico modulo dell'agente che importa `asyncio` e `langchain_mcp_adapters`: il resto del programma
(grafo, CLI) resta sincrono e vede soltanto strumenti LangChain ordinari e testo.
"""

import asyncio
import logging
import re
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool, StructuredTool, ToolException
from langchain_mcp_adapters.client import MultiServerMCPClient
from mcp.shared.exceptions import McpError
from mcp.types import CONNECTION_CLOSED

logger = logging.getLogger(__name__)

CARTELLA_PROGETTO = Path(__file__).resolve().parent.parent

PREFISSO_INGLESE = re.compile(r"^Error executing tool \S+: ")
PREFISSO_PROMPT = re.compile(r"^Error rendering prompt \S+: ")


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

# Server della sola resource delle preferenze: non espone strumenti e non è tra i server degli strumenti.
PREFERENZE = ServerMCP("preferenze", ("-m", "preferenze_mcp"), ())
URI_PREFERENZE = "utente://preferenze"

# Server dei soli prompt: non espone strumenti e non è tra i server degli strumenti.
PROMPT = ServerMCP("prompt", ("-m", "prompt_mcp"), ())


@dataclass(frozen=True)
class ArgomentoPrompt:
    """Un argomento di un prompt come lo descrive `prompts/list` (descrizione vuota se il server non la dà)."""

    nome: str
    descrizione: str
    obbligatorio: bool


@dataclass(frozen=True)
class DefinizionePrompt:
    """Un prompt del server: nome, descrizione e argomenti nell'ordine del server."""

    nome: str
    descrizione: str
    argomenti: tuple[ArgomentoPrompt, ...]


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


def _eccezione_prima(errore: BaseException) -> BaseException:
    """La causa più interna di `errore` (per esempio l'errore del server dietro quello dell'adattatore)."""
    foglia = _prima_foglia(errore)
    while foglia.__cause__ is not None:
        foglia = _prima_foglia(foglia.__cause__)
    return foglia


def _causa_prima(errore: BaseException) -> str:
    """Testo della causa più interna di `errore` o, se vuoto, il nome del suo tipo."""
    foglia = _eccezione_prima(errore)
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


def _connessione(server: ServerMCP) -> dict:
    """Connessione stdio al server: interprete corrente, dalla cartella del progetto."""
    return {
        "transport": "stdio",
        "command": sys.executable,
        "args": list(server.argomenti),
        "cwd": str(CARTELLA_PROGETTO),
    }


def _comando(server: ServerMCP) -> str:
    """Il comando del server per i messaggi d'errore, per esempio `python.exe -m calcolatrice_mcp`."""
    return " ".join([Path(sys.executable).name, *server.argomenti])


def carica_server_mcp(server: ServerMCP) -> list[BaseTool]:
    """Avvia un server MCP, ne legge il catalogo e restituisce gli strumenti sincroni.

    Il server si avvia con l'interprete corrente, dalla cartella del progetto. Se non parte, non espone
    strumenti o non espone uno degli strumenti richiesti, solleva `ErroreMCP` con un messaggio in italiano.
    """
    comando = _comando(server)
    client = MultiServerMCPClient({server.nome: _connessione(server)}, handle_tool_errors=False)
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


def leggi_resource_mcp(server: ServerMCP, uri: str) -> str:
    """Avvia il server MCP, legge la resource `uri` e ne restituisce il testo.

    Server che non parte, resource che non si legge o senza contenuto: `ErroreMCP` con un messaggio in italiano.
    Nessuna riga di log: le scrive chi usa il testo.
    """
    client = MultiServerMCPClient({server.nome: _connessione(server)})
    try:
        contenuti = _esegui(client.get_resources(server.nome, uris=[uri]))
    except Exception as errore:
        raise ErroreMCP(
            f"resource {uri} non letta dal server MCP {server.nome} ({_comando(server)}): {_causa_prima(errore)}"
        ) from errore
    if not contenuti:
        raise ErroreMCP(f"resource {uri} non letta dal server MCP {server.nome} ({_comando(server)}): nessun contenuto")
    return contenuti[0].as_string()


def leggi_preferenze_mcp() -> str:
    """Il testo della resource delle preferenze dell'utente (`utente://preferenze`)."""
    return leggi_resource_mcp(PREFERENZE, URI_PREFERENZE)


def leggi_elenco_prompt(server: ServerMCP = PROMPT) -> list[DefinizionePrompt]:
    """Avvia il server dei prompt e ne legge l'elenco (`prompts/list`), nell'ordine del server.

    Server che non parte o elenco che non si legge: `ErroreMCP` con un messaggio in italiano. Nessuna riga di log.
    """
    client = MultiServerMCPClient({server.nome: _connessione(server)})

    async def elenco():
        async with client.session(server.nome) as sessione:
            return await sessione.list_prompts()

    try:
        risultato = _esegui(elenco())
    except Exception as errore:
        raise ErroreMCP(
            f"elenco dei prompt non letto dal server MCP {server.nome} ({_comando(server)}): {_causa_prima(errore)}"
        ) from errore
    return [
        DefinizionePrompt(
            p.name,
            p.description or "",
            tuple(ArgomentoPrompt(a.name, a.description or "", bool(a.required)) for a in p.arguments or ()),
        )
        for p in risultato.prompts
    ]


def richiedi_prompt(nome: str, argomenti: dict[str, str], server: ServerMCP = PROMPT) -> str:
    """Chiede al server il prompt `nome` con gli `argomenti` (`prompts/get`) e restituisce il testo compilato.

    Errore del server (per esempio un valore non ammesso): `ErroreMCP` con il suo messaggio, senza il prefisso
    inglese di FastMCP. Server che non parte, o risposta che non è un solo messaggio utente di testo: `ErroreMCP`.
    """
    client = MultiServerMCPClient({server.nome: _connessione(server)})
    try:
        messaggi = _esegui(client.get_prompt(server.nome, nome, arguments=argomenti))
    except Exception as errore:
        causa = _eccezione_prima(errore)
        if isinstance(causa, McpError) and causa.error.code != CONNECTION_CLOSED:   # il server ha risposto
            motivo = PREFISSO_PROMPT.sub("", str(causa))
            raise ErroreMCP(f"prompt {nome} non letto dal server MCP {server.nome}: {motivo}") from errore
        raise ErroreMCP(
            f"prompt {nome} non letto dal server MCP {server.nome} ({_comando(server)}): {_causa_prima(errore)}"
        ) from errore
    if len(messaggi) != 1 or not isinstance(messaggi[0], HumanMessage) or not isinstance(messaggi[0].content, str):
        raise ErroreMCP(
            f"prompt {nome} non letto dal server MCP {server.nome}: "
            "risposta inattesa (atteso un solo messaggio utente di testo)"
        )
    return messaggi[0].content
