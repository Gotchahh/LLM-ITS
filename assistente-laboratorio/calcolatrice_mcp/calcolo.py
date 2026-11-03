"""Calcolo sicuro: legge l'espressione con `ast` e la valuta solo con operazioni ammesse, senza eseguire codice."""

import ast
import math
import operator

LUNGHEZZA_MASSIMA = 200
ESPONENTE_MASSIMO = 100
VALORE_MASSIMO = 10**100

VUOTA = "espressione vuota"
TROPPO_LUNGA = "espressione troppo lunga (massimo 200 caratteri)"
SINTASSI = "sintassi non valida"
NON_AMMESSO = "elemento non ammesso: sono permessi solo numeri, + - * / // % ** e parentesi"
VIRGOLA = "la virgola non è ammessa: per i decimali usa il punto, per esempio 2.5"
POTENZA = "il simbolo ^ non è ammesso: per le potenze usa **, per esempio 2**3"
DIVISIONE_PER_ZERO = "divisione per zero"
ESPONENTE_GRANDE = "esponente troppo grande (massimo 100 in valore assoluto)"
NUMERO_GRANDE = "numero troppo grande (massimo 10**100 in valore assoluto)"
NON_REALE = "il risultato non è un numero reale"

OPERAZIONI_BINARIE = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
OPERAZIONI_UNARIE = {ast.UAdd: operator.pos, ast.USub: operator.neg}


class ErroreCalcolo(ValueError):
    """Espressione non calcolabile: il messaggio, in italiano, dice che cosa correggere."""


def verifica(valore: object) -> int | float:
    """Restituisce `valore` se è un numero reale finito entro `VALORE_MASSIMO`, altrimenti solleva l'errore."""
    if isinstance(valore, complex):
        raise ErroreCalcolo(NON_REALE)
    if isinstance(valore, float) and not math.isfinite(valore):
        raise ErroreCalcolo(NUMERO_GRANDE)
    if abs(valore) > VALORE_MASSIMO:
        raise ErroreCalcolo(NUMERO_GRANDE)
    return valore


def valuta_operazione(nodo: ast.BinOp) -> int | float:
    """Valuta un'operazione binaria; la potenza controlla l'esponente prima di calcolare."""
    sinistra = valuta(nodo.left)
    destra = valuta(nodo.right)
    if isinstance(nodo.op, ast.Pow) and abs(destra) > ESPONENTE_MASSIMO:
        raise ErroreCalcolo(ESPONENTE_GRANDE)
    try:
        risultato = OPERAZIONI_BINARIE[type(nodo.op)](sinistra, destra)
    except ZeroDivisionError:
        raise ErroreCalcolo(DIVISIONE_PER_ZERO) from None
    except OverflowError:
        raise ErroreCalcolo(NUMERO_GRANDE) from None
    return verifica(risultato)


def valuta(nodo: ast.AST) -> int | float:
    """Valuta ricorsivamente un nodo: accetta solo numeri, operatori ammessi e segni."""
    if isinstance(nodo, ast.Constant):
        if type(nodo.value) not in (int, float):  # esclude bool, complessi, testo, None
            raise ErroreCalcolo(NON_AMMESSO)
        return verifica(nodo.value)
    if isinstance(nodo, ast.Tuple):
        raise ErroreCalcolo(VIRGOLA)
    if isinstance(nodo, ast.UnaryOp) and type(nodo.op) in OPERAZIONI_UNARIE:
        return OPERAZIONI_UNARIE[type(nodo.op)](valuta(nodo.operand))  # il segno non cambia il valore assoluto
    if isinstance(nodo, ast.BinOp):
        if isinstance(nodo.op, ast.BitXor):
            raise ErroreCalcolo(POTENZA)
        if type(nodo.op) in OPERAZIONI_BINARIE:
            return valuta_operazione(nodo)
    raise ErroreCalcolo(NON_AMMESSO)


def formatta(valore: int | float) -> str:
    """Interi esatti; decimali con al massimo 15 cifre significative; `-0` reso come `0`."""
    if isinstance(valore, int):
        return str(valore)
    testo = format(valore, ".15g")
    return "0" if testo == "-0" else testo


def calcola(espressione: str) -> str:
    """Calcola `espressione` e restituisce il risultato come testo; solleva `ErroreCalcolo` se non è calcolabile."""
    testo = espressione.strip()
    if not testo:
        raise ErroreCalcolo(VUOTA)
    if len(testo) > LUNGHEZZA_MASSIMA:
        raise ErroreCalcolo(TROPPO_LUNGA)
    try:
        albero = ast.parse(testo, mode="eval")
    except (SyntaxError, ValueError):
        raise ErroreCalcolo(SINTASSI) from None
    return formatta(valuta(albero.body))
