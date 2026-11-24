"""Prompt MCP scelti dall'utente: lettura e controllo del comando `/prompt`, testo di `/prompts`, righe di log.

Modulo sincrono e senza MCP: l'elenco dei prompt e la funzione che chiede il testo al server arrivano come
argomenti. L'host controlla solo nomi e presenza degli argomenti; i valori li controlla il server.
"""

import json
import logging
import re
import time
from collections.abc import Callable, Sequence

from assistente.client_mcp import DefinizionePrompt, ErroreMCP

logger = logging.getLogger(__name__)

# Nome del prompt: una parola senza «=» né virgolette, seguita da uno spazio o dalla fine della riga.
NOME = re.compile(r'([^\s="]+)(?=\s|$)')
# Una coppia: spazi, nome=valore; valore tra virgolette doppie (non vuoto) o una parola senza virgolette.
# Gli apostrofi restano parte del valore (`argomento=l'entropia`).
COPPIA = re.compile(r'\s+([^\s="]+)=(?:"([^"]+)"|([^\s"]+))(?=\s|$)')

RIGA_NON_VALIDA = (
    "riga non valida. Scrivi /prompt nome argomento=valore (virgolette doppie per i valori con spazi)."
)
SUGGERIMENTO = " Scrivi /prompts per l'elenco."


class ErrorePrompt(Exception):
    """Richiesta `/prompt` sbagliata: il messaggio, in italiano, va dopo «Errore: »."""


def leggi_comando(resto: str) -> tuple[str, dict[str, str]]:
    """Nome del prompt e argomenti dalla riga dopo `/prompt` (`nome arg=valore arg="valore con spazi"`)."""
    testo = resto.strip()
    trovato = NOME.match(testo)
    if trovato is None:
        raise ErrorePrompt(RIGA_NON_VALIDA)
    nome, posizione = trovato.group(1), trovato.end()
    argomenti: dict[str, str] = {}
    while posizione < len(testo):
        coppia = COPPIA.match(testo, posizione)
        if coppia is None:
            raise ErrorePrompt(RIGA_NON_VALIDA)
        chiave = coppia.group(1)
        if chiave in argomenti:
            raise ErrorePrompt(f"l'argomento {chiave} è ripetuto.")
        argomenti[chiave] = coppia.group(2) if coppia.group(2) is not None else coppia.group(3)
        posizione = coppia.end()
    return nome, argomenti


def controlla(nome: str, argomenti: dict[str, str], elenco: Sequence[DefinizionePrompt]) -> None:
    """Controlla nome e argomenti rispetto all'elenco del server; `ErrorePrompt` al primo problema."""
    definizione = next((p for p in elenco if p.nome == nome), None)
    if definizione is None:
        raise ErrorePrompt(f"il prompt {nome} non esiste." + SUGGERIMENTO)
    for argomento in definizione.argomenti:
        if argomento.obbligatorio and argomento.nome not in argomenti:
            raise ErrorePrompt(f"al prompt {nome} manca l'argomento obbligatorio {argomento.nome}." + SUGGERIMENTO)
    ammessi = {a.nome for a in definizione.argomenti}
    for chiave in argomenti:
        if chiave not in ammessi:
            raise ErrorePrompt(f"il prompt {nome} non ha l'argomento {chiave}." + SUGGERIMENTO)


def righe_elenco(elenco: Sequence[DefinizionePrompt]) -> list[str]:
    """Il testo di `/prompts`: firma e descrizione di ogni prompt (facoltativi tra parentesi quadre), poi le
    descrizioni degli argomenti, se il server le dà."""
    righe = []
    for prompt in elenco:
        firma = ", ".join(a.nome if a.obbligatorio else f"[{a.nome}]" for a in prompt.argomenti)
        righe.append(f"{prompt.nome}({firma}): {prompt.descrizione}")
        descritti = [f"{a.nome}: {a.descrizione}" for a in prompt.argomenti if a.descrizione]
        if descritti:
            righe.append("  " + "; ".join(descritti))
    return righe


def carica_prompt(leggi: Callable[[], list[DefinizionePrompt]]) -> list[DefinizionePrompt] | None:
    """Legge l'elenco all'avvio e scrive la riga di log; `None` (comandi disattivati) se il server non risponde."""
    inizio = time.perf_counter()
    try:
        elenco = leggi()
    except ErroreMCP as errore:
        logger.warning("prompt: elenco non disponibile (%s), comandi /prompt disattivati", errore)
        return None
    nomi = ", ".join(f"{p.nome}({', '.join(a.nome for a in p.argomenti)})" for p in elenco)
    logger.info("prompt: elenco letto in %.1f s: %s", time.perf_counter() - inizio, nomi)
    return elenco


def compila_prompt(
    resto: str,
    elenco: Sequence[DefinizionePrompt],
    richiedi: Callable[[str, dict[str, str]], str],
) -> str:
    """Legge e controlla la riga dopo `/prompt`, chiede il testo al server e lo restituisce.

    Una richiesta sbagliata solleva `ErrorePrompt` senza chiamare `richiedi`; gli errori di `richiedi`
    (`ErroreMCP`) passano.
    """
    nome, argomenti = leggi_comando(resto)
    controlla(nome, argomenti, elenco)
    testo = richiedi(nome, argomenti)
    logger.info(
        "prompt: %s %s -> «%s»", nome, json.dumps(argomenti, ensure_ascii=False), " ".join(testo.splitlines())
    )
    return testo
