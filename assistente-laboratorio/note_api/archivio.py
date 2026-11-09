"""Archivio SQLite delle note: una connessione per operazione, perché uvicorn usa thread diversi."""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = (
    "CREATE TABLE IF NOT EXISTS note ("
    "numero INTEGER PRIMARY KEY AUTOINCREMENT, testo TEXT NOT NULL, creata TEXT NOT NULL)"
)


def _nota(riga: sqlite3.Row) -> dict:
    return {"numero": riga["numero"], "testo": riga["testo"], "creata": riga["creata"]}


class ArchivioNote:
    """Note salvate nel file `percorso`; cartella e tabella create se mancano."""

    def __init__(self, percorso: Path):
        self.percorso = Path(percorso)
        self.percorso.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connetti()) as connessione, connessione:
            connessione.execute(SCHEMA)

    def _connetti(self) -> sqlite3.Connection:
        connessione = sqlite3.connect(self.percorso)
        connessione.row_factory = sqlite3.Row
        return connessione

    def salva(self, testo: str) -> dict:
        creata = datetime.now(UTC).isoformat(timespec="seconds")
        with closing(self._connetti()) as connessione, connessione:
            cursore = connessione.execute("INSERT INTO note (testo, creata) VALUES (?, ?)", (testo, creata))
            return {"numero": cursore.lastrowid, "testo": testo, "creata": creata}

    def elenca(self, cerca: str | None = None, limite: int = 20) -> tuple[int, list[dict]]:
        """Totale e note, dalla più recente; `cerca` senza distinzione di maiuscole (anche accentate)."""
        with closing(self._connetti()) as connessione:
            righe = connessione.execute("SELECT * FROM note ORDER BY numero DESC").fetchall()
        note = [_nota(r) for r in righe]
        if cerca:
            chiave = cerca.casefold()
            note = [n for n in note if chiave in n["testo"].casefold()]
        return len(note), note[:limite]

    def cancella(self, numero: int) -> dict | None:
        with closing(self._connetti()) as connessione, connessione:
            riga = connessione.execute("SELECT * FROM note WHERE numero = ?", (numero,)).fetchone()
            if riga is None:
                return None
            connessione.execute("DELETE FROM note WHERE numero = ?", (numero,))
            return _nota(riga)
