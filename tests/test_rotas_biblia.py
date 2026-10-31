import re

import pytest
from fastapi.testclient import TestClient

from mana.web.app import app
from mana.web.rotas import repositorio_biblia


@pytest.fixture
def cliente(repo):
    app.dependency_overrides[repositorio_biblia] = lambda: repo
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_lista_de_livros(cliente):
    r = cliente.get("/biblia")
    assert r.status_code == 200
    assert r.text.count('class="pilula"') == 66
    assert "Antigo Testamento" in r.text and "Novo Testamento" in r.text


def test_capitulo_com_credito_e_versiculos(cliente):
    r = cliente.get("/biblia/romanos/8")
    assert r.status_code == 200
    assert '<span class="versiculo" id="v28"><sup>28</sup>E sabemos' in r.text
    assert "Bíblia Livre (BLIVRE)" in r.text and "Creative Commons Atribuição 4.0" in r.text
    assert 'lang="pt-BR"' in r.text


def test_destaque_de_faixa(cliente):
    r = cliente.get("/biblia/romanos/5?destacar=3-4")
    destacados = re.findall(r'class="versiculo destacado" id="v(\d+)"', r.text)
    assert destacados == ["3", "4"]
    assert "destacado" not in cliente.get("/biblia/romanos/5?destacar=lixo").text.split("<h1>")[1]


def test_navegacao_entre_capitulos_e_livros(cliente):
    meio = cliente.get("/biblia/romanos/8").text
    assert 'href="/biblia/romanos/7" rel="prev"' in meio
    assert 'href="/biblia/romanos/9" rel="next"' in meio
    fim = cliente.get("/biblia/malaquias/4").text
    assert 'href="/biblia/mateus/1" rel="next"' in fim
    inicio = cliente.get("/biblia/mateus/1").text
    assert 'href="/biblia/malaquias/4" rel="prev"' in inicio
    assert 'rel="prev"' not in cliente.get("/biblia/genesis/1").text
    assert 'rel="next"' not in cliente.get("/biblia/apocalipse/22").text


def test_404_em_html_para_capitulo_ou_livro_inexistente(cliente):
    for url in ("/biblia/romanos/17", "/biblia/romanos/0", "/biblia/inexistente/1", "/nada"):
        r = cliente.get(url)
        assert r.status_code == 404, url
        assert "text/html" in r.headers["content-type"]
        assert "Não encontrado" in r.text


def test_404_da_api_continua_json(cliente):
    r = cliente.get("/api/passagem", params={"ref": "rom.8.99"})
    assert r.status_code == 404 and r.json() == {"detail": "Passagem não encontrada"}


def test_livro_sem_capitulo_redireciona(cliente):
    r = cliente.get("/biblia/romanos", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "/biblia/romanos/1"


def test_seletor_sem_javascript(cliente):
    r = cliente.get("/biblia/ir?livro=romanos&cap=8", follow_redirects=False)
    assert r.headers["location"] == "/biblia/romanos/8"
    r = cliente.get("/biblia/ir?livro=judas&cap=9", follow_redirects=False)
    assert r.headers["location"] == "/biblia/judas/1"
    assert (
        cliente.get("/biblia/ir?livro=xx", follow_redirects=False).headers["location"] == "/biblia"
    )


def test_busca(cliente):
    r = cliente.get("/biblia/busca", params={"q": "esperanca"})
    assert r.status_code == 200
    assert "<mark>" in r.text and "resultados" in r.text
    assert "destacar=" in r.text
    assert 'href="/biblia/busca?q=esperanca&amp;p=2"' in r.text


def test_busca_vazia_e_sem_resultado(cliente):
    assert cliente.get("/biblia/busca").status_code == 200
    r = cliente.get("/biblia/busca", params={"q": "zzzzqqqq"})
    assert "Nenhum versículo encontrado" in r.text


def test_busca_nao_quebra_com_sintaxe_fts_nem_html(cliente):
    for q in ['"', "AND OR", "a*", "<script>", "-"]:
        assert cliente.get("/biblia/busca", params={"q": q}).status_code == 200
    assert "<script>" not in cliente.get("/biblia/busca", params={"q": "<script>"}).text.replace(
        '<script src="', ""
    )


def test_arquivos_estaticos(cliente):
    for caminho in (
        "/static/css/tema.css",
        "/static/css/fontes.css",
        "/static/js/ref-popover.js",
        "/static/fonts/nunito-800-latin.woff2",
        "/static/img/logo-mana.svg",
    ):
        assert cliente.get(caminho).status_code == 200, caminho
