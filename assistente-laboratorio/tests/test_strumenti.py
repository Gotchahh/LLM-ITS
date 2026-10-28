"""Test dello strumento orologio: formato, cambio d'ora e uso dell'istante fornito."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from assistente.strumenti import crea_strumento_orologio, formatta_ora

ROMA = ZoneInfo("Europe/Rome")


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
    assert s.name == "ora_corrente" and s.args == {}
    assert s.invoke({}) == "lunedì 2026-10-26T16:42:10+01:00 (Europe/Rome)"
