"""Acesso ao banco de estudos e calendário (data/mana.sqlite).

O `web` e o `agendador` abrem o mesmo arquivo: modo WAL, `busy_timeout` e esquema
idempotente (qualquer um dos dois pode subir primeiro).
"""

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from mana.estudos.modelos import Estudo

ESQUEMA = """
CREATE TABLE IF NOT EXISTS calendario (
  data TEXT PRIMARY KEY,              -- AAAA-MM-DD
  ref TEXT NOT NULL,                  -- forma canônica (rom.8.28)
  ocasiao TEXT,                       -- código da ocasião especial, se houver
  origem TEXT NOT NULL DEFAULT 'gerado' CHECK (origem IN ('gerado', 'editado'))
);

CREATE TABLE IF NOT EXISTS estudos (
  data TEXT PRIMARY KEY,
  status TEXT NOT NULL CHECK (status IN ('ok', 'falhou')),
  ref TEXT NOT NULL,
  ocasiao TEXT,
  titulo TEXT,
  frase_do_dia TEXT,
  paragrafos TEXT NOT NULL DEFAULT '[]',        -- JSON
  complementar TEXT,
  palavras_chave TEXT NOT NULL DEFAULT '[]',    -- JSON
  provedor TEXT NOT NULL DEFAULT '',
  modelo TEXT NOT NULL DEFAULT '',
  versao_prompt TEXT NOT NULL DEFAULT '',
  tentativas INTEGER NOT NULL DEFAULT 0,
  revisado INTEGER NOT NULL DEFAULT 0,
  json_bruto TEXT,
  motivos TEXT NOT NULL DEFAULT '[]',           -- JSON
  tempo_s REAL NOT NULL DEFAULT 0,
  gerado_em TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class LinhaCalendario:
    data: date
    ref: str
    ocasiao: str | None = None
    origem: str = "gerado"


class RepositorioEstudos:
    def __init__(self, caminho: str | Path) -> None:
        self.caminho = Path(caminho)

    def _conectar(self) -> sqlite3.Connection:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.caminho, timeout=5)
        con.execute("PRAGMA busy_timeout = 5000")
        con.execute("PRAGMA journal_mode = WAL")
        con.executescript(ESQUEMA)
        return con

    # --- calendário

    def calendario(self, ini: date | None = None, fim: date | None = None) -> list[LinhaCalendario]:
        sql, args = "SELECT data, ref, ocasiao, origem FROM calendario", []
        filtros = []
        if ini:
            filtros.append("data >= ?")
            args.append(ini.isoformat())
        if fim:
            filtros.append("data <= ?")
            args.append(fim.isoformat())
        if filtros:
            sql += " WHERE " + " AND ".join(filtros)
        with closing(self._conectar()) as con:
            linhas = con.execute(sql + " ORDER BY data", args).fetchall()
        return [LinhaCalendario(date.fromisoformat(d), r, o, og) for d, r, o, og in linhas]

    def dia(self, data: date) -> LinhaCalendario | None:
        achadas = self.calendario(data, data)
        return achadas[0] if achadas else None

    def gravar(self, linhas: list[LinhaCalendario]) -> None:
        with closing(self._conectar()) as con, con:
            con.executemany(
                "INSERT INTO calendario (data, ref, ocasiao, origem) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(data) DO UPDATE SET ref=excluded.ref, ocasiao=excluded.ocasiao, "
                "origem=excluded.origem",
                [(x.data.isoformat(), x.ref, x.ocasiao, x.origem) for x in linhas],
            )

    def apagar_calendario(self, ini: date, fim: date) -> int:
        with closing(self._conectar()) as con, con:
            return con.execute(
                "DELETE FROM calendario WHERE data BETWEEN ? AND ?",
                (ini.isoformat(), fim.isoformat()),
            ).rowcount

    # --- estudos

    _COLUNAS = (
        "data, status, ref, ocasiao, titulo, frase_do_dia, paragrafos, complementar, "
        "palavras_chave, provedor, modelo, versao_prompt, tentativas, revisado, json_bruto, "
        "motivos, tempo_s, gerado_em"
    )

    @staticmethod
    def _estudo(linha: tuple) -> Estudo:
        (data, status, ref, ocasiao, titulo, frase, paragrafos, comp, palavras, provedor, modelo,
         versao, tentativas, revisado, bruto, motivos, tempo, gerado_em) = linha  # fmt: skip
        return Estudo(
            data=date.fromisoformat(data),
            status=status,
            ref=ref,
            ocasiao=ocasiao,
            titulo=titulo,
            frase_do_dia=frase,
            paragrafos=json.loads(paragrafos),
            complementar=comp,
            palavras_chave=json.loads(palavras),
            provedor=provedor,
            modelo=modelo,
            versao_prompt=versao,
            tentativas=tentativas,
            revisado=bool(revisado),
            json_bruto=bruto,
            motivos=json.loads(motivos),
            tempo_s=tempo,
            gerado_em=gerado_em,
        )

    def _estudos(self, onde: str = "", args: tuple = ()) -> list[Estudo]:
        with closing(self._conectar()) as con:
            linhas = con.execute(
                f"SELECT {self._COLUNAS} FROM estudos {onde} ORDER BY data", args
            ).fetchall()
        return [self._estudo(x) for x in linhas]

    def estudo(self, data: date) -> Estudo | None:
        achados = self._estudos("WHERE data = ?", (data.isoformat(),))
        return achados[0] if achados else None

    def estudos_entre(self, ini: date, fim: date) -> list[Estudo]:
        return self._estudos("WHERE data BETWEEN ? AND ?", (ini.isoformat(), fim.isoformat()))

    def recentes(self, antes_de: date, dias: int = 30) -> list[Estudo]:
        """Estudos publicáveis (status ok) dos `dias` anteriores a `antes_de`."""
        ini = antes_de - timedelta(days=dias)
        return [
            e for e in self.estudos_entre(ini, antes_de - timedelta(days=1)) if e.status == "ok"
        ]

    def do_modelo_nao_revisados(self, modelo: str) -> list[Estudo]:
        return self._estudos("WHERE modelo = ? AND revisado = 0", (modelo,))

    def gravar_estudo(self, e: Estudo) -> None:
        with closing(self._conectar()) as con, con:
            con.execute(
                f"INSERT OR REPLACE INTO estudos ({self._COLUNAS}) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    e.data.isoformat(), e.status, e.ref, e.ocasiao, e.titulo, e.frase_do_dia,
                    json.dumps(e.paragrafos, ensure_ascii=False), e.complementar,
                    json.dumps(e.palavras_chave, ensure_ascii=False), e.provedor, e.modelo,
                    e.versao_prompt, e.tentativas, int(e.revisado), e.json_bruto,
                    json.dumps(e.motivos, ensure_ascii=False), e.tempo_s, e.gerado_em.isoformat(),
                ),
            )  # fmt: skip

    def marcar_revisado(self, data: date, revisado: bool = True) -> bool:
        with closing(self._conectar()) as con, con:
            return (
                con.execute(
                    "UPDATE estudos SET revisado = ? WHERE data = ? AND status = 'ok'",
                    (int(revisado), data.isoformat()),
                ).rowcount
                == 1
            )
