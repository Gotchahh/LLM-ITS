"""Strumenti delle note: chiamano il servizio `note_api` con `urllib` (nessun client HTTP esterno)."""

import json
import urllib.error
import urllib.request
from datetime import datetime
from typing import Annotated
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

from langchain_core.tools import BaseTool, StructuredTool, ToolException

TIMEOUT = 5
LIMITE = 20

DESCRIZIONE_SALVA = (
    "Salva una nota nel servizio delle note del laboratorio; da usare quando l'utente chiede di segnare, "
    "annotare o ricordare qualcosa"
)
DESCRIZIONE_ELENCA = (
    "Elenca le note salvate, dalla più recente, con numero e data; con cerca solo quelle che contengono "
    "quel testo; da usare per ogni domanda sulle note salvate"
)
DESCRIZIONE_CANCELLA = (
    "Cancella la nota con il numero dato; se l'utente indica la nota per argomento, prima usare elenca_note "
    "per trovarne il numero"
)
DESCRIZIONE_TESTO = "Il testo della nota, da 1 a 500 caratteri"
DESCRIZIONE_CERCA = "Testo da cercare nelle note, senza distinzione di maiuscole; omettere per tutte le note"
DESCRIZIONE_NUMERO = "Il numero della nota da cancellare, un intero come 3"


def _rifiuta(messaggio: str):
    """Argomenti mancanti o del tipo sbagliato: ToolException in italiano, senza la traccia di validazione."""

    def rifiuta(_errore) -> str:
        raise ToolException(messaggio)

    return rifiuta


def _richiesta(url: str, metodo: str, percorso: str, corpo: dict | None = None) -> dict:
    """Chiamata JSON al servizio; errori HTTP e di rete diventano ToolException in italiano."""
    dati = None if corpo is None else json.dumps(corpo).encode("utf-8")
    richiesta = urllib.request.Request(
        url + percorso, data=dati, method=metodo, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(richiesta, timeout=TIMEOUT) as risposta:
            return json.loads(risposta.read().decode("utf-8"))
    except urllib.error.HTTPError as errore:
        try:
            messaggio = json.loads(errore.read().decode("utf-8"))["errore"]
        except (ValueError, KeyError, TypeError):
            messaggio = f"il servizio delle note ha risposto con l'errore {errore.code}"
        raise ToolException(messaggio) from None
    except (urllib.error.URLError, OSError, ValueError):
        raise ToolException(f"servizio note non raggiungibile a {url}: avviarlo con python -m note_api") from None


def servizio_raggiungibile(url: str) -> bool:
    """Vero se `GET /salute` risponde."""
    try:
        return _richiesta(url, "GET", "/salute").get("stato") == "ok"
    except ToolException:
        return False


def formatta_nota(nota: dict, fuso: ZoneInfo) -> str:
    """«n. 3 (9/11/2026 10:15) testo», con la data nel fuso dato."""
    d = datetime.fromisoformat(nota["creata"]).astimezone(fuso)
    return f"n. {nota['numero']} ({d.day}/{d.month}/{d.year} {d:%H:%M}) {nota['testo']}"


def crea_strumenti_note(url: str, fuso: ZoneInfo) -> list[BaseTool]:
    """Crea `salva_nota`, `elenca_note` e `cancella_nota`, che chiamano il servizio all'indirizzo `url`."""

    def salva_nota(testo: Annotated[str, DESCRIZIONE_TESTO]) -> str:
        nota = _richiesta(url, "POST", "/note", {"testo": testo})
        return f"nota {nota['numero']} salvata: «{nota['testo']}»"

    def elenca_note(cerca: Annotated[str | None, DESCRIZIONE_CERCA] = None) -> str:
        cerca = cerca.strip() if cerca and cerca.strip() else None
        percorso = "/note" + ("?" + urlencode({"cerca": cerca}) if cerca else "")
        risposta = _richiesta(url, "GET", percorso)
        totale, note = risposta["totale"], risposta["note"]
        if totale == 0:
            return f"nessuna nota contiene «{cerca}»" if cerca else "nessuna nota"
        testo = ("1 nota: " if totale == 1 else f"{totale} note: ") + "; ".join(
            formatta_nota(n, fuso) for n in note
        )
        if totale > len(note):
            testo += f" (mostrate le {len(note)} più recenti su {totale})"
        return testo

    def cancella_nota(numero: Annotated[int, DESCRIZIONE_NUMERO]) -> str:
        nota = _richiesta(url, "DELETE", f"/note/{quote(str(numero))}")
        return f"nota {nota['numero']} cancellata: «{nota['testo']}»"

    return [
        StructuredTool.from_function(
            func=salva_nota, name="salva_nota", description=DESCRIZIONE_SALVA,
            handle_validation_error=_rifiuta("argomenti non validi: serve testo, il testo della nota (1–500 caratteri)"),
        ),
        StructuredTool.from_function(
            func=elenca_note, name="elenca_note", description=DESCRIZIONE_ELENCA,
            handle_validation_error=_rifiuta(
                "argomenti non validi: cerca è facoltativo e deve essere un testo (omettere per tutte le note)"
            ),
        ),
        StructuredTool.from_function(
            func=cancella_nota, name="cancella_nota", description=DESCRIZIONE_CANCELLA,
            handle_validation_error=_rifiuta(
                "argomenti non validi: serve numero, il numero intero della nota, per esempio 3"
            ),
        ),
    ]
