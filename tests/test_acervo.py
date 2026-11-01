import pytest

from mana.biblia.referencias import parse_referencia
from mana.estudos.acervo import (
    MIN_ENTRADAS,
    MIN_POR_OCASIAO,
    Acervo,
    Entrada,
    carregar,
    validar,
)
from mana.estudos.datas_especiais import OCASIOES


@pytest.fixture(scope="module")
def acervo():
    return carregar()


def test_acervo_real_integro_e_com_os_minimos(acervo, repo):
    assert validar(acervo, repo, frozenset(OCASIOES), exigir_minimos=True) == []


def test_tamanho_e_ocasioes(acervo):
    assert len(acervo.entradas) >= MIN_ENTRADAS
    for codigo in OCASIOES:
        assert sum(codigo in e.ocasioes for e in acervo.entradas) >= MIN_POR_OCASIAO, codigo


def test_cobre_os_66_livros_e_pesa_mais_em_salmos_proverbios_evangelhos_epistolas(acervo):
    por_livro = {}
    for e in acervo.entradas:
        por_livro[e.livro_id] = por_livro.get(e.livro_id, 0) + 1
    assert set(por_livro) == set(range(1, 67))
    assert por_livro[19] >= 100 and por_livro[20] >= 60  # Salmos, Provérbios
    assert sum(por_livro[i] for i in (40, 41, 42, 43)) >= 300  # Evangelhos
    assert sum(por_livro[i] for i in range(45, 66)) >= 300  # Epístolas


def test_proporcao_at_nt_razoavel(acervo):
    at = sum(e.testamento == "AT" for e in acervo.entradas)
    assert 0.38 <= at / len(acervo.entradas) <= 0.55


def test_temas_dentro_da_lista_fechada(acervo):
    assert 20 <= len(acervo.temas) <= 35
    usados = {t for e in acervo.entradas for t in e.temas}
    assert usados <= set(acervo.temas)
    assert set(acervo.temas) - usados == set()  # nenhum tema órfão


def test_sem_duplicatas_nem_sobreposicao(acervo):
    chaves = [e.chave for e in acervo.entradas]
    assert len(chaves) == len(set(chaves))
    vistos: set = set()
    for e in acervo.entradas:
        assert not (e.versiculos & vistos), e.chave
        vistos |= e.versiculos


def test_ocasioes_conhecidas_e_entradas_pequenas(acervo):
    for e in acervo.entradas:
        assert set(e.ocasioes) <= set(OCASIOES)
        assert 1 <= len(e.versiculos) <= 3 and 1 <= len(e.temas) <= 3


def montar(*itens, temas=("fe", "paz")):
    return Acervo(
        temas=temas,
        entradas=[Entrada(parse_referencia(r), tuple(t), tuple(o)) for r, t, o in itens],
    )


@pytest.mark.parametrize(
    ("itens", "trecho"),
    [
        ([("Rm 8.28", ["fe"], []), ("Rm 8.28", ["paz"], [])], "duplicada"),
        ([("Rm 8.28,29", ["fe"], []), ("Rm 8.29", ["paz"], [])], "sobrepõe"),
        ([("Rm 8.99", ["fe"], [])], "não existe"),
        ([("Rm 8.28", ["inventado"], [])], "fora da lista"),
        ([("Rm 8.28", [], [])], "temas"),
        ([("Rm 8.28", ["fe", "paz", "fe", "paz"], [])], "temas"),
        ([("Rm 8.28", ["fe"], ["carnaval"])], "ocasião desconhecida"),
        ([("Rm 8.28-31", ["fe"], [])], "máximo 3"),
        ([("Rm 8", ["fe"], [])], "um só capítulo"),
        ([("Gn 1.31-2.2", ["fe"], [])], "um só capítulo"),
    ],
)
def test_validador_pega_problemas(itens, trecho, repo):
    erros = validar(montar(*itens), repo, frozenset())
    assert any(trecho in e for e in erros), erros


def test_validador_exige_minimos_so_quando_pedido(repo):
    pequeno = montar(("Rm 8.28", ["fe"], []))
    assert validar(pequeno, repo, frozenset({"natal"})) == []
    erros = validar(pequeno, repo, frozenset({"natal"}), exigir_minimos=True)
    assert any("mínimo" in e for e in erros) and any("natal" in e for e in erros)
