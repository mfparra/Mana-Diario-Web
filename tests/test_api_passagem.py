import pytest
from fastapi.testclient import TestClient

from mana.web.app import app
from mana.web.rotas import repositorio_biblia


@pytest.fixture
def cliente(repo):
    app.dependency_overrides[repositorio_biblia] = lambda: repo
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_passagem_canonica(cliente):
    r = cliente.get("/api/passagem", params={"ref": "rom.8.28"})
    assert r.status_code == 200
    d = r.json()
    assert d["referencia"] == "Romanos 8.28"
    assert d["url"] == "/biblia/romanos/8#v28"
    assert d["edicao"] == "BLIVRE"
    assert d["versiculos"][0]["numero"] == 28
    assert d["versiculos"][0]["texto"].startswith("E sabemos que todas as coisas")


def test_passagem_forma_de_exibicao_e_intervalo(cliente):
    d = cliente.get("/api/passagem", params={"ref": "Rm 5:3,4"}).json()
    assert [v["numero"] for v in d["versiculos"]] == [3, 4]
    assert d["referencia"] == "Romanos 5.3,4"


def test_passagem_entre_capitulos(cliente):
    d = cliente.get("/api/passagem", params={"ref": "gen.1.31-2.2"}).json()
    assert [(v["capitulo"], v["numero"]) for v in d["versiculos"]] == [(1, 31), (2, 1), (2, 2)]


def test_ref_invalida_400(cliente):
    assert cliente.get("/api/passagem", params={"ref": "lixo"}).status_code == 400
    assert cliente.get("/api/passagem").status_code == 422


def test_ref_inexistente_404(cliente):
    assert cliente.get("/api/passagem", params={"ref": "rom.8.99"}).status_code == 404


def test_passagem_longa_demais(cliente):
    assert cliente.get("/api/passagem", params={"ref": "psa.1-150"}).status_code == 400
