import logging
from pathlib import Path

import pytest
from conftest import VALIDO

from assistente.config import (
    ErroreConfigurazione,
    ModalitaLog,
    carica_configurazione,
    configura_log,
    leggi_ambito,
    leggi_revisore,
    leggi_riassunto,
    leggi_file_env,
)


@pytest.fixture
def log_isolati():
    """Salva e ripristina handler e livelli della radice e del logger `assistente`."""
    radice = logging.getLogger()
    app = logging.getLogger("assistente")
    handler_radice, livello_radice = radice.handlers[:], radice.level
    handler_app, livello_app = app.handlers[:], app.level
    yield
    radice.handlers[:] = handler_radice
    radice.setLevel(livello_radice)
    app.handlers[:] = handler_app
    app.setLevel(livello_app)


def test_configurazione_valida():
    c = carica_configurazione(VALIDO)
    assert (c.base_url, c.modello, c.fuso.key, c.livello_log) == (
        "http://localhost:1234/v1", "google/gemma-4-e4b", "Europe/Rome", "INFO")


def test_ambiente_vuoto_nomina_variabili_e_file_di_esempio():          # Review Focus 3
    with pytest.raises(ErroreConfigurazione) as e:
        carica_configurazione({})
    for atteso in ("LMSTUDIO_BASE_URL", "LMSTUDIO_MODEL", "APP_TIMEZONE", ".env.example"):
        assert atteso in str(e.value)


def test_modello_vuoto_e_mancante():
    with pytest.raises(ErroreConfigurazione, match="LMSTUDIO_MODEL"):
        carica_configurazione({**VALIDO, "LMSTUDIO_MODEL": "  "})


def test_url_senza_schema_rifiutato():
    with pytest.raises(ErroreConfigurazione, match="LMSTUDIO_BASE_URL"):
        carica_configurazione({**VALIDO, "LMSTUDIO_BASE_URL": "localhost:1234/v1"})


def test_url_con_barra_finale_normalizzato():                          # Review Focus 4
    assert carica_configurazione({**VALIDO, "LMSTUDIO_BASE_URL": "http://localhost:1234/v1/"}).base_url \
        == "http://localhost:1234/v1"


def test_fuso_non_valido():
    with pytest.raises(ErroreConfigurazione, match="APP_TIMEZONE"):
        carica_configurazione({**VALIDO, "APP_TIMEZONE": "Roma"})


def test_livello_log_minuscolo_accettato():                            # Review Focus 5
    assert carica_configurazione({**VALIDO, "LOG_LEVEL": "info"}).livello_log == "INFO"


def test_livello_log_non_valido():
    with pytest.raises(ErroreConfigurazione, match="LOG_LEVEL"):
        carica_configurazione({**VALIDO, "LOG_LEVEL": "TANTO"})


def test_file_env_con_bom_e_crlf(tmp_path):
    f = tmp_path / ".env"
    f.write_bytes("\ufeffLMSTUDIO_MODEL=google/gemma-4-e4b\r\nAPP_TIMEZONE=Europe/Rome\r\n".encode("utf-8"))
    assert leggi_file_env(f) == {"LMSTUDIO_MODEL": "google/gemma-4-e4b", "APP_TIMEZONE": "Europe/Rome"}


def test_file_env_assente(tmp_path):
    assert leggi_file_env(tmp_path / "manca.env") == {}


@pytest.mark.parametrize("contenuto", ["LMSTUDIO_MODEL=x\n".encode("utf-16"), b"LMSTUDIO_MODEL=caff\xe8\n"],
                         ids=["utf-16", "cp1252"])
def test_file_env_non_utf8_errore_chiaro(tmp_path, contenuto):
    # Il redirect `>` di PowerShell 5.1 scrive UTF-16: senza questo controllo si avrebbe un traceback.
    f = tmp_path / ".env"
    f.write_bytes(contenuto)
    with pytest.raises(ErroreConfigurazione, match=r"\.env non è in UTF-8"):
        leggi_file_env(f)


@pytest.mark.parametrize("url", ["http://[::1/v1", "http://[abc]:1234/v1"])
def test_url_con_parentesi_quadre_errate_rifiutato(url):
    with pytest.raises(ErroreConfigurazione, match="LMSTUDIO_BASE_URL"):
        carica_configurazione({**VALIDO, "LMSTUDIO_BASE_URL": url})


def test_log_esterni_restano_a_warning(log_isolati):
    configura_log("INFO")
    assert logging.getLogger("assistente.grafo").isEnabledFor(logging.INFO)
    assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)


def test_modalita_silenziosa(log_isolati):
    configura_log("INFO")
    configura_log("WARNING")
    assert not logging.getLogger("assistente.grafo").isEnabledFor(logging.INFO)


@pytest.mark.parametrize("iniziale, visibili, dopo_uno, dopo_due", [
    ("DEBUG", True, "WARNING", "DEBUG"),
    ("INFO", True, "WARNING", "INFO"),
    ("WARNING", False, "INFO", "WARNING"),
    ("ERROR", False, "INFO", "ERROR"),
])
def test_modalita_log_alterna_e_torna_al_livello_d_avvio(log_isolati, iniziale, visibili, dopo_uno, dopo_due):
    configura_log(iniziale)
    modalita = ModalitaLog(iniziale)
    assert modalita.visibili is visibili
    assert modalita.alterna() is (not visibili)
    assert logging.getLevelName(logging.getLogger("assistente").level) == dopo_uno
    assert modalita.alterna() is visibili
    assert logging.getLevelName(logging.getLogger("assistente").level) == dopo_due


def test_modalita_log_non_tocca_i_logger_alla_creazione(log_isolati):
    configura_log("DEBUG")
    ModalitaLog("INFO")
    assert logging.getLogger("assistente").level == logging.DEBUG


def test_modalita_log_tocca_solo_i_log_dell_applicazione(log_isolati):
    configura_log("WARNING")
    ModalitaLog("WARNING").alterna()
    assert logging.getLogger("assistente.grafo").isEnabledFor(logging.INFO)
    assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)


def test_indirizzo_delle_note():
    assert carica_configurazione(VALIDO).note_url == "http://localhost:8000"
    assert carica_configurazione({**VALIDO, "NOTE_API_URL": " "}).note_url == "http://localhost:8000"
    assert carica_configurazione({**VALIDO, "NOTE_API_URL": "http://note:8000/"}).note_url == "http://note:8000"
    with pytest.raises(ErroreConfigurazione, match="NOTE_API_URL"):
        carica_configurazione({**VALIDO, "NOTE_API_URL": "note:8000"})


def test_file_dell_ambito():
    assert carica_configurazione(VALIDO).ambito_file == Path("ambito.txt")
    assert carica_configurazione({**VALIDO, "AMBITO_FILE": " "}).ambito_file == Path("ambito.txt")
    assert carica_configurazione({**VALIDO, "AMBITO_FILE": " altro.txt "}).ambito_file == Path("altro.txt")


def test_leggi_ambito(tmp_path):
    valido = tmp_path / "ambito.txt"
    valido.write_text("  testo \n", encoding="utf-8")
    assert leggi_ambito(valido) == "testo"


@pytest.mark.parametrize("contenuto", [None, "   \n", "utf16"])
def test_leggi_ambito_non_valido(tmp_path, contenuto):
    percorso = tmp_path / "ambito.txt"
    if contenuto == "utf16":
        percorso.write_text("ambito", encoding="utf-16")
    elif contenuto is not None:
        percorso.write_text(contenuto, encoding="utf-8")
    with pytest.raises(ErroreConfigurazione) as errore:
        leggi_ambito(percorso)
    assert "AMBITO_FILE" in str(errore.value) and "ambito.txt" in str(errore.value)


def test_ambito_del_progetto():
    testo = leggi_ambito(Path(__file__).resolve().parent.parent / "ambito.txt")
    assert "laboratorio" in testo and "fuori_ambito" in testo and "conversazione" in testo


def test_configurazione_del_revisore():
    c = carica_configurazione(VALIDO)
    assert (c.revisore_file, c.revisioni_max) == (Path("revisore.txt"), 2)
    assert carica_configurazione({**VALIDO, "REVISORE_FILE": " r.txt "}).revisore_file == Path("r.txt")
    assert carica_configurazione({**VALIDO, "REVISIONI_MAX": "0"}).revisioni_max == 0
    assert carica_configurazione({**VALIDO, "REVISIONI_MAX": " 3 "}).revisioni_max == 3


@pytest.mark.parametrize("valore", ["due", "-1", "1.5"])
def test_revisioni_max_non_valido(valore):
    with pytest.raises(ErroreConfigurazione, match="REVISIONI_MAX"):
        carica_configurazione({**VALIDO, "REVISIONI_MAX": valore})


@pytest.mark.parametrize("contenuto", [None, "  \n"])
def test_leggi_revisore_non_valido(tmp_path, contenuto):
    percorso = tmp_path / "revisore.txt"
    if contenuto is not None:
        percorso.write_text(contenuto, encoding="utf-8")
    with pytest.raises(ErroreConfigurazione) as errore:
        leggi_revisore(percorso)
    assert "REVISORE_FILE" in str(errore.value) and "revisore" in str(errore.value)


def test_revisore_del_progetto():
    assert "coerente" in leggi_revisore(Path(__file__).resolve().parent.parent / "revisore.txt")


def test_configurazione_del_riassunto():
    c = carica_configurazione(VALIDO)
    assert (c.riassunto_file, c.riassunto_soglia, c.riassunto_turni) == (Path("riassunto.txt"), 20, 2)
    assert carica_configurazione({**VALIDO, "RIASSUNTO_FILE": " r.txt "}).riassunto_file == Path("r.txt")
    assert carica_configurazione({**VALIDO, "RIASSUNTO_SOGLIA": " 6 "}).riassunto_soglia == 6
    assert carica_configurazione({**VALIDO, "RIASSUNTO_TURNI": "1"}).riassunto_turni == 1


@pytest.mark.parametrize(
    "variabile, valore",
    [
        ("RIASSUNTO_SOGLIA", "0"),
        ("RIASSUNTO_SOGLIA", "-3"),
        ("RIASSUNTO_SOGLIA", "venti"),
        ("RIASSUNTO_TURNI", "0"),
        ("RIASSUNTO_TURNI", "due"),
    ],
)
def test_riassunto_intero_non_valido(variabile, valore):                     # Review Focus 5
    with pytest.raises(ErroreConfigurazione, match=variabile):
        carica_configurazione({**VALIDO, variabile: valore})


@pytest.mark.parametrize("contenuto", [None, "  \n"])
def test_leggi_riassunto_non_valido(tmp_path, contenuto):
    percorso = tmp_path / "riassunto.txt"
    if contenuto is not None:
        percorso.write_text(contenuto, encoding="utf-8")
    with pytest.raises(ErroreConfigurazione) as errore:
        leggi_riassunto(percorso)
    assert "RIASSUNTO_FILE" in str(errore.value) and "riassunto" in str(errore.value)


def test_riassunto_del_progetto():
    assert "nome" in leggi_riassunto(Path(__file__).resolve().parent.parent / "riassunto.txt")


def test_il_revisore_non_giudica_la_lingua():
    istruzioni = leggi_revisore(Path(__file__).resolve().parent.parent / "revisore.txt")
    assert "La lingua della risposta non è mai un motivo per coerente=false" in istruzioni


def test_preferenze_json_del_progetto_valido(caplog):
    from zoneinfo import ZoneInfo

    from assistente.preferenze import Preferenze, leggi_preferenze

    testo = (Path(__file__).resolve().parent.parent / "preferenze.json").read_text(encoding="utf-8")
    assert leggi_preferenze(testo, ZoneInfo("UTC")) == Preferenze("italiano", ZoneInfo("Europe/Rome"), "sintetico")
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
