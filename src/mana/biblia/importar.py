"""Download da Bíblia Livre (eBible, USFX) e conversão para SQLite (docs/BIBLIA.md §2)."""

import hashlib
import json
import re
import sqlite3
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from pathlib import Path

import httpx

URL_USFX = "https://ebible.org/Scriptures/porbr2018_usfx.zip"
NOME_ZIP = "porbr2018_usfx.zip"
NOME_XML = "porbr2018_usfx.xml"
VERSAO = "fevereiro de 2018"
CREDITO = (
    "Textos bíblicos: Bíblia Livre (BLIVRE), © Diego Santos, Mario Sérgio e Marco Teles, "
    f"versão de {VERSAO}. Licença Creative Commons Atribuição 4.0."
)
# Elementos cujo conteúdo não é texto do versículo: notas de rodapé e referências cruzadas.
IGNORAR = {"f", "x", "rq"}

ESQUEMA = """
CREATE TABLE livros (
  id INTEGER PRIMARY KEY,
  codigo TEXT NOT NULL UNIQUE,
  nome TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  abrev TEXT NOT NULL,
  testamento TEXT NOT NULL CHECK (testamento IN ('AT','NT')),
  capitulos INTEGER NOT NULL
);
CREATE TABLE versiculos (
  livro_id INTEGER NOT NULL REFERENCES livros(id),
  capitulo INTEGER NOT NULL,
  versiculo INTEGER NOT NULL,
  texto TEXT NOT NULL,
  PRIMARY KEY (livro_id, capitulo, versiculo)
);
CREATE VIRTUAL TABLE versiculos_fts USING fts5(
  texto, content='versiculos', content_rowid='rowid',
  tokenize='unicode61 remove_diacritics 2'
);
CREATE TABLE metadados (chave TEXT PRIMARY KEY, valor TEXT);
"""


class ErroImportacao(Exception):
    pass


def carregar_livros(caminho: Path) -> list[dict]:
    return json.loads(caminho.read_text(encoding="utf-8"))["livros"]


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def baixar(pasta_raw: Path, url: str = URL_USFX) -> Path:
    """Baixa e extrai o USFX em `pasta_raw`; grava `FONTE.md` ao lado. Devolve o XML."""
    pasta_raw.mkdir(parents=True, exist_ok=True)
    destino = pasta_raw / NOME_ZIP
    resp = httpx.get(url, follow_redirects=True, timeout=120)
    resp.raise_for_status()
    destino.write_bytes(resp.content)
    extraida = pasta_raw / "usfx"
    extraida.mkdir(exist_ok=True)
    with zipfile.ZipFile(destino) as z:
        for nome in z.namelist():
            if Path(nome).name != nome:  # nada de caminhos dentro do zip
                raise ErroImportacao(f"entrada suspeita no zip: {nome}")
        z.extractall(extraida)
    xml = extraida / NOME_XML
    if not xml.exists():
        raise ErroImportacao(f"{NOME_XML} não está no pacote")
    escrever_fonte(pasta_raw.parent / "FONTE.md", url, destino)
    return xml


def escrever_fonte(caminho: Path, url: str, zip_baixado: Path) -> None:
    caminho.write_text(
        f"""# Fonte da Bíblia

- **Edição:** Bíblia Livre (BLIVRE), eBible.org id `porbr2018`
  (revisão da Almeida de 1819, Textus Receptus).
- **Arquivo:** `{url}` (USFX)
- **Baixado em:** {date.today().isoformat()}
- **SHA-256 do zip:** `{sha256(zip_baixado)}`
- **Versão da BLIVRE:** {VERSAO}
- **Licença:** Creative Commons Atribuição 4.0 (https://creativecommons.org/licenses/by/4.0/br/)
- **Texto sem alterações de conteúdo.** Na importação: notas de rodapé e referências cruzadas
  são descartadas; as palavras acrescentadas (`<add>`) são mantidas como texto simples; e os
  espaços antes de pontuação (`isso , mas`, artefato de formatação do arquivo, ~800
  versículos) são removidos. Nenhuma palavra é alterada.

## Crédito exibido no site

> {CREDITO}

Forma curta (popover): **BLIVRE**.
""",
        encoding="utf-8",
    )


def normalizar(texto: str) -> str:
    """Espaços simples e sem espaço antes de pontuação (artefato do USFX: `</add> ,`)."""
    texto = re.sub(r"\s+", " ", texto).strip()
    return re.sub(r"\s+([,.;:!?])", r"\1", texto)


class _Leitor:
    """Percorre o USFX em ordem de documento, juntando o texto de cada versículo.

    `<c id>` e `<v id>` são marcos vazios; o texto do versículo vai até `<ve/>` (ou o
    próximo `<v>`). Notas (`f`) e referências cruzadas (`rq`) são puladas, mas o texto que
    vem depois delas (`tail`) continua valendo.
    """

    def __init__(self) -> None:
        self.capitulos: dict[int, dict[int, list[str]]] = {}
        self.cap = 0
        self.vers: int | None = None

    def _texto(self, texto: str | None) -> None:
        if texto and self.vers is not None:
            self.capitulos[self.cap][self.vers].append(texto)

    def visitar(self, elem: ET.Element) -> None:
        if elem.tag == "c":
            self.cap, self.vers = int(elem.get("id")), None
        elif elem.tag == "v":
            self.vers = int(elem.get("id"))
            self.capitulos.setdefault(self.cap, {})[self.vers] = []
        elif elem.tag == "ve":
            self.vers = None
        elif elem.tag not in IGNORAR:
            self._texto(elem.text)
            for filho in elem:
                self.visitar(filho)
                self._texto(filho.tail)
            return
        # marcos e ignorados: nenhum conteúdo próprio a percorrer


def ler_usfx(xml: Path) -> dict[str, dict[int, dict[int, str]]]:
    """Devolve {codigo_livro: {capitulo: {versiculo: texto}}}."""
    raiz = ET.parse(xml).getroot()
    resultado: dict[str, dict[int, dict[int, str]]] = {}
    for livro in raiz.iter("book"):
        leitor = _Leitor()
        leitor.visitar(livro)
        resultado[livro.get("id")] = {
            cap: {v: normalizar("".join(partes)) for v, partes in vs.items()}
            for cap, vs in leitor.capitulos.items()
        }
    return resultado


def verificar(con: sqlite3.Connection, livros: list[dict]) -> None:
    """Verificações de integridade (docs/BIBLIA.md §4). Levanta ErroImportacao se falhar."""
    erros: list[str] = []
    n_livros = con.execute("SELECT COUNT(*) FROM livros").fetchone()[0]
    if n_livros != 66:
        erros.append(f"{n_livros} livros (esperado 66)")
    for livro in livros:
        caps = con.execute(
            "SELECT COUNT(DISTINCT capitulo), MAX(capitulo) FROM versiculos WHERE livro_id=?",
            (livro["id"],),
        ).fetchone()
        if caps != (livro["capitulos"], livro["capitulos"]):
            erros.append(f"{livro['nome']}: {caps[0]} capítulos (esperado {livro['capitulos']})")
    por_t = dict(
        con.execute(
            "SELECT l.testamento, COUNT(DISTINCT v.livro_id*1000+v.capitulo) FROM versiculos v "
            "JOIN livros l ON l.id=v.livro_id GROUP BY l.testamento"
        ).fetchall()
    )
    if por_t != {"AT": 929, "NT": 260}:
        erros.append(f"capítulos por testamento: {por_t}")
    vazios = con.execute("SELECT COUNT(*) FROM versiculos WHERE TRIM(texto)=''").fetchone()[0]
    if vazios:
        erros.append(f"{vazios} versículos vazios")
    sem_v1 = con.execute(
        "SELECT COUNT(*) FROM (SELECT livro_id, capitulo FROM versiculos "
        "GROUP BY livro_id, capitulo HAVING MIN(versiculo) <> 1)"
    ).fetchone()[0]
    if sem_v1:
        erros.append(f"{sem_v1} capítulos sem o versículo 1")
    if erros:
        raise ErroImportacao("; ".join(erros))


def importar(xml: Path, livros_json: Path, destino: Path) -> int:
    """Converte o USFX em SQLite; só substitui `destino` se tudo passar. Devolve o total."""
    livros = carregar_livros(livros_json)
    dados = ler_usfx(xml)
    temporario = destino.with_suffix(".sqlite.novo")
    temporario.unlink(missing_ok=True)
    destino.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(temporario)
    try:
        con.executescript(ESQUEMA)
        for livro in livros:
            con.execute(
                "INSERT INTO livros VALUES (?,?,?,?,?,?,?)",
                (
                    livro["id"],
                    livro["codigo"],
                    livro["nome"],
                    livro["slug"],
                    livro["abrev"],
                    livro["testamento"],
                    livro["capitulos"],
                ),
            )
            for cap, vs in dados.get(livro["codigo"], {}).items():
                con.executemany(
                    "INSERT INTO versiculos VALUES (?,?,?,?)",
                    [(livro["id"], cap, v, t) for v, t in vs.items()],
                )
        con.execute("INSERT INTO versiculos_fts(rowid, texto) SELECT rowid, texto FROM versiculos")
        total = con.execute("SELECT COUNT(*) FROM versiculos").fetchone()[0]
        meta = {
            "edicao": "Bíblia Livre (BLIVRE)",
            "versao": VERSAO,
            "licenca": "CC BY 4.0",
            "credito": CREDITO,
            "sha256_xml": sha256(xml),
            "total_versiculos": str(total),
        }
        con.executemany("INSERT INTO metadados VALUES (?,?)", meta.items())
        verificar(con, livros)
        con.commit()
    except Exception:
        con.close()
        temporario.unlink(missing_ok=True)
        raise
    con.close()
    temporario.replace(destino)
    return total
