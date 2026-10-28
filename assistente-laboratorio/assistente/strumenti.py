"""Strumento orologio: data, giorno della settimana e ora nel fuso orario configurato."""

from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from langchain_core.tools import BaseTool, StructuredTool

GIORNI = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")
DESCRIZIONE = (
    "Restituisce data, giorno della settimana e ora correnti nel fuso orario configurato; "
    "da usare per ogni domanda su ora, data o giorno attuali"
)


def formatta_ora(istante: datetime, fuso: ZoneInfo) -> str:
    """Formatta `istante` nel fuso dato: giorno della settimana, data e ora ISO con offset."""
    d = istante.astimezone(fuso)
    return f"{GIORNI[d.weekday()]} {d.isoformat(timespec='seconds')} ({fuso.key})"


def crea_strumento_orologio(
    fuso: ZoneInfo,
    adesso: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> BaseTool:
    """Crea lo strumento `ora_corrente`, senza parametri, che legge l'istante da `adesso`."""

    def ora_corrente() -> str:
        return formatta_ora(adesso(), fuso)

    return StructuredTool.from_function(
        func=ora_corrente,
        name="ora_corrente",
        description=DESCRIZIONE,
    )
