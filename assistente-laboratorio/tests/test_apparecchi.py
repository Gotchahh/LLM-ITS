import json
from pathlib import Path

import pytest

from catalogo_mcp.apparecchi import ErroreCatalogo, carica, cerca, dettaglio, elenca, riga

DATI = carica(Path(__file__).resolve().parent.parent / "catalogo_mcp" / "apparecchi.json")


def per_codice(codice):
    return next(a for a in DATI if a["codice"] == codice)


def test_riga():
    assert riga(per_codice("MIC-02")) == (
        "MIC-02 Microscopio ottico 2 (microscopio) — stanza B12, in manutenzione, calibrato il 10/03/2026"
    )


def test_cerca():
    risultato = cerca(DATI, "CENTRIFUGA")
    assert "CEN-01" in risultato and "CEN-02" in risultato and "stanza A03" in risultato
    assert "MIC-02" in cerca(DATI, "obiettivo")
    assert cerca(DATI, "xyz") == "nessun apparecchio corrisponde a «xyz»"
    with pytest.raises(ErroreCatalogo, match="testo"):
        cerca(DATI, "  ")


def test_dettaglio():
    testo = dettaglio(DATI, "mic-02")
    assert testo.startswith("MIC-02 Microscopio ottico 2")
    assert "ultima calibrazione: 10/03/2026" in testo and "note: obiettivo 40x da sostituire" in testo
    with pytest.raises(ErroreCatalogo) as errore:
        dettaglio(DATI, "XYZ-99")
    assert str(errore.value) == "nessun apparecchio con codice «XYZ-99»"


def test_elenca():
    assert elenca(DATI, stato="In Manutenzione").split("\n") == [riga(per_codice("MIC-02")), riga(per_codice("PHM-01"))]
    assert [r.split()[0] for r in elenca(DATI, stanza=" b12 ").split("\n")] == ["MIC-01", "MIC-02"]
    assert elenca(DATI, stanza="A01", stato="in uso") == "nessun apparecchio nella stanza «A01» con stato «in uso»"
    assert len(elenca(DATI).split("\n")) == 10
    with pytest.raises(ErroreCatalogo) as errore:
        elenca(DATI, stato="rotto")
    for stato in ["disponibile", "in uso", "in manutenzione", "fuori servizio"]:
        assert stato in str(errore.value)


@pytest.mark.parametrize("contenuto", [
    "{ non è json",
    json.dumps([{"codice": "X-1", "nome": "x", "tipo": "x", "stanza": "A", "stato": "rotto",
                 "ultima_calibrazione": "2026-01-01"}]),
    json.dumps([{"codice": "X-1"}]),
])
def test_file_non_valido(tmp_path, contenuto):
    percorso = tmp_path / "rotto.json"
    percorso.write_text(contenuto, encoding="utf-8")
    with pytest.raises(ErroreCatalogo, match="rotto.json"):
        carica(percorso)
