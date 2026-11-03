"""Test della logica della calcolatrice: risultati, formato, errori e assenza di esecuzione di codice."""

import re
from pathlib import Path

import pytest

from calcolatrice_mcp import calcolo
from calcolatrice_mcp.calcolo import ErroreCalcolo, calcola

SINTASSI = "sintassi non valida"
NON_AMMESSO = "elemento non ammesso: sono permessi solo numeri, + - * / // % ** e parentesi"
VIRGOLA = "la virgola non è ammessa: per i decimali usa il punto, per esempio 2.5"
POTENZA = "il simbolo ^ non è ammesso: per le potenze usa **, per esempio 2**3"
ZERO = "divisione per zero"
ESPONENTE = "esponente troppo grande (massimo 100 in valore assoluto)"
GRANDE = "numero troppo grande (massimo 10**100 in valore assoluto)"


@pytest.mark.parametrize("espressione, atteso", [
    ("2+3*4", "14"), ("(2+3)*4", "20"), ("-2**2", "-4"), ("2**-1", "0.5"), ("--3", "3"),
    ("0.1+0.2", "0.3"), ("1/3", "0.333333333333333"), ("7/2", "3.5"), ("4/2", "2"), ("1e3", "1000"),
    ("-7//2", "-4"), ("-7%3", "2"), ("7.5%2", "1.5"), ("2**10", "1024"), ("12.5*8-3", "97"),
    ("-0.0", "0"), ("10**100", "1" + "0" * 100), ("  2+2\n", "4"),
    ("(" * 99 + "1" + ")" * 99, "1"), ("-" * 199 + "1", "-1"),
])
def test_calcoli_validi(espressione, atteso):
    assert calcola(espressione) == atteso


@pytest.mark.parametrize("espressione, messaggio", [
    ("", "espressione vuota"), ("   ", "espressione vuota"),
    ("1" * 201, "espressione troppo lunga (massimo 200 caratteri)"),
    ("2+", SINTASSI), ("(2", SINTASSI), ("2 3", SINTASSI), ("2×3", SINTASSI),
    ("__import__('os')", NON_AMMESSO), ("().__class__", NON_AMMESSO), ("x", NON_AMMESSO),
    ("abs(-1)", NON_AMMESSO), ("[1, 2]", NON_AMMESSO), ("'a'*3", NON_AMMESSO), ("1<2", NON_AMMESSO),
    ("True+1", NON_AMMESSO), ("2j", NON_AMMESSO),
    ("2,5", VIRGOLA), ("1.000,50", VIRGOLA), ("2^3", POTENZA),
    ("1/0", ZERO), ("1//0", ZERO), ("1%0", ZERO), ("0**-1", ZERO),
    ("9**9**9", ESPONENTE), ("2**101", ESPONENTE),
    ("10**100*10", GRANDE), ("1e308*10", GRANDE), ("1" + "0" * 101, GRANDE),
    ("(-8)**0.5", "il risultato non è un numero reale"),
])
def test_errori(espressione, messaggio):
    with pytest.raises(ErroreCalcolo) as errore:
        calcola(espressione)
    assert str(errore.value) == messaggio


def test_il_modulo_non_esegue_codice():
    sorgente = Path(calcolo.__file__).read_text(encoding="utf-8")
    assert not re.search(r"\b(eval|exec|compile)\s*\(", sorgente)
