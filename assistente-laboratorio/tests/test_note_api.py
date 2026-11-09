import pytest
from fastapi.testclient import TestClient

from note_api.server import crea_app


@pytest.fixture
def client(tmp_path):
    return TestClient(crea_app(tmp_path / "note.db"))


def salva(client, testo):
    return client.post("/note", json={"testo": testo})


def test_salute(client):
    risposta = client.get("/salute")
    assert risposta.status_code == 200 and risposta.json() == {"stato": "ok"}


def test_salva_ed_elenca(client):
    risposta = salva(client, "  calibrare il microscopio 2 ")
    assert risposta.status_code == 201
    nota = risposta.json()
    assert nota["testo"] == "calibrare il microscopio 2" and nota["numero"] == 1
    assert nota["creata"].endswith("+00:00")
    assert client.get("/note").json() == {"totale": 1, "note": [nota]}


def test_ordine_e_limite(client):
    for i in range(1, 26):
        salva(client, f"nota {i}")
    elenco = client.get("/note").json()
    assert elenco["totale"] == 25 and len(elenco["note"]) == 20
    assert elenco["note"][0]["numero"] == 25


@pytest.mark.parametrize("cerca, quante", [("microscopio", 1), ("PERCHÉ", 1), ("xyz", 0)])
def test_ricerca(client, cerca, quante):
    for testo in ["Microscopio da calibrare", "perché no", "centrifuga"]:
        salva(client, testo)
    elenco = client.get("/note", params={"cerca": cerca}).json()
    assert elenco["totale"] == quante and len(elenco["note"]) == quante


def test_cancella(client):
    nota = salva(client, "da cancellare").json()
    risposta = client.delete("/note/1")
    assert risposta.status_code == 200 and risposta.json() == nota
    di_nuovo = client.delete("/note/1")
    assert di_nuovo.status_code == 404 and di_nuovo.json() == {"errore": "nessuna nota con numero 1"}
    assert salva(client, "dopo").json()["numero"] == 2


@pytest.mark.parametrize("corpo", [{"testo": "   "}, {"testo": "x" * 501}, {}, {"testo": 5}])
def test_testo_non_valido(client, corpo):
    risposta = client.post("/note", json=corpo)
    assert risposta.status_code == 400
    assert set(risposta.json()) == {"errore"} and "testo" in risposta.json()["errore"]
    assert "Field required" not in risposta.text and "detail" not in risposta.text


def test_numero_non_intero_e_percorso_sconosciuto(client):
    risposta = client.delete("/note/tre")
    assert risposta.status_code == 400 and "numero" in risposta.json()["errore"]
    sconosciuto = client.get("/inesistente")
    assert sconosciuto.status_code == 404 and set(sconosciuto.json()) == {"errore"}


def test_persistenza(tmp_path):
    salva(TestClient(crea_app(tmp_path / "note.db")), "resta")
    elenco = TestClient(crea_app(tmp_path / "note.db")).get("/note").json()
    assert [n["testo"] for n in elenco["note"]] == ["resta"]
