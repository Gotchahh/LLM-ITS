"""Test dello strumento orologio: formato, cambio d'ora, istante fornito e fuso richiesto."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from assistente.strumenti import crea_strumento_orologio, formatta_ora

ROMA = ZoneInfo("Europe/Rome")
ISTANTE = datetime(2026, 10, 28, 8, 56, tzinfo=UTC)  # mercoledì: Roma UTC+1, New York UTC-4
orologio = crea_strumento_orologio(ROMA, adesso=lambda: ISTANTE)


def test_formato_con_giorno_e_offset():
    assert formatta_ora(datetime(2026, 10, 26, 15, 42, 10, tzinfo=UTC), ROMA) == \
        "lunedì 2026-10-26T16:42:10+01:00 (Europe/Rome)"


@pytest.mark.parametrize("utc, atteso", [
    (datetime(2026, 10, 24, 22, 0, tzinfo=UTC), "domenica 2026-10-25T00:00:00+02:00 (Europe/Rome)"),
    (datetime(2026, 10, 25, 2, 0, tzinfo=UTC), "domenica 2026-10-25T03:00:00+01:00 (Europe/Rome)")])
def test_cambio_ora_legale(utc, atteso):
    assert formatta_ora(utc, ROMA) == atteso


def test_altro_fuso():
    assert formatta_ora(datetime(2026, 10, 26, 15, 42, 10, tzinfo=UTC), ZoneInfo("America/New_York")) == \
        "lunedì 2026-10-26T11:42:10-04:00 (America/New_York)"


def test_strumento_usa_l_istante_fornito():
    s = crea_strumento_orologio(ROMA, adesso=lambda: datetime(2026, 10, 26, 15, 42, 10, tzinfo=UTC))
    assert s.name == "ora_corrente" and set(s.args) == {"fuso"}
    assert s.invoke({}) == "lunedì 2026-10-26T16:42:10+01:00 (Europe/Rome)"


def test_parametro_fuso_facoltativo_e_descritto():
    assert "IANA" in orologio.args["fuso"]["description"]
    assert "fuso" not in orologio.tool_call_schema.model_json_schema().get("required", [])


@pytest.mark.parametrize("argomenti, atteso", [
    ({}, "mercoledì 2026-10-28T09:56:00+01:00 (Europe/Rome)"),
    ({"fuso": None}, "mercoledì 2026-10-28T09:56:00+01:00 (Europe/Rome)"),
    ({"fuso": ""}, "mercoledì 2026-10-28T09:56:00+01:00 (Europe/Rome)"),
    ({"fuso": "  "}, "mercoledì 2026-10-28T09:56:00+01:00 (Europe/Rome)"),
    ({"fuso": "America/New_York"}, "mercoledì 2026-10-28T04:56:00-04:00 (America/New_York)"),
    ({"fuso": "Asia/Tokyo"}, "mercoledì 2026-10-28T17:56:00+09:00 (Asia/Tokyo)"),
])
def test_ora_nel_fuso_richiesto(argomenti, atteso):
    assert orologio.invoke(argomenti) == atteso


@pytest.mark.parametrize("fuso", ["New York", "Europa/Roma", "../Europe/Rome"])
def test_fuso_non_valido_restituisce_un_errore(fuso):
    assert orologio.invoke({"fuso": fuso}) == \
        f"Errore: fuso orario sconosciuto «{fuso}»: serve un nome IANA, per esempio America/New_York"


def test_fuso_non_testuale_restituisce_un_errore():
    assert orologio.invoke({"fuso": 5}) == \
        "Errore: il fuso orario deve essere un nome IANA, per esempio America/New_York"
