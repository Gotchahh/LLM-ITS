"""Strumento orologio: data, giorno della settimana e ora nel fuso orario configurato o richiesto."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import BaseTool, StructuredTool

GIORNI = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")
DESCRIZIONE = (
    "Restituisce data, giorno della settimana e ora correnti: senza argomenti nel fuso orario "
    "configurato, con fuso nel fuso orario di un'altra località; "
    "da usare per ogni domanda su ora, data o giorno attuali"
)
DESCRIZIONE_FUSO = (
    "Nome IANA del fuso orario della località richiesta, per esempio America/New_York o Asia/Tokyo; "
    "omettere per il fuso orario configurato"
)
ERRORE_FUSO = "Errore: fuso orario sconosciuto «{}»: serve un nome IANA, per esempio America/New_York"
ERRORE_FUSO_NON_TESTO = "Errore: il fuso orario deve essere un nome IANA, per esempio America/New_York"


def formatta_ora(istante: datetime, fuso: ZoneInfo) -> str:
    """Formatta `istante` nel fuso dato: giorno della settimana, data e ora ISO con offset."""
    d = istante.astimezone(fuso)
    return f"{GIORNI[d.weekday()]} {d.isoformat(timespec='seconds')} ({fuso.key})"


def crea_strumento_orologio(
    fuso: ZoneInfo,
    adesso: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> BaseTool:
    """Crea lo strumento `ora_corrente`, che legge l'istante da `adesso`.

    Il parametro `fuso` è facoltativo: se manca, è nullo o vuoto vale il fuso configurato.
    Un fuso richiesto e non valido produce un testo d'errore, non un'eccezione.
    """

    configurato = fuso  # il parametro dello strumento si chiama `fuso` e lo nasconde

    def ora_corrente(fuso: Annotated[str | None, DESCRIZIONE_FUSO] = None) -> str:
        if fuso is None or not fuso.strip():
            return formatta_ora(adesso(), configurato)
        try:
            richiesto = ZoneInfo(fuso.strip())
        except (ZoneInfoNotFoundError, ValueError, OSError):
            return ERRORE_FUSO.format(fuso)
        return formatta_ora(adesso(), richiesto)

    return StructuredTool.from_function(
        func=ora_corrente,
        name="ora_corrente",
        description=DESCRIZIONE,
        handle_validation_error=ERRORE_FUSO_NON_TESTO,
    )
