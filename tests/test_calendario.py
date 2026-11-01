from datetime import date, timedelta

import pytest

from mana.biblia.referencias import canonico, parse_canonico, parse_referencia
from mana.estudos import calendario as cal
from mana.estudos.acervo import Acervo, carregar
from mana.estudos.datas_especiais import OCASIOES, ocasioes_do_ano
from mana.estudos.repositorio import LinhaCalendario, RepositorioEstudos

TODAS = frozenset(OCASIOES)


@pytest.fixture(scope="module")
def acervo():
    return carregar()


@pytest.fixture(scope="module")
def cadeia(acervo):
    """2027, 2028 (bissexto) e 2029 gerados em sequência, como em produção."""
    historico: list[LinhaCalendario] = []
    resultados = {}
    for ano in (2027, 2028, 2029):
        r = cal.gerar(ano, acervo, TODAS, historico)
        historico += r.linhas
        resultados[ano] = r
    return resultados, historico


def test_deterministico_para_a_mesma_semente(acervo):
    a = cal.gerar(2027, acervo, TODAS, [])
    b = cal.gerar(2027, acervo, TODAS, [])
    assert a.linhas == b.linhas
    assert cal.gerar(2028, acervo, TODAS, []).linhas != a.linhas


def test_anos_completos_inclusive_bissexto(cadeia):
    resultados, _ = cadeia
    assert [len(resultados[a].linhas) for a in (2027, 2028, 2029)] == [365, 366, 365]
    assert date(2028, 2, 29) in {x.data for x in resultados[2028].linhas}
    datas = [x.data for x in resultados[2028].linhas]
    assert datas == sorted(datas) and len(set(datas)) == 366


def test_respeita_janela_livros_e_temas_em_tres_anos(cadeia, acervo):
    _, historico = cadeia
    assert cal.verificar(historico, acervo) == []
    assert all(not r.avisos for r in cadeia[0].values())


def test_nenhuma_referencia_repete_em_1095_dias(cadeia):
    _, historico = cadeia
    ultima: dict[str, date] = {}
    for x in historico:
        if x.ref in ultima:
            assert (x.data - ultima[x.ref]).days >= 1095, x
        ultima[x.ref] = x.data


def test_datas_especiais_recebem_referencia_da_ocasiao(cadeia, acervo):
    resultados, _ = cadeia
    por_chave = {e.chave: e for e in acervo.entradas}
    for ano, r in resultados.items():
        do_dia = {x.data: x for x in r.linhas}
        for d, oc in ocasioes_do_ano(ano).items():
            assert do_dia[d].ocasiao == oc.codigo
            assert oc.codigo in por_chave[do_dia[d].ref].ocasioes


def test_entradas_de_ocasiao_nao_caem_em_dia_comum(cadeia, acervo):
    reservadas = {e.chave for e in acervo.entradas if e.ocasioes}
    for r in cadeia[0].values():
        for x in r.linhas:
            assert (x.ocasiao is not None) == (x.ref in reservadas), x


def test_proporcoes_por_ano(cadeia):
    for ano, r in cadeia[0].items():
        est = cal.estatisticas(r.linhas)
        assert 42 <= est["pct_at"] <= 48, (ano, est)
        assert est["pct_salmos_proverbios"] <= 25, (ano, est)


def test_nada_de_livro_tres_dias_seguidos_nem_tema_em_dias_seguidos(cadeia, acervo):
    por_chave = {e.chave: e for e in acervo.entradas}
    dias = sorted(cadeia[1], key=lambda x: x.data)
    for a, b in zip(dias, dias[1:], strict=False):
        assert not set(por_chave[a.ref].temas) & set(por_chave[b.ref].temas), (a.data, b.data)
    for a, b, c in zip(dias, dias[1:], dias[2:], strict=False):
        livros = {por_chave[x.ref].livro_id for x in (a, b, c)}
        assert len(livros) > 1, a.data


def test_todas_as_referencias_existem_no_banco(cadeia, repo):
    for x in cadeia[1]:
        assert repo.existe(parse_canonico(x.ref)), x


def test_ano_parcial_comeca_na_data_pedida_e_respeita_o_historico(acervo, cadeia):
    _, historico_2027 = cadeia
    r = cal.gerar(2026, acervo, TODAS, [], inicio=date(2026, 10, 31))
    assert r.linhas[0].data == date(2026, 10, 31) and r.linhas[-1].data == date(2026, 12, 31)
    assert len(r.linhas) == 62
    assert [x.ocasiao for x in r.linhas if x.ocasiao] == [
        "advento",
        "vespera-natal",
        "natal",
        "fim-de-ano",
    ]
    # 2027 gerado depois de 2026 não repete nada de 2026 dentro da janela
    r27 = cal.gerar(2027, acervo, TODAS, r.linhas)
    assert cal.verificar(r.linhas + r27.linhas, acervo) == []


def test_dias_ja_existentes_nao_sao_refeitos(acervo):
    primeiro = cal.gerar(2027, acervo, TODAS, [])
    fixos = primeiro.linhas[:100]
    refeito = cal.gerar(2027, acervo, TODAS, fixos)
    assert len(refeito.linhas) == 265
    assert refeito.linhas[0].data == fixos[-1].data + timedelta(days=1)
    assert cal.verificar(fixos + refeito.linhas, acervo) == []


def test_ocasioes_desativadas_nao_aparecem(acervo):
    r = cal.gerar(2027, acervo, frozenset({"natal"}), [])
    assert [x.ocasiao for x in r.linhas if x.ocasiao] == ["natal"]


def test_acervo_pequeno_reduz_a_janela_e_avisa(acervo):
    comuns = [e for e in acervo.entradas if not e.ocasioes]
    pequeno = Acervo(
        temas=acervo.temas,
        entradas=[e for e in acervo.entradas if e.ocasioes]
        + comuns[::3][:140]
        + comuns[1::3][:140],
    )
    r = cal.gerar(2027, pequeno, TODAS, [])
    assert len(r.linhas) == 365
    assert any("janela" in a for a in r.avisos)


def test_acervo_sem_ocasiao_da_data_e_erro(acervo):
    sem_natal = Acervo(
        temas=acervo.temas, entradas=[e for e in acervo.entradas if "natal" not in e.ocasioes]
    )
    with pytest.raises(cal.ErroCalendario):
        cal.gerar(2027, sem_natal, frozenset({"natal"}), [])


# ------------------------------------------------------------------ banco e YAML


@pytest.fixture
def repo_estudos(tmp_path):
    return RepositorioEstudos(tmp_path / "mana.sqlite")


def test_repositorio_idempotente_e_wal(repo_estudos):
    assert repo_estudos.calendario() == []
    repo_estudos.gravar([LinhaCalendario(date(2027, 1, 1), "rom.8.28")])
    repo_estudos.gravar([LinhaCalendario(date(2027, 1, 1), "jhn.3.16", "ano-novo", "editado")])
    assert repo_estudos.calendario() == [
        LinhaCalendario(date(2027, 1, 1), "jhn.3.16", "ano-novo", "editado")
    ]
    assert repo_estudos.dia(date(2027, 1, 2)) is None
    assert repo_estudos.apagar_calendario(date(2027, 1, 1), date(2027, 1, 31)) == 1
    import sqlite3

    assert (
        sqlite3.connect(repo_estudos.caminho).execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    )


def preparar(tmp_path, repo_estudos, acervo):
    r = cal.gerar(2027, acervo, TODAS, [])
    repo_estudos.gravar(r.linhas)
    arquivo = tmp_path / "2027.yaml"
    cal.exportar_yaml(2027, repo_estudos.calendario(), arquivo)
    return arquivo, r.linhas


def test_exportar_e_reimportar_sem_mudancas(tmp_path, repo_estudos, acervo, repo):
    arquivo, _ = preparar(tmp_path, repo_estudos, acervo)
    texto = arquivo.read_text(encoding="utf-8")
    assert 'ref: "Deuteronômio 11.12"' in texto or "ocasiao: ano-novo" in texto
    rel = cal.importar_yaml(2027, arquivo, repo_estudos, repo, acervo, hoje=date(2026, 10, 31))
    assert rel.erros == [] and rel.alterados == [] and rel.avisos == []


def test_importar_aplica_edicoes_futuras(tmp_path, repo_estudos, acervo, repo):
    arquivo, linhas = preparar(tmp_path, repo_estudos, acervo)
    alvo = linhas[40]
    antigo = arquivo.read_text(encoding="utf-8")
    linha_antiga = next(x for x in antigo.splitlines() if f'"{alvo.data}"' in x)
    nova_linha = f'  - {{data: "{alvo.data}", ref: "Romanos 8.28"}}'
    arquivo.write_text(antigo.replace(linha_antiga, nova_linha), encoding="utf-8")
    rel = cal.importar_yaml(2027, arquivo, repo_estudos, repo, acervo, hoje=date(2026, 10, 31))
    assert rel.erros == [] and rel.alterados == [alvo.data]
    gravado = repo_estudos.dia(alvo.data)
    assert (gravado.ref, gravado.origem) == (canonico(parse_referencia("Rm 8.28")), "editado")


def test_importar_recusa_mudar_dia_publicado_e_nao_grava_nada(tmp_path, repo_estudos, acervo, repo):
    arquivo, linhas = preparar(tmp_path, repo_estudos, acervo)
    texto = arquivo.read_text(encoding="utf-8")
    passado = linhas[3]  # 04/01/2027 já "publicado" se hoje for 10/01/2027
    futuro = linhas[200]
    for alvo in (passado, futuro):
        linha = next(x for x in texto.splitlines() if f'"{alvo.data}"' in x)
        texto = texto.replace(linha, f'  - {{data: "{alvo.data}", ref: "Salmos 23.1"}}')
    arquivo.write_text(texto, encoding="utf-8")
    antes = repo_estudos.calendario()
    rel = cal.importar_yaml(2027, arquivo, repo_estudos, repo, acervo, hoje=date(2027, 1, 10))
    assert any("já publicado" in e for e in rel.erros)
    assert repo_estudos.calendario() == antes  # tudo ou nada


@pytest.mark.parametrize(
    ("ref", "trecho"),
    [("Romanos 8.99", "inexistente"), ("lixo", "inválida")],
)
def test_importar_recusa_referencia_ruim(tmp_path, repo_estudos, acervo, repo, ref, trecho):
    arquivo, linhas = preparar(tmp_path, repo_estudos, acervo)
    texto = arquivo.read_text(encoding="utf-8")
    linha = next(x for x in texto.splitlines() if f'"{linhas[50].data}"' in x)
    arquivo.write_text(
        texto.replace(linha, f'  - {{data: "{linhas[50].data}", ref: "{ref}"}}'), encoding="utf-8"
    )
    rel = cal.importar_yaml(2027, arquivo, repo_estudos, repo, acervo, hoje=date(2026, 10, 31))
    assert any(trecho in e for e in rel.erros)


def test_importar_avisa_referencia_fora_do_acervo_e_repeticao(tmp_path, repo_estudos, acervo, repo):
    arquivo, linhas = preparar(tmp_path, repo_estudos, acervo)
    texto = arquivo.read_text(encoding="utf-8")
    a, b = linhas[60], linhas[100]
    ref_a = next(x for x in texto.splitlines() if f'"{a.data}"' in x)
    ref_b = next(x for x in texto.splitlines() if f'"{b.data}"' in x)
    nova = f'  - {{data: "{b.data}", ref: "{ref_a.split("ref: ")[1].split(",")[0].split("}")[0]}"}}'
    arquivo.write_text(texto.replace(ref_b, nova.replace('""', '"')), encoding="utf-8")
    rel = cal.importar_yaml(2027, arquivo, repo_estudos, repo, acervo, hoje=date(2026, 10, 31))
    assert rel.erros == [] and any("repete" in w for w in rel.avisos)


def test_importar_arquivo_de_outro_ano(tmp_path, repo_estudos, acervo, repo):
    arquivo, _ = preparar(tmp_path, repo_estudos, acervo)
    rel = cal.importar_yaml(2028, arquivo, repo_estudos, repo, acervo, hoje=date(2026, 10, 31))
    assert any("ano" in e for e in rel.erros)
