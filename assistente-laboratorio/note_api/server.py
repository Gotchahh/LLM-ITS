"""API HTTP delle note; ogni errore ha il corpo {"errore": "<messaggio in italiano>"}."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from note_api.archivio import ArchivioNote

LUNGHEZZA_MASSIMA = 500
ERRORE_TESTO = f"il testo della nota deve avere da 1 a {LUNGHEZZA_MASSIMA} caratteri"
ERRORE_NUMERO = "il numero della nota deve essere un numero intero, per esempio 3"


class NuovaNota(BaseModel):
    testo: str


def errore(stato: int, messaggio: str) -> JSONResponse:
    return JSONResponse(status_code=stato, content={"errore": messaggio})


def crea_app(percorso_db: Path) -> FastAPI:
    """App FastAPI con le note salvate in `percorso_db`."""
    archivio = ArchivioNote(percorso_db)
    app = FastAPI(title="Note del laboratorio")

    @app.exception_handler(RequestValidationError)
    def richiesta_non_valida(_richiesta: Request, eccezione: RequestValidationError) -> JSONResponse:
        campi = {str(e["loc"][-1]) for e in eccezione.errors() if e.get("loc")}
        if "numero" in campi:
            return errore(400, f"richiesta non valida: {ERRORE_NUMERO}")
        return errore(400, f"richiesta non valida: {ERRORE_TESTO}")

    @app.exception_handler(StarletteHTTPException)
    def errore_http(_richiesta: Request, eccezione: StarletteHTTPException) -> JSONResponse:
        if eccezione.status_code == 404:
            return errore(404, "percorso inesistente")
        return errore(eccezione.status_code, f"richiesta non accettata ({eccezione.status_code})")

    @app.get("/salute")
    def salute() -> dict:
        return {"stato": "ok"}

    @app.post("/note", status_code=201)
    def salva(nota: NuovaNota):
        testo = nota.testo.strip()
        if not 1 <= len(testo) <= LUNGHEZZA_MASSIMA:
            return errore(400, ERRORE_TESTO)
        return archivio.salva(testo)

    @app.get("/note")
    def elenca(cerca: str | None = None) -> dict:
        totale, note = archivio.elenca(cerca.strip() if cerca else None)
        return {"totale": totale, "note": note}

    @app.delete("/note/{numero}")
    def cancella(numero: int):
        nota = archivio.cancella(numero)
        if nota is None:
            return errore(404, f"nessuna nota con numero {numero}")
        return nota

    return app
