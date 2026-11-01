from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from mana import tempo
from mana.estudos.modelos import Estudo
from mana.estudos.repositorio import LinhaCalendario, RepositorioEstudos
from mana.web.app import app
from mana.web.rotas import repositorio_biblia, repositorio_estudos

HOJE = date(2026, 11, 3)


def estudo(data, ref="rom.8.28", **sobre):
    base = dict(
        data=data, status="ok", ref=ref, titulo=f"Título de {data.day}",
        frase_do_dia="Uma frase para o dia que resume a lição.",
        paragrafos=[
            "Primeiro, veja Filipenses 4.6 & pense.",
            "Segundo parágrafo com <b>marca</b>.",
        ],
        complementar="psa.23.1-2", palavras_chave=["paz", "cuidado"], modelo="m",
        gerado_em=datetime(2026, 11, 1, 6),
    )  # fmt: skip
    return Estudo(**{**base, **sobre})


@pytest.fixture
def estudos(tmp_path):
    repo = RepositorioEstudos(tmp_path / "mana.sqlite")
    repo.gravar(
        [LinhaCalendario(date(2026, 11, d), "rom.8.28") for d in range(1, 7)]
        + [LinhaCalendario(date(2026, 12, 25), "isa.7.14", "natal")]
    )
    for d in (1, 2, 3, 4, 5):  # 4 e 5 são futuros
        repo.gravar_estudo(estudo(date(2026, 11, d)))
    return repo


@pytest.fixture
def cliente(repo, estudos, monkeypatch):
    monkeypatch.setattr(tempo, "hoje", lambda: HOJE)
    app.dependency_overrides[repositorio_biblia] = lambda: repo
    app.dependency_overrides[repositorio_estudos] = lambda: estudos
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_pagina_de_hoje(cliente):
    r = cliente.get("/")
    assert r.status_code == 200
    t = r.text
    assert "Título de 3" in t and "03" in t and "NOV" in t
    assert "E sabemos que todas as coisas" in t  # versículo vem da Bíblia local
    assert "307/365" in t  # nº do dia no ano (3 de novembro de 2026)
    assert 'data-ref="psa.23.1-2"' in t  # leitura complementar com popover
    assert "<li>paz</li>" in t and "<li>cuidado</li>" in t
    assert 'lang="pt-BR"' in t and 'rel="prev"' in t
    assert "Bíblia Livre (BLIVRE)" in t  # crédito em todas as páginas


def test_referencias_do_corpo_viram_links_e_html_e_escapado(cliente):
    t = cliente.get("/").text
    assert (
        '<a class="ref" href="/biblia/filipenses/4#v6" data-ref="php.4.6">Filipenses 4.6</a>' in t
    )
    assert "&amp; pense" in t
    assert "<b>marca</b>" not in t and "&lt;b&gt;marca&lt;/b&gt;" in t


def test_open_graph(cliente):
    t = cliente.get("/").text
    assert '<meta property="og:title" content="Título de 3 — Maná Diário">' in t
    assert 'content="Uma frase para o dia que resume a lição."' in t
    assert 'property="og:image" content="http://localhost:8000/static/img/og.png"' in t
    assert 'property="og:url" content="http://localhost:8000/"' in t


def test_estudo_de_data_passada(cliente):
    r = cliente.get("/estudo/2026-11-01")
    assert r.status_code == 200 and "Título de 1" in r.text
    assert 'property="og:url" content="http://localhost:8000/estudo/2026-11-01"' in r.text
    assert 'rel="prev"' not in r.text and 'href="/estudo/2026-11-02" rel="next"' in r.text


def test_navegacao_so_aponta_para_estudos_ja_publicados(cliente):
    t = cliente.get("/estudo/2026-11-02").text
    assert (
        'href="/estudo/2026-11-01" rel="prev"' in t and 'href="/estudo/2026-11-03" rel="next"' in t
    )
    hoje = cliente.get("/").text
    assert 'rel="next"' not in hoje and "2026-11-04" not in hoje  # nunca vaza o futuro


@pytest.mark.parametrize("url", ["/estudo/2026-11-04", "/estudo/2026-11-05", "/estudo/2030-01-01"])
def test_estudos_futuros_dao_404_mesmo_existindo(cliente, url):
    assert cliente.get(url).status_code == 404


@pytest.mark.parametrize("url", ["/estudo/lixo", "/estudo/2026-13-45", "/estudo/2020-01-01"])
def test_datas_invalidas_ou_sem_registro_dao_404(cliente, url):
    r = cliente.get(url)
    assert r.status_code == 404 and "Não encontrado" in r.text


def test_futuro_nao_aparece_no_arquivo_nem_em_lugar_nenhum(cliente):
    for url in ("/", "/estudos", "/estudo/2026-11-03"):
        t = cliente.get(url).text
        assert "Título de 4" not in t and "Título de 5" not in t


def test_estudo_em_preparacao_quando_falhou(cliente, estudos):
    estudos.gravar_estudo(
        Estudo(data=HOJE, status="falhou", ref="rom.8.28", gerado_em=datetime(2026, 11, 3, 6))
    )
    r = cliente.get("/")
    assert r.status_code == 200
    assert "Estudo em preparação" in r.text and "E sabemos que todas as coisas" in r.text
    assert "Título de 3" not in r.text and 'class="frase"' not in r.text


def test_estudo_em_preparacao_quando_ainda_nao_existe(cliente, estudos):
    estudos.gravar([LinhaCalendario(date(2026, 11, 3), "jhn.3.16")])
    estudos.gravar_estudo(
        Estudo(data=HOJE, status="falhou", ref="jhn.3.16", gerado_em=datetime(2026, 11, 3, 6))
    )
    assert "Porque Deus amou ao mundo" in cliente.get("/").text


def test_hoje_sem_calendario_nem_estudo_mostra_preparacao(tmp_path, repo, monkeypatch):
    vazio = RepositorioEstudos(tmp_path / "vazio.sqlite")
    monkeypatch.setattr(tempo, "hoje", lambda: HOJE)
    app.dependency_overrides[repositorio_biblia] = lambda: repo
    app.dependency_overrides[repositorio_estudos] = lambda: vazio
    try:
        r = TestClient(app).get("/")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200 and "Estudo em preparação" in r.text


def test_ocasiao_aparece_na_data(cliente, estudos, monkeypatch):
    monkeypatch.setattr(tempo, "hoje", lambda: date(2026, 12, 25))
    estudos.gravar_estudo(estudo(date(2026, 12, 25), ref="isa.7.14", ocasiao="natal"))
    t = cliente.get("/").text
    assert "· NATAL" in t and "25" in t and "DEZ" in t


def test_arquivo_por_mes(cliente):
    t = cliente.get("/estudos").text
    assert "Novembro de 2026" in t
    assert t.index("Título de 3") < t.index("Título de 2") < t.index("Título de 1")
    assert 'href="/estudo/2026-11-02"' in t and "Romanos 8.28" in t


def test_arquivo_vazio(tmp_path, repo, monkeypatch):
    monkeypatch.setattr(tempo, "hoje", lambda: HOJE)
    app.dependency_overrides[repositorio_biblia] = lambda: repo
    app.dependency_overrides[repositorio_estudos] = lambda: RepositorioEstudos(tmp_path / "x.db")
    try:
        assert "Os primeiros estudos" in TestClient(app).get("/estudos").text
    finally:
        app.dependency_overrides.clear()


def test_ano_bissexto_no_numero_do_dia(cliente, estudos, monkeypatch):
    monkeypatch.setattr(tempo, "hoje", lambda: date(2028, 12, 31))
    estudos.gravar([LinhaCalendario(date(2028, 12, 31), "rom.8.28", "fim-de-ano")])
    estudos.gravar_estudo(estudo(date(2028, 12, 31)))
    assert "366/366" in cliente.get("/").text


def test_favicon_e_icones_no_head(cliente):
    t = cliente.get("/").text
    assert 'rel="icon" href="/static/img/favicon.svg"' in t and "apple-touch-icon" in t
    for caminho in ("favicon.svg", "favicon-32.png", "apple-touch-icon.png", "og.png"):
        assert cliente.get(f"/static/img/{caminho}").status_code == 200
