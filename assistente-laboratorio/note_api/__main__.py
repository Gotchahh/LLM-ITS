"""Avvio del servizio: `python -m note_api` (variabili NOTE_DB, NOTE_HOST, NOTE_PORT)."""

import os
from pathlib import Path

import uvicorn

from note_api.server import crea_app


def main() -> None:
    uvicorn.run(
        crea_app(Path(os.environ.get("NOTE_DB") or "dati/note.db")),
        host=os.environ.get("NOTE_HOST") or "127.0.0.1",
        port=int(os.environ.get("NOTE_PORT") or "8000"),
    )


if __name__ == "__main__":
    main()
