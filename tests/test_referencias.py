import pytest

from mana.biblia.referencias import (
    canonico,
    chave,
    encontrar_referencias,
    formatar,
    linkar_referencias,
    livros,
    parse_canonico,
    parse_referencia,
)

# entrada → (canônico, exibição)
VALIDAS = [
    ("Romanos 5.3,4", "rom.5.3-4", "Romanos 5.3,4"),
    ("Tiago 1.2-4", "jas.1.2-4", "Tiago 1.2-4"),
    ("Rm 8:28", "rom.8.28", "Romanos 8.28"),
    ("rm 8.28", "rom.8.28", "Romanos 8.28"),
    ("1 Coríntios 13", "1co.13", "1 Coríntios 13"),
    ("1Co 13", "1co.13", "1 Coríntios 13"),
    ("I Co 13.4-7", "1co.13.4-7", "1 Coríntios 13.4-7"),
    ("II Coríntios 5.17", "2co.5.17", "2 Coríntios 5.17"),
    ("1 Corintios 13.4", "1co.13.4", "1 Coríntios 13.4"),
    ("III Jo 4", "3jn.1.4", "3 João 4"),
    ("Jo 3.16; 14.6", "jhn.3.16;jhn.14.6", "João 3.16; 14.6"),
    ("Jo 3.16; Rm 8.28", "jhn.3.16;rom.8.28", "João 3.16; Romanos 8.28"),
    ("Gn 1.1-2.3", "gen.1.1-2.3", "Gênesis 1.1-2.3"),
    ("Gn 1-3", "gen.1-3", "Gênesis 1-3"),
    ("Sl 23", "psa.23", "Salmos 23"),
    ("Salmo 23", "psa.23", "Salmos 23"),
    ("Salmos 23.1-3", "psa.23.1-3", "Salmos 23.1-3"),
    ("Obadias 4", "oba.1.4", "Obadias 4"),
    ("Judas 3", "jud.1.3", "Judas 3"),
    ("Rm 5.3,5", "rom.5.3;rom.5.5", "Romanos 5.3,5"),
    ("Jó 3.1", "job.3.1", "Jó 3.1"),
    ("Job 3.1", "job.3.1", "Jó 3.1"),
    ("Jo 3.16", "jhn.3.16", "João 3.16"),
    ("João 3.16", "jhn.3.16", "João 3.16"),
    ("Joao 3:16", "jhn.3.16", "João 3.16"),
    ("Cantares de Salomão 2.1", "sng.2.1", "Cantares 2.1"),
    ("Atos dos Apóstolos 2.38", "act.2.38", "Atos 2.38"),
    ("Êx 20.1-17", "exo.20.1-17", "Êxodo 20.1-17"),
    ("Mt 5.3 - 12", "mat.5.3-12", "Mateus 5.3-12"),
    ("Ap 22.21", "rev.22.21", "Apocalipse 22.21"),
]

INVALIDAS = [
    "",
    "Xyz 3",
    "Romanos",
    "Romanos 99.1",
    "Rm 8.0",
    "Rm 8.30-28",
    "Judas 3-1",
    "Obadias 2.3",
    "Jo",
    "3.16",
    "Rm 8.28 e 29",
    "Jo 3.16;",
    "Gn 51",
]


@pytest.mark.parametrize(("entrada", "canon", "exib"), VALIDAS)
def test_referencias_validas(entrada, canon, exib):
    ref = parse_referencia(entrada)
    assert ref is not None
    assert canonico(ref) == canon
    assert formatar(ref) == exib


@pytest.mark.parametrize("entrada", INVALIDAS)
def test_referencias_invalidas(entrada):
    assert parse_referencia(entrada) is None


@pytest.mark.parametrize(("entrada", "canon", "_"), VALIDAS)
def test_ida_e_volta_canonica(entrada, canon, _):
    ref = parse_referencia(entrada)
    assert parse_canonico(canon) == ref


def test_jo_com_e_sem_acento():
    assert canonico(parse_referencia("Jó 3.1")).startswith("job.")
    assert canonico(parse_referencia("Jo 3.1")).startswith("jhn.")
    assert chave("Jó") == "job" and chave("Jo") == "jo"


def test_sem_nomes_ambiguos_e_66_livros_resolvem():
    for livro in livros():
        ref = parse_referencia(f"{livro.abrev} 1.1") or parse_referencia(f"{livro.nome} 1.1")
        assert ref is not None, livro.nome
        assert canonico(ref).startswith(livro.usfm + "."), livro.nome


def test_canonico_so_ascii():
    for livro in livros():
        assert livro.usfm.isascii()


@pytest.mark.parametrize("texto", ["rom.0.1", "xxx.1.1", "rom.8.28-27", "rom", "rom.8.1-2.3"])
def test_canonico_invalido(texto):
    assert parse_canonico(texto) is None


# ----------------------------------------------------------------- texto livre


def refs(texto):
    return [texto[e.inicio : e.fim] for e in encontrar_referencias(texto)]


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Veja Os 6.6 agora", ["Os 6.6"]),
        ("em At 2:38 vemos", ["At 2:38"]),
        ("Leia Isaías 40 hoje", ["Isaías 40"]),
        ("Salmo 23 é belo", ["Salmo 23"]),
        ("Em 2 Coríntios 5.17 diz", ["2 Coríntios 5.17"]),
        ("Romanos 8.28,29 ou Jo 3.16; 14.6.", ["Romanos 8.28,29", "Jo 3.16; 14.6"]),
        ("Jó 3.1 e Jo 3.16", ["Jó 3.1", "Jo 3.16"]),
        ("Veja Tiago 1.2-4.", ["Tiago 1.2-4"]),
        ("Judas 3 e Obadias 4", ["Judas 3", "Obadias 4"]),
    ],
)
def test_encontra_referencias_em_texto(texto, esperado):
    assert refs(texto) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        "os 12 discípulos",
        "Os 12 discípulos seguiram",
        "na 1ª carta aos coríntios",
        "Is 40 é um capítulo",
        "Am 3 sem versículo",
        "Atos sozinho",
        "Em 2020 foi",
        "Mateus disse 5 vezes",
    ],
)
def test_falsos_positivos(texto):
    assert refs(texto) == []


def test_ponto_e_virgula_so_continua_com_capitulo_e_versiculo():
    assert refs("Jo 3.16; 14 pessoas") == ["Jo 3.16"]


def test_linkar_gera_link_e_escapa_html():
    html = linkar_referencias("Veja <b> Romanos 8.28 & mais.")
    assert html == (
        'Veja &lt;b&gt; <a class="ref" href="/biblia/romanos/8#v28" data-ref="rom.8.28">'
        "Romanos 8.28</a> &amp; mais."
    )


def test_linkar_capitulo_inteiro_sem_ancora():
    assert 'href="/biblia/isaias/40"' in linkar_referencias("Isaías 40")


def test_linkar_deixa_texto_puro_se_nao_existe():
    assert linkar_referencias("Romanos 8.28", existe=lambda r: False) == "Romanos 8.28"
    assert "<a " in linkar_referencias("Romanos 8.28", existe=lambda r: True)


def test_existencia_no_banco(repo):
    assert repo.existe(parse_referencia("Rm 8.28"))
    assert repo.existe(parse_referencia("Gn 1.1-2.3"))
    assert repo.existe(parse_referencia("Sl 119"))
    assert not repo.existe(parse_referencia("Rm 8.99"))
    assert not repo.existe(parse_referencia("Jd 1.99"))
