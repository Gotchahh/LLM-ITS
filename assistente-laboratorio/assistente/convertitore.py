"""Strumento convertitore: lunghezze, pesi e temperature, con risultato in formato italiano."""

import math
from decimal import Decimal
from typing import Annotated

from langchain_core.tools import BaseTool, StructuredTool, ToolException

CIFRE_SIGNIFICATIVE = 6
ZERO_ASSOLUTO_C = 273.15

# simbolo -> (grandezza, fattore verso l'unità base: m, kg; None per le temperature), nomi accettati
UNITA = {
    "mm": ("lunghezza", 0.001, ("millimetro", "millimetri")),
    "cm": ("lunghezza", 0.01, ("centimetro", "centimetri")),
    "m": ("lunghezza", 1.0, ("metro", "metri")),
    "km": ("lunghezza", 1000.0, ("chilometro", "chilometri")),
    "in": ("lunghezza", 0.0254, ("pollice", "pollici")),
    "ft": ("lunghezza", 0.3048, ("piede", "piedi")),
    "mi": ("lunghezza", 1609.344, ("miglio", "miglia")),
    "mg": ("peso", 0.000001, ("milligrammo", "milligrammi")),
    "g": ("peso", 0.001, ("grammo", "grammi")),
    "kg": ("peso", 1.0, ("chilogrammo", "chilogrammi", "chilo", "chili")),
    "t": ("peso", 1000.0, ("tonnellata", "tonnellate")),
    "lb": ("peso", 0.45359237, ("libbra", "libbre")),
    "oz": ("peso", 0.028349523125, ("oncia", "once")),
    "°C": ("temperatura", None, ("c", "celsius", "gradi celsius")),
    "°F": ("temperatura", None, ("f", "fahrenheit", "gradi fahrenheit")),
    "K": ("temperatura", None, ("kelvin",)),
}
NOMI = {nome: simbolo for simbolo, (_, _, nomi) in UNITA.items() for nome in (simbolo.lower(), *nomi)}
ARTICOLI = {"lunghezza": "una lunghezza", "peso": "un peso", "temperatura": "una temperatura"}
ELENCO = (
    "lunghezze mm, cm, m, km, in, ft, mi; pesi mg, g, kg, t, lb, oz; temperature °C, °F, K"
)

DESCRIZIONE = (
    "Converte un valore tra due unità della stessa grandezza e restituisce il risultato già formattato: "
    f"{ELENCO}; da usare per ogni domanda di conversione tra unità"
)
DESCRIZIONE_VALORE = "Il numero da convertire, per esempio 25 o 2.5"
DESCRIZIONE_DA = "Unità di partenza: simbolo o nome italiano, per esempio cm, centimetri, °C, libbre"
DESCRIZIONE_A = "Unità di arrivo: simbolo o nome italiano, per esempio m, metri, °F, kg"
ERRORE_NUMERO = "il valore da convertire deve essere un numero, per esempio 25 o 2.5"
ERRORE_ARGOMENTI = (
    "argomenti non validi: servono valore (un numero, per esempio 25 o 2.5), "
    "da e a (le unità come testo, per esempio cm e m)"
)


def formatta_numero(x: float, cifre: int | None = None) -> str:
    """Notazione decimale ordinaria con la virgola, senza zeri finali inutili né `-0`.

    Con `cifre` arrotonda a quel numero di cifre significative; senza, riporta il numero com'è.
    """
    testo = format(x, f".{cifre}g") if cifre is not None else repr(float(x))
    testo = format(Decimal(testo), "f")
    if "." in testo:
        testo = testo.rstrip("0").rstrip(".")
    if testo == "-0":
        testo = "0"
    return testo.replace(".", ",")


def _unita(testo: str) -> str:
    """Simbolo dell'unità scritta in `testo`, o ToolException se non è nell'elenco."""
    simbolo = NOMI.get(" ".join(testo.split()).lower())
    if simbolo is None:
        raise ToolException(f"unità non supportata «{testo.strip()}»; unità disponibili: {ELENCO}")
    return simbolo


def _in_kelvin(valore: float, simbolo: str) -> float:
    if simbolo == "°C":
        return valore + ZERO_ASSOLUTO_C
    if simbolo == "°F":
        return (valore - 32) * 5 / 9 + ZERO_ASSOLUTO_C
    return valore


def _da_kelvin(kelvin: float, simbolo: str) -> float:
    if simbolo == "°C":
        return kelvin - ZERO_ASSOLUTO_C
    if simbolo == "°F":
        return (kelvin - ZERO_ASSOLUTO_C) * 9 / 5 + 32
    return kelvin


def converti(valore: float, da: str, a: str) -> str:
    """Converte `valore` dall'unità `da` all'unità `a`: «<valore> <da> = <risultato> <a>».

    Solleva ToolException (messaggio in italiano) se un'unità è sconosciuta, se le grandezze sono
    diverse, se il valore non è un numero finito, se un peso o una lunghezza sono negativi o se una
    temperatura è sotto lo zero assoluto.
    """
    origine, destinazione = _unita(da), _unita(a)
    grandezza, fattore_da, _ = UNITA[origine]
    grandezza_a, fattore_a, _ = UNITA[destinazione]
    if grandezza != grandezza_a:
        raise ToolException(
            f"non si può convertire {ARTICOLI[grandezza]} ({origine}) in {ARTICOLI[grandezza_a]} ({destinazione})"
        )
    if not math.isfinite(valore):
        raise ToolException(ERRORE_NUMERO)
    if grandezza == "temperatura":
        kelvin = _in_kelvin(valore, origine)
        if kelvin < -1e-9:
            raise ToolException(
                f"temperatura impossibile: {formatta_numero(valore)} {origine} è sotto lo zero assoluto "
                f"(-273,15 °C)"
            )
        risultato = round(_da_kelvin(max(kelvin, 0.0), destinazione), 10)
    else:
        if valore < 0:
            negativo = "negativo" if grandezza == "peso" else "negativa"
            raise ToolException(f"{ARTICOLI[grandezza]} non può essere {negativo}")
        risultato = valore * fattore_da / fattore_a
    if not math.isfinite(risultato):
        raise ToolException("il risultato è troppo grande per essere rappresentato")
    return (
        f"{formatta_numero(valore)} {origine} = "
        f"{formatta_numero(risultato, CIFRE_SIGNIFICATIVE)} {destinazione}"
    )


def _rifiuta_valore(_errore) -> str:
    """Argomenti mancanti o del tipo sbagliato: ToolException in italiano, senza la traccia di validazione."""
    raise ToolException(ERRORE_ARGOMENTI)


def crea_strumento_convertitore() -> BaseTool:
    """Crea lo strumento `converti`."""

    def converti_unita(
        valore: Annotated[float, DESCRIZIONE_VALORE],
        da: Annotated[str, DESCRIZIONE_DA],
        a: Annotated[str, DESCRIZIONE_A],
    ) -> str:
        return converti(valore, da, a)

    return StructuredTool.from_function(
        func=converti_unita,
        name="converti",
        description=DESCRIZIONE,
        handle_validation_error=_rifiuta_valore,
    )
