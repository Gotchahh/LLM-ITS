"""Logica pura del catalogo: lettura e controllo dei dati, ricerca, dettaglio, elenco filtrato."""

import json
from datetime import date
from pathlib import Path

STATI = ("disponibile", "in uso", "in manutenzione", "fuori servizio")
CAMPI = ("codice", "nome", "tipo", "stanza", "stato", "ultima_calibrazione")


class ErroreCatalogo(Exception):
    """Richiesta impossibile o file del catalogo non valido; il messaggio è in italiano."""


def _normale(testo: str) -> str:
    return " ".join(testo.split()).casefold()


def _data(testo: str) -> str:
    return date.fromisoformat(testo).strftime("%d/%m/%Y")


def carica(percorso: Path) -> list[dict]:
    """Legge il catalogo e controlla campi, stati e date; altrimenti ErroreCatalogo con il nome del file."""
    try:
        apparecchi = json.loads(Path(percorso).read_text(encoding="utf-8"))
    except (OSError, ValueError) as errore:
        raise ErroreCatalogo(f"catalogo {percorso} non leggibile: {errore}") from None
    if not isinstance(apparecchi, list):
        raise ErroreCatalogo(f"catalogo {percorso} non valido: serve un elenco di apparecchi")
    for a in apparecchi:
        codice = a.get("codice", "?") if isinstance(a, dict) else "?"
        if not isinstance(a, dict) or any(not isinstance(a.get(c), str) or not a[c].strip() for c in CAMPI):
            raise ErroreCatalogo(
                f"catalogo {percorso} non valido: all'apparecchio {codice} manca un campo tra {', '.join(CAMPI)}"
            )
        if a["stato"] not in STATI:
            raise ErroreCatalogo(f"catalogo {percorso} non valido: stato «{a['stato']}» di {codice} non ammesso")
        try:
            _data(a["ultima_calibrazione"])
        except ValueError:
            raise ErroreCatalogo(
                f"catalogo {percorso} non valido: data di {codice} non nel formato AAAA-MM-GG"
            ) from None
    return apparecchi


def riga(a: dict) -> str:
    """«MIC-02 Microscopio ottico 2 (microscopio) — stanza B12, in manutenzione, calibrato il 10/03/2026»."""
    return (
        f"{a['codice']} {a['nome']} ({a['tipo']}) — stanza {a['stanza']}, {a['stato']}, "
        f"calibrato il {_data(a['ultima_calibrazione'])}"
    )


def cerca(apparecchi: list[dict], testo: str) -> str:
    """Apparecchi con `testo` in codice, nome, tipo o note, senza distinzione di maiuscole."""
    chiave = _normale(testo)
    if not chiave:
        raise ErroreCatalogo("serve un testo da cercare, per esempio centrifuga o MIC-02")
    trovati = [
        a for a in apparecchi
        if any(chiave in _normale(a.get(campo, "")) for campo in ("codice", "nome", "tipo", "note"))
    ]
    if not trovati:
        return f"nessun apparecchio corrisponde a «{testo.strip()}»"
    return "\n".join(riga(a) for a in trovati)


def dettaglio(apparecchi: list[dict], codice: str) -> str:
    """Tutti i campi dell'apparecchio con il codice dato (senza distinzione di maiuscole)."""
    for a in apparecchi:
        if _normale(a["codice"]) == _normale(codice):
            righe = [
                f"{a['codice']} {a['nome']}",
                f"tipo: {a['tipo']}",
                f"stanza: {a['stanza']}",
                f"stato: {a['stato']}",
                f"ultima calibrazione: {_data(a['ultima_calibrazione'])}",
            ]
            if a.get("note"):
                righe.append(f"note: {a['note']}")
            return "\n".join(righe)
    raise ErroreCatalogo(f"nessun apparecchio con codice «{codice.strip()}»")


def elenca(apparecchi: list[dict], stanza: str | None = None, stato: str | None = None) -> str:
    """Apparecchi filtrati per stanza e stato (facoltativi, senza distinzione di maiuscole)."""
    stanza = _normale(stanza) if stanza and stanza.strip() else None
    stato = _normale(stato) if stato and stato.strip() else None
    if stato is not None and stato not in STATI:
        raise ErroreCatalogo(f"stato «{stato}» non ammesso; stati possibili: {', '.join(STATI)}")
    trovati = [
        a for a in apparecchi
        if (stanza is None or _normale(a["stanza"]) == stanza) and (stato is None or a["stato"] == stato)
    ]
    if trovati:
        return "\n".join(riga(a) for a in trovati)
    filtri = []
    if stanza is not None:
        filtri.append(f"nella stanza «{stanza.upper()}»")
    if stato is not None:
        filtri.append(f"con stato «{stato}»")
    return " ".join(["nessun apparecchio", *filtri])
