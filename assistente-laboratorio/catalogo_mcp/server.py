"""Server MCP del catalogo: tre strumenti sugli stessi dati, su stdio con FastMCP.

Lo stdout è riservato al protocollo MCP: il server non stampa nulla e i suoi log vanno su stderr.
"""

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from catalogo_mcp import apparecchi

FILE_DATI = Path(__file__).with_name("apparecchi.json")

server = FastMCP("catalogo", log_level="WARNING")
dati: list[dict] = []


@server.tool()
def cerca_apparecchi(testo: str) -> str:
    """Cerca gli apparecchi del laboratorio (microscopi, centrifughe, bilance...) per codice, nome, tipo o note e dice dove sono, in che stato e quando sono stati calibrati; da usare per domande come «dov'è la centrifuga?»."""
    # `ErroreCatalogo` non si intercetta: FastMCP lo trasforma in un risultato `isError=True` con il messaggio.
    return apparecchi.cerca(dati, testo)


@server.tool()
def dettaglio_apparecchio(codice: str) -> str:
    """Restituisce tutte le informazioni di un apparecchio del laboratorio dato il suo codice, per esempio MIC-02."""
    return apparecchi.dettaglio(dati, codice)


@server.tool()
def elenca_apparecchi(stanza: str | None = None, stato: str | None = None) -> str:
    """Elenca gli apparecchi del laboratorio, facoltativamente solo quelli di una stanza (per esempio B12) e/o con uno stato tra: disponibile, in uso, in manutenzione, fuori servizio."""
    return apparecchi.elenca(dati, stanza, stato)


def main() -> None:
    """Legge il catalogo (un file non valido ferma l'avvio) e avvia il server sullo standard input/output."""
    dati[:] = apparecchi.carica(FILE_DATI)
    server.run(transport="stdio")
