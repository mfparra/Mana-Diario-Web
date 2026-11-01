from datetime import date

import pytest

from mana.estudos.datas_especiais import (
    CIVIL,
    OCASIOES,
    interpretar_ativas,
    ocasioes_do_ano,
)


def datas(ano):
    return {o.codigo: d for d, o in ocasioes_do_ano(ano).items()}


@pytest.mark.parametrize(
    ("ano", "codigo", "esperada"),
    [
        (2026, "pascoa", date(2026, 4, 5)),
        (2026, "corpus-christi", date(2026, 6, 4)),
        (2027, "pascoa", date(2027, 3, 28)),
        (2027, "corpus-christi", date(2027, 5, 27)),
        (2028, "advento", date(2028, 12, 3)),
        (2027, "dia-das-maes", date(2027, 5, 9)),
        (2027, "dia-dos-pais", date(2027, 8, 8)),
        (2026, "cinzas", date(2026, 2, 18)),
        (2026, "ramos", date(2026, 3, 29)),
        (2026, "quinta-santa", date(2026, 4, 2)),
        (2026, "sexta-santa", date(2026, 4, 3)),
        (2026, "ascensao", date(2026, 5, 14)),
        (2026, "pentecostes", date(2026, 5, 24)),
        (2026, "trindade", date(2026, 5, 31)),
        (2026, "ano-novo", date(2026, 1, 1)),
        (2026, "epifania", date(2026, 1, 6)),
        (2026, "vespera-natal", date(2026, 12, 24)),
        (2026, "natal", date(2026, 12, 25)),
        (2026, "fim-de-ano", date(2026, 12, 31)),
    ],
)
def test_datas_conhecidas(ano, codigo, esperada):
    assert datas(ano)[codigo] == esperada


def test_todas_as_ocasioes_caem_no_ano_e_so_as_civis_perdem_empates():
    for ano in range(2024, 2060):
        resultado = ocasioes_do_ano(ano)
        assert all(d.year == ano for d in resultado)
        perdidas = set(OCASIOES) - {o.codigo for o in resultado.values()}
        assert all(OCASIOES[c].prioridade == CIVIL for c in perdidas), (ano, perdidas)
        assert len(perdidas) <= 1


def test_empate_acontece_em_anos_conhecidos():
    # 2035: Pentecostes = 2º domingo de maio (13/05) → o Dia das Mães perde
    assert "dia-das-maes" not in datas(2035)
    assert datas(2035)["pentecostes"] == date(2035, 5, 13)


def test_advento_e_sempre_um_domingo_a_partir_de_27_de_novembro():
    for ano in range(2024, 2040):
        d = datas(ano)["advento"]
        assert d.weekday() == 6 and date(ano, 11, 27) <= d <= date(ano, 12, 3)


def test_dia_das_maes_e_dos_pais_sao_domingos():
    for ano in range(2024, 2040):
        maes = datas(ano).get("dia-das-maes")
        if maes:  # em anos de empate com o Pentecostes ela some
            assert maes.weekday() == 6 and 8 <= maes.day <= 14
        assert datas(ano)["dia-dos-pais"].weekday() == 6


def test_empate_vale_o_calendario_cristao_sobre_o_civil():
    # 2008: Pentecostes e o 2º domingo de maio caíram em 11/05
    assert ocasioes_do_ano(2008)[date(2008, 5, 11)].codigo == "pentecostes"


def test_ocasioes_ativas():
    so_natal = ocasioes_do_ano(2027, {"natal", "pascoa"})
    assert sorted(o.codigo for o in so_natal.values()) == ["natal", "pascoa"]
    assert interpretar_ativas("todas") == frozenset(OCASIOES)
    assert interpretar_ativas("pascoa, natal") == {"pascoa", "natal"}
    with pytest.raises(ValueError):
        interpretar_ativas("pascoa,carnaval")
