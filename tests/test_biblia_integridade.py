import json
import re
import sqlite3

from conftest import RAIZ

LIVROS = json.loads((RAIZ / "data" / "livros.json").read_text(encoding="utf-8"))["livros"]


def con(repo):
    return sqlite3.connect(f"file:{repo.caminho}?mode=ro", uri=True)


def test_66_livros_e_1189_capitulos(repo):
    c = con(repo)
    assert c.execute("SELECT COUNT(*) FROM livros").fetchone()[0] == 66
    total = c.execute("SELECT COUNT(*) FROM (SELECT DISTINCT livro_id, capitulo FROM versiculos)")
    assert total.fetchone()[0] == 1189
    assert sum(livro["capitulos"] for livro in LIVROS) == 1189


def test_capitulos_por_livro_batem_com_livros_json(repo):
    c = con(repo)
    for livro in LIVROS:
        n, maximo = c.execute(
            "SELECT COUNT(DISTINCT capitulo), MAX(capitulo) FROM versiculos WHERE livro_id=?",
            (livro["id"],),
        ).fetchone()
        assert (n, maximo) == (livro["capitulos"], livro["capitulos"]), livro["nome"]


def test_testamentos(repo):
    c = con(repo)
    linhas = dict(
        c.execute(
            "SELECT l.testamento, COUNT(*) "
            "FROM (SELECT DISTINCT livro_id, capitulo FROM versiculos) v "
            "JOIN livros l ON l.id = v.livro_id GROUP BY l.testamento"
        ).fetchall()
    )
    assert linhas == {"AT": 929, "NT": 260}


def test_nenhum_versiculo_vazio_e_todo_capitulo_comeca_no_1(repo):
    c = con(repo)
    assert c.execute("SELECT COUNT(*) FROM versiculos WHERE TRIM(texto) = ''").fetchone()[0] == 0
    sem_v1 = c.execute(
        "SELECT COUNT(*) FROM (SELECT 1 FROM versiculos GROUP BY livro_id, capitulo "
        "HAVING MIN(versiculo) <> 1)"
    ).fetchone()[0]
    assert sem_v1 == 0


def test_total_de_versiculos_da_edicao(repo):
    assert con(repo).execute("SELECT COUNT(*) FROM versiculos").fetchone()[0] == 31102
    assert repo.metadado("total_versiculos") == "31102"


def test_amostras_conhecidas(repo):
    c = con(repo)
    for livro, cap, v in [(1, 1, 1), (19, 23, 1), (43, 3, 16), (45, 8, 28), (66, 22, 21)]:
        assert c.execute(
            "SELECT 1 FROM versiculos WHERE livro_id=? AND capitulo=? AND versiculo=?",
            (livro, cap, v),
        ).fetchone()
    assert repo.capitulo(43, 3)[15].texto.startswith("Porque Deus amou ao mundo")


def test_sem_restos_de_marcacao_ou_notas(repo):
    c = con(repo)
    assert c.execute("SELECT COUNT(*) FROM versiculos WHERE texto LIKE '%<%'").fetchone()[0] == 0
    assert c.execute("SELECT COUNT(*) FROM versiculos WHERE texto LIKE '%  %'").fetchone()[0] == 0


def test_credito_nos_metadados(repo):
    assert "Bíblia Livre" in repo.metadado("credito")
    assert repo.metadado("licenca") == "CC BY 4.0"


def test_busca_ignora_acento(repo):
    assert repo.contar_busca("esperanca") == repo.contar_busca("esperança") > 50
    achados = repo.buscar("pastor", limite=3)
    assert len(achados) == 3 and "<mark>" in achados[0].trecho


def test_sem_espaco_antes_de_pontuacao(repo):
    ruins = [
        t
        for (t,) in con(repo).execute("SELECT texto FROM versiculos")
        if re.search(r"\s[,.;:!?]", t)
    ]
    assert ruins == []
    assert "adoção, isto é, a redenção" in repo.capitulo(45, 8)[22].texto


def test_palavras_acrescentadas_nao_colam_na_anterior(repo):
    texto = repo.capitulo(55, 2)[14].texto  # 2 Timóteo 2.15
    assert "a Deus como um trabalhador" in texto
    colados = [
        t
        for (t,) in con(repo).execute("SELECT texto FROM versiculos")
        if re.search(r"\b(Deus|Senhor)(como|mais|apenas|somente)\b", t)
    ]
    assert colados == []
