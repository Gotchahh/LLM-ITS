"""Strumenti del calendario: giorni tra date, date spostate, giorno della settimana e Pasqua.

«Oggi» viene dallo stesso orologio di `ora_corrente`, nel fuso configurato, con istante iniettabile nei test.
"""

import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from langchain_core.tools import BaseTool, StructuredTool, ToolException

from assistente.strumenti import GIORNI

MESI = (
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
)
CON_ANNO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SENZA_ANNO = re.compile(r"^\d{2}-\d{2}$")
ANNI_DI_RICERCA = 8  # il 29 febbraio può mancare per otto anni (per esempio dal 2097 al 2104)

ERRORE_INTERVALLO = "anno fuori dall'intervallo 1–9999"
ERRORE_PASQUA = (
    "la data di Pasqua si calcola solo dal 1583, dopo l'introduzione del calendario gregoriano"
)
FORMATI = "usare 2026-12-25 oppure 12-25 se l'anno non c'è"

DESCRIZIONE_DATA = (
    "Data nel formato AAAA-MM-GG, per esempio 2026-12-25, oppure MM-GG, per esempio 12-25, "
    "se l'anno non è indicato (vale la prossima occorrenza, oggi compreso)"
)
DESCRIZIONE_PARTENZA = "Data di partenza, AAAA-MM-GG oppure MM-GG; omettere per oggi"
DESCRIZIONE_DATA_PARTENZA = "Data da cui contare, AAAA-MM-GG oppure MM-GG; omettere per oggi"
DESCRIZIONE_GIORNI = "Numero intero di giorni: positivo per il futuro, negativo per il passato"
DESCRIZIONE_ANNO = "Anno, per esempio 2027; omettere per l'anno corrente"

DESCRIZIONE_GIORNI_TRA = (
    "Conta i giorni che mancano a una data o che sono passati da essa, oppure i giorni tra due date; "
    "da usare per ogni domanda su quanti giorni mancano, sono passati o ci sono tra due date"
)
DESCRIZIONE_SPOSTA_DATA = (
    "Restituisce la data che cade N giorni dopo (o prima, con N negativo) di oggi o di una data; "
    "da usare per domande come «che giorno sarà tra 30 giorni» o «che data era 10 giorni fa»"
)
DESCRIZIONE_GIORNO_SETTIMANA = (
    "Restituisce il giorno della settimana di una data; da usare per domande come «che giorno della "
    "settimana è il 25 dicembre»"
)
DESCRIZIONE_PASQUA = (
    "Restituisce la data della Pasqua (cattolica) di un anno, dal 1583 in poi; "
    "da usare per ogni domanda su quando cade Pasqua"
)


def formatta_data(d: date) -> str:
    """«venerdì 25 dicembre 2026»."""
    return f"{GIORNI[d.weekday()]} {d.day} {MESI[d.month - 1]} {d.year}"


def _giorni(n: int) -> str:
    return "1 giorno" if n == 1 else f"{n} giorni"


def leggi_data(testo: str, oggi: date) -> date:
    """Legge `AAAA-MM-GG` o `MM-GG` (prossima occorrenza da `oggi`, oggi compreso); altrimenti ToolException."""
    pulito = testo.strip()
    if CON_ANNO.match(pulito):
        anno, mese, giorno = (int(parte) for parte in pulito.split("-"))
        if anno < 1:
            raise ToolException(ERRORE_INTERVALLO)
        try:
            return date(anno, mese, giorno)
        except ValueError:
            raise ToolException(f"data non valida «{pulito}»") from None
    if SENZA_ANNO.match(pulito):
        mese, giorno = (int(parte) for parte in pulito.split("-"))
        for anno in range(oggi.year, oggi.year + ANNI_DI_RICERCA + 1):
            if anno > 9999:
                raise ToolException(ERRORE_INTERVALLO)
            try:
                candidata = date(anno, mese, giorno)
            except ValueError:
                continue
            if candidata >= oggi:
                return candidata
        raise ToolException(f"data non valida «{pulito}»")
    raise ToolException(f"formato di data non riconosciuto «{pulito}»: {FORMATI}")


def data_di_pasqua(anno: int) -> date:
    """Pasqua gregoriana (algoritmo anonimo, Meeus/Jones/Butcher)."""
    if not 1 <= anno <= 9999:
        raise ToolException(ERRORE_INTERVALLO)
    if anno < 1583:
        raise ToolException(ERRORE_PASQUA)
    a = anno % 19
    b, c = divmod(anno, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741 (nome dell'algoritmo)
    m = (a + 11 * h + 22 * l) // 451
    mese, giorno = divmod(h + l - 7 * m + 114, 31)
    return date(anno, mese, giorno + 1)


def _assente(testo: str | None) -> bool:
    """Una data facoltativa mancante, nulla o vuota vale oggi (come il fuso di `ora_corrente`)."""
    return testo is None or not testo.strip()


def giorni_tra(data: str, partenza: str | None, oggi: date) -> str:
    """Giorni da `partenza` (oggi se manca) a `data`: «mancano N giorni», «sono passati N giorni», «è oggi»."""
    partenza = None if _assente(partenza) else partenza
    arrivo = leggi_data(data, oggi)
    inizio = oggi if partenza is None else leggi_data(partenza, oggi)
    differenza = (arrivo - inizio).days
    if differenza == 0 and partenza is None:
        return f"{formatta_data(arrivo)}: è oggi"
    prefisso = f"da {formatta_data(inizio)} a {formatta_data(arrivo)}: "
    if differenza == 0:
        return prefisso + "0 giorni"
    if differenza > 0:
        return prefisso + ("manca " if differenza == 1 else "mancano ") + _giorni(differenza)
    return prefisso + ("è passato " if differenza == -1 else "sono passati ") + _giorni(-differenza)


def sposta_data(giorni: int, data: str | None, oggi: date) -> str:
    """La data `giorni` giorni dopo (o prima) di `data` (oggi se manca)."""
    data = None if _assente(data) else data
    inizio = oggi if data is None else leggi_data(data, oggi)
    try:
        arrivo = inizio + timedelta(days=giorni)
    except OverflowError:
        raise ToolException(ERRORE_INTERVALLO) from None
    if data is None:
        if giorni == 0:
            return f"oggi: {formatta_data(arrivo)}"
        if giorni > 0:
            return f"tra {_giorni(giorni)}: {formatta_data(arrivo)}"
        return f"{_giorni(-giorni)} fa: {formatta_data(arrivo)}"
    if giorni >= 0:
        return f"{_giorni(giorni)} dopo {formatta_data(inizio)}: {formatta_data(arrivo)}"
    return f"{_giorni(-giorni)} prima di {formatta_data(inizio)}: {formatta_data(arrivo)}"


def giorno_settimana(data: str, oggi: date) -> str:
    """La data per esteso, con il giorno della settimana."""
    return formatta_data(leggi_data(data, oggi))


def pasqua(anno: int | None, oggi: date) -> str:
    """«Pasqua 2027: domenica 28 marzo 2027»; senza anno, quella dell'anno corrente."""
    anno = oggi.year if anno is None else anno
    return f"Pasqua {anno}: {formatta_data(data_di_pasqua(anno))}"


def _rifiuta(messaggio: str) -> Callable[[object], str]:
    """Argomenti mancanti o del tipo sbagliato: ToolException in italiano, senza la traccia di validazione."""

    def rifiuta(_errore) -> str:
        raise ToolException(messaggio)

    return rifiuta


def crea_strumenti_calendario(
    fuso: ZoneInfo,
    adesso: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> list[BaseTool]:
    """Crea `giorni_tra`, `sposta_data`, `giorno_settimana` e `pasqua`; «oggi» è la data di `adesso()` in `fuso`."""

    def oggi() -> date:
        return adesso().astimezone(fuso).date()

    def strumento_giorni_tra(
        data: Annotated[str, DESCRIZIONE_DATA],
        partenza: Annotated[str | None, DESCRIZIONE_PARTENZA] = None,
    ) -> str:
        return giorni_tra(data, partenza, oggi())

    def strumento_sposta_data(
        giorni: Annotated[int, DESCRIZIONE_GIORNI],
        data: Annotated[str | None, DESCRIZIONE_DATA_PARTENZA] = None,
    ) -> str:
        return sposta_data(giorni, data, oggi())

    def strumento_giorno_settimana(data: Annotated[str, DESCRIZIONE_DATA]) -> str:
        return giorno_settimana(data, oggi())

    def strumento_pasqua(anno: Annotated[int | None, DESCRIZIONE_ANNO] = None) -> str:
        return pasqua(anno, oggi())

    return [
        StructuredTool.from_function(
            func=strumento_giorni_tra,
            name="giorni_tra",
            description=DESCRIZIONE_GIORNI_TRA,
            handle_validation_error=_rifiuta(
                "argomenti non validi: servono data (testo AAAA-MM-GG o MM-GG, per esempio 2026-12-25 o 12-25) "
                "e, se serve, partenza (stesso formato; omettere per oggi)"
            ),
        ),
        StructuredTool.from_function(
            func=strumento_sposta_data,
            name="sposta_data",
            description=DESCRIZIONE_SPOSTA_DATA,
            handle_validation_error=_rifiuta(
                "argomenti non validi: servono giorni (un numero intero, per esempio 30 o -10, senza decimali) "
                "e, se serve, data (testo AAAA-MM-GG o MM-GG; omettere per oggi)"
            ),
        ),
        StructuredTool.from_function(
            func=strumento_giorno_settimana,
            name="giorno_settimana",
            description=DESCRIZIONE_GIORNO_SETTIMANA,
            handle_validation_error=_rifiuta(
                "argomenti non validi: serve data (testo AAAA-MM-GG o MM-GG, per esempio 2026-12-25 o 12-25)"
            ),
        ),
        StructuredTool.from_function(
            func=strumento_pasqua,
            name="pasqua",
            description=DESCRIZIONE_PASQUA,
            handle_validation_error=_rifiuta(
                "argomenti non validi: anno deve essere un numero intero, per esempio 2027 (omettere per l'anno "
                "corrente)"
            ),
        ),
    ]
