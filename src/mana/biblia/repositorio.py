"""Acesso de leitura à Bíblia local (data/biblia/biblia.sqlite)."""

import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from mana.biblia.referencias import Referencia, Trecho

LIMITE_VERSICULOS = 400


@dataclass(frozen=True)
class Versiculo:
    capitulo: int
    numero: int
    texto: str


@dataclass(frozen=True)
class ResultadoBusca:
    livro_id: int
    capitulo: int
    numero: int
    trecho: str  # com <mark> nos termos encontrados


def _expressao_fts(consulta: str) -> str:
    """Todas as palavras entre aspas (sem sintaxe FTS do usuário); prefixo na última."""
    termos = re.findall(r"\w+", consulta)
    if not termos:
        return ""
    return " ".join(f'"{t}"' for t in termos) + "*"


class RepositorioBiblia:
    def __init__(self, caminho: str | Path) -> None:
        self.caminho = Path(caminho)

    def _conectar(self) -> sqlite3.Connection:
        if not self.caminho.exists():
            raise FileNotFoundError(f"Bíblia não encontrada: {self.caminho} (mana biblia importar)")
        return sqlite3.connect(f"file:{self.caminho}?mode=ro", uri=True)

    def capitulo(self, livro_id: int, capitulo: int) -> list[Versiculo]:
        return self.versiculos(Trecho(livro_id, capitulo, None, capitulo, None))

    def versiculos(self, t: Trecho) -> list[Versiculo]:
        ini = (t.cap_ini, t.vers_ini if t.vers_ini is not None else 1)
        fim = (t.cap_fim, t.vers_fim if t.vers_fim is not None else 999)
        with closing(self._conectar()) as con:
            linhas = con.execute(
                "SELECT capitulo, versiculo, texto FROM versiculos WHERE livro_id=? "
                "AND (capitulo, versiculo) BETWEEN (?, ?) AND (?, ?) ORDER BY capitulo, versiculo",
                (t.livro_id, *ini, *fim),
            ).fetchall()
        return [Versiculo(*linha) for linha in linhas]

    def passagem(self, ref: Referencia) -> list[Versiculo]:
        return [v for t in ref.trechos for v in self.versiculos(t)]

    def _existe_versiculo(
        self, con: sqlite3.Connection, livro_id: int, cap: int, vers: int
    ) -> bool:
        return (
            con.execute(
                "SELECT 1 FROM versiculos WHERE livro_id=? AND capitulo=? AND versiculo=?",
                (livro_id, cap, vers),
            ).fetchone()
            is not None
        )

    def existe(self, ref: Referencia) -> bool:
        """True se o início e o fim de cada trecho existem na Bíblia."""
        with closing(self._conectar()) as con:
            for t in ref.trechos:
                if t.vers_ini is None:
                    extremos = [(t.cap_ini, 1), (t.cap_fim, 1)]
                else:
                    extremos = [(t.cap_ini, t.vers_ini), (t.cap_fim, t.vers_fim)]
                if not all(self._existe_versiculo(con, t.livro_id, c, v) for c, v in extremos):
                    return False
        return True

    def contar_versiculos(self, ref: Referencia) -> int:
        return len(self.passagem(ref))

    def buscar(
        self, consulta: str, limite: int = 20, deslocamento: int = 0
    ) -> list[ResultadoBusca]:
        """Busca por todas as palavras (FTS5, sem acento); prefixo na última."""
        expr = _expressao_fts(consulta)
        if not expr:
            return []
        with closing(self._conectar()) as con:
            linhas = con.execute(
                "SELECT v.livro_id, v.capitulo, v.versiculo, "
                "snippet(versiculos_fts, 0, '<mark>', '</mark>', '…', 40) "
                "FROM versiculos_fts f JOIN versiculos v ON v.rowid = f.rowid "
                "WHERE versiculos_fts MATCH ? ORDER BY v.livro_id, v.capitulo, v.versiculo "
                "LIMIT ? OFFSET ?",
                (expr, limite, deslocamento),
            ).fetchall()
        return [ResultadoBusca(*linha) for linha in linhas]

    def contar_busca(self, consulta: str) -> int:
        expr = _expressao_fts(consulta)
        if not expr:
            return 0
        with closing(self._conectar()) as con:
            return con.execute(
                "SELECT COUNT(*) FROM versiculos_fts WHERE versiculos_fts MATCH ?", (expr,)
            ).fetchone()[0]

    def metadado(self, chave: str) -> str:
        with closing(self._conectar()) as con:
            linha = con.execute("SELECT valor FROM metadados WHERE chave=?", (chave,)).fetchone()
        return linha[0] if linha else ""

    def ultimo_versiculo(self, livro_id: int, capitulo: int) -> int | None:
        with closing(self._conectar()) as con:
            return con.execute(
                "SELECT MAX(versiculo) FROM versiculos WHERE livro_id=? AND capitulo=?",
                (livro_id, capitulo),
            ).fetchone()[0]
