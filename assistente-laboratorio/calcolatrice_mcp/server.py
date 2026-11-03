"""Server MCP della calcolatrice: espone lo strumento `calcola` su stdio con FastMCP.

Lo stdout è riservato al protocollo MCP: il server non stampa nulla e i suoi log vanno su stderr.
"""

from mcp.server.fastmcp import FastMCP

from calcolatrice_mcp import calcolo

server = FastMCP("calcolatrice", log_level="WARNING")


@server.tool()
def calcola(espressione: str) -> str:
    """Calcola un'espressione aritmetica e restituisce il risultato esatto; da usare per ogni calcolo. Ammessi numeri (punto per i decimali), + - * / // % ** e parentesi; % è il resto della divisione, non la percentuale; ** è la potenza. Esempi: 2*(3+4), 12.5*8-3."""
    # `ErroreCalcolo` non si intercetta: FastMCP lo trasforma in un risultato `isError=True` con il messaggio.
    return calcolo.calcola(espressione)


def main() -> None:
    """Avvia il server sullo standard input/output."""
    server.run(transport="stdio")
