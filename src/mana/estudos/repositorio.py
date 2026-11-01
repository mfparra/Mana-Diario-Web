"""Acesso ao banco de estudos e calendário (data/mana.sqlite).

O `web` e o `agendador` abrem o mesmo arquivo: modo WAL, `busy_timeout` e esquema
idempotente (qualquer um dos dois pode subir primeiro).
"""

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS calendario (
  data TEXT PRIMARY KEY,              -- AAAA-MM-DD
  ref TEXT NOT NULL,                  -- forma canônica (rom.8.28)
  ocasiao TEXT,                       -- código da ocasião especial, se houver
  origem TEXT NOT NULL DEFAULT 'gerado' CHECK (origem IN ('gerado', 'editado'))
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
