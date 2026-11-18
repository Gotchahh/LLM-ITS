"""Server MCP delle preferenze: espone `utente://preferenze` come resource su stdio con FastMCP, senza strumenti.

La resource restituisce il testo del file delle preferenze letto al momento della richiesta, senza controllarlo:
i controlli li fa l'host. Lo stdout è riservato al protocollo MCP: il server non stampa nulla e i suoi log vanno
su stderr.
"""

import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

server = FastMCP("preferenze", log_level="WARNING")
percorso = Path("preferenze.json")


@server.resource("utente://preferenze", name="preferenze", mime_type="application/json")
def preferenze() -> str:
    """Preferenze dell'utente (lingua delle risposte, fuso orario predefinito, stile), come testo JSON."""
    # Un file mancante o illeggibile non si intercetta: la lettura della resource risponde con un errore MCP.
    # `utf-8-sig` toglie il BOM che PowerShell 5.1 aggiunge con `Set-Content -Encoding utf8`.
    return percorso.read_text(encoding="utf-8-sig")


def main(argv: list[str] | None = None) -> None:
    """Avvia il server sullo standard input/output; il primo argomento, se c'è, è il percorso del file."""
    global percorso
    argomenti = sys.argv[1:] if argv is None else argv
    if argomenti:
        percorso = Path(argomenti[0])
    server.run(transport="stdio")
