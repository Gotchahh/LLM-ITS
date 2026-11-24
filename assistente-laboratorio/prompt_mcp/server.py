"""Server MCP dei prompt: espone `spiega` e `riassumi_conversazione` su stdio con FastMCP, senza strumenti né
resource.

Ogni prompt restituisce un solo messaggio utente in italiano. I valori degli argomenti li controlla il server:
un valore non ammesso fa fallire `prompts/get` con un messaggio in italiano. Lo stdout è riservato al protocollo
MCP: il server non stampa nulla e i suoi log vanno su stderr. Non importa nulla da `assistente/`.
"""

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

# FastMCP registra ogni prompt fallito con il traceback, e lo stderr del server finisce nel terminale della chat:
# il server resta silenzioso e il motivo arriva all'host nella risposta d'errore.
server = FastMCP("prompt", log_level="CRITICAL")

LIVELLI = {
    "base": "usa parole semplici e un esempio concreto, senza formule.",
    "intermedio": "usa i termini tecnici principali spiegandoli, con un esempio.",
    "avanzato": "usa il linguaggio tecnico, con i dettagli, le formule se servono e i limiti.",
}
STILI = {
    "sintetico": "pochi punti brevi con gli argomenti principali.",
    "dettagliato": "gli argomenti trattati, i risultati ottenuti e le decisioni prese, nell'ordine.",
}


def _scegli(nome: str, valore: str, ammessi: dict[str, str]) -> str:
    """Il valore normalizzato (`strip().lower()`); se non è ammesso, `ValueError` con i valori ammessi."""
    chiave = valore.strip().lower()
    if chiave not in ammessi:
        *primi, ultimo = ammessi
        raise ValueError(f"{nome} non valido («{valore}»): usa {', '.join(primi)} o {ultimo}")
    return chiave


@server.prompt()
def spiega(
    argomento: Annotated[str, Field(description="concetto da spiegare")],
    livello: Annotated[str, Field(description="base (predefinito), intermedio o avanzato")] = "base",
) -> str:
    """Spiega un argomento al livello richiesto."""
    livello = _scegli("livello", livello, LIVELLI)
    return f"Spiegami «{argomento}» a livello {livello}: {LIVELLI[livello]}"


@server.prompt()
def riassumi_conversazione(
    stile: Annotated[str, Field(description="sintetico o dettagliato")],
) -> str:
    """Riassume la conversazione finora."""
    stile = _scegli("stile", stile, STILI)
    return f"Riassumi la conversazione che abbiamo avuto finora, in modo {stile}: {STILI[stile]}"


def main() -> None:
    """Avvia il server sullo standard input/output."""
    server.run(transport="stdio")
