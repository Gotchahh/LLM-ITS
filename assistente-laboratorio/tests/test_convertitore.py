import pytest
from langchain_core.tools import ToolException

from assistente.convertitore import converti, crea_strumento_convertitore, formatta_numero


@pytest.mark.parametrize("valore, da, a, atteso", [
    (2, "cm", "m", "2 cm = 0,02 m"),
    (4, "centimetri", "metri", "4 cm = 0,04 m"),
    (25, "m", "km", "25 m = 0,025 km"),
    (1, "mi", "m", "1 mi = 1609,34 m"),
    (1, "pollice", "cm", "1 in = 2,54 cm"),
    (1, "piede", "pollici", "1 ft = 12 in"),
    (1, "mm", "m", "1 mm = 0,001 m"),
    (1, "lb", "kg", "1 lb = 0,453592 kg"),
    (16, "once", "libbre", "16 oz = 1 lb"),
    (1, "t", "kg", "1 t = 1000 kg"),
    (1, "mg", "g", "1 mg = 0,001 g"),
    (1, "chili", "grammi", "1 kg = 1000 g"),
    (20, "°C", "°F", "20 °C = 68 °F"),
    (0, "celsius", "kelvin", "0 °C = 273,15 K"),
    (-40, "C", "F", "-40 °C = -40 °F"),
    (0, "K", "°C", "0 K = -273,15 °C"),
    (-459.67, "fahrenheit", "K", "-459,67 °F = 0 K"),
    (2.5, "m", "m", "2,5 m = 2,5 m"),
    (1234567, "m", "km", "1234567 m = 1234,57 km"),
])
def test_conversioni(valore, da, a, atteso):
    assert converti(valore, da, a) == atteso


def test_nomi_senza_maiuscole_e_spazi():
    assert converti(1, " KM ", "M") == "1 km = 1000 m"
    assert converti(20, " Gradi  Celsius ", "°f") == "20 °C = 68 °F"


def test_mai_notazione_esponenziale():
    assert converti(1, "mg", "t") == "1 mg = 0,000000001 t"
    assert converti(1000, "mi", "mm") == "1000 mi = 1609340000 mm"
    assert converti(0.000001, "km", "m") == "0,000001 km = 0,001 m"


def test_formatta_numero():
    assert formatta_numero(-0.0) == "0"
    assert formatta_numero(0.1 + 0.2, 6) == "0,3"
    assert formatta_numero(-1e-12, 6) == "-0,000000000001"
    assert formatta_numero(1609.344, 6) == "1609,34"


def messaggio_d_errore(valore, da, a):
    with pytest.raises(ToolException) as errore:
        converti(valore, da, a)
    return str(errore.value)


def test_grandezze_diverse():
    messaggio = messaggio_d_errore(5, "kg", "m")
    assert "peso" in messaggio and "lunghezza" in messaggio
    messaggio = messaggio_d_errore(5, "°C", "g")
    assert "temperatura" in messaggio and "peso" in messaggio


@pytest.mark.parametrize("da, a", [("m", "iarde"), ("iarde", "m")])
def test_unita_sconosciuta(da, a):
    messaggio = messaggio_d_errore(10, da, a)
    assert "«iarde»" in messaggio
    assert all(simbolo in messaggio for simbolo in ("km", "lb", "°F"))


@pytest.mark.parametrize("valore, da", [(-300, "°C"), (-1, "K"), (-500, "°F")])
def test_sotto_lo_zero_assoluto(valore, da):
    messaggio = messaggio_d_errore(valore, da, "°C" if da == "K" else "K")
    assert "zero assoluto" in messaggio and "-273,15 °C" in messaggio


def test_peso_o_lunghezza_negativi():
    messaggio = messaggio_d_errore(-5, "kg", "g")
    assert "peso" in messaggio and "negativo" in messaggio
    messaggio = messaggio_d_errore(-1, "m", "cm")
    assert "lunghezza" in messaggio and "negativ" in messaggio
    assert converti(0, "kg", "g") == "0 kg = 0 g"


@pytest.mark.parametrize("valore", [float("inf"), float("nan")])
def test_valore_non_finito(valore):
    assert "numero" in messaggio_d_errore(valore, "m", "km")


def test_strumento():
    strumento = crea_strumento_convertitore()
    assert strumento.name == "converti"
    assert set(strumento.args) == {"valore", "da", "a"}
    assert strumento.invoke({"valore": 2, "da": "cm", "a": "m"}) == "2 cm = 0,02 m"
    with pytest.raises(ToolException) as errore:
        strumento.invoke({"valore": "tanti", "da": "m", "a": "km"})
    assert "numero" in str(errore.value) and "validation" not in str(errore.value).lower()
