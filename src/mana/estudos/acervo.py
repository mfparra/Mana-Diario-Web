"""Acervo curado do versículo do dia: só referências (data/versiculos.yaml)."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from mana.biblia.referencias import Referencia, canonico, livro_por_id, parse_referencia
from mana.biblia.repositorio import RepositorioBiblia
from mana.estudos.datas_especiais import OCASIOES

ACERVO_YAML = Path(__file__).resolve().parents[3] / "data" / "versiculos.yaml"
MIN_ENTRADAS = 1100
MIN_POR_OCASIAO = 3
MAX_VERSICULOS = 3


class ErroAcervo(Exception):
    pass


@dataclass(frozen=True)
class Entrada:
    ref: Referencia
    temas: tuple[str, ...]
    ocasioes: tuple[str, ...] = ()

    @property
    def chave(self) -> str:
        return canonico(self.ref)

    @property
    def livro_id(self) -> int:
        return self.ref.trechos[0].livro_id

    @property
    def testamento(self) -> str:
        return livro_por_id(self.livro_id).testamento

    @property
    def versiculos(self) -> frozenset[tuple[int, int, int]]:
        """(livro, capítulo, versículo) de cada versículo; só para entradas de um capítulo."""
        return frozenset(
            (t.livro_id, t.cap_ini, v)
            for t in self.ref.trechos
            for v in range(t.vers_ini or 0, (t.vers_fim or 0) + 1)
        )


@dataclass
class Acervo:
    temas: tuple[str, ...]
    entradas: list[Entrada] = field(default_factory=list)
    problemas: list[str] = field(default_factory=list)  # erros de leitura (referência ilegível...)


def carregar(caminho: Path = ACERVO_YAML) -> Acervo:
    bruto = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    temas = tuple(bruto.get("temas") or ())
    acervo = Acervo(temas=temas)
    for i, item in enumerate(bruto.get("versiculos") or [], start=1):
        texto = str(item.get("ref", ""))
        ref = parse_referencia(texto)
        if ref is None:
            acervo.problemas.append(f"entrada {i}: referência ilegível {texto!r}")
            continue
        acervo.entradas.append(
            Entrada(
                ref=ref,
                temas=tuple(item.get("temas") or ()),
                ocasioes=tuple(item.get("ocasioes") or ()),
            )
        )
    return acervo


def validar(
    acervo: Acervo,
    biblia: RepositorioBiblia,
    ativas: frozenset[str],
    exigir_minimos: bool = False,
) -> list[str]:
    """Problemas encontrados (lista vazia = acervo íntegro).

    Com `exigir_minimos`, exige também ≥ 1.100 entradas e ≥ 3 por ocasião ativa.
    """
    erros = list(acervo.problemas)
    usados: dict[tuple[int, int, int], str] = {}
    chaves: set[str] = set()
    for e in acervo.entradas:
        nome = e.chave
        if nome in chaves:
            erros.append(f"{nome}: duplicada")
        chaves.add(nome)
        if not biblia.existe(e.ref):
            erros.append(f"{nome}: não existe na Bíblia local")
            continue
        capitulos = {(t.livro_id, t.cap_ini) for t in e.ref.trechos}
        if len(capitulos) != 1 or any(
            t.vers_ini is None or t.cap_ini != t.cap_fim for t in e.ref.trechos
        ):
            erros.append(f"{nome}: deve ser de versículos de um só capítulo")
            continue
        if not 1 <= len(e.versiculos) <= MAX_VERSICULOS:
            erros.append(f"{nome}: {len(e.versiculos)} versículos (máximo {MAX_VERSICULOS})")
        if not 1 <= len(e.temas) <= 3:
            erros.append(f"{nome}: {len(e.temas)} temas (esperado de 1 a 3)")
        for tema in e.temas:
            if tema not in acervo.temas:
                erros.append(f"{nome}: tema fora da lista fechada: {tema!r}")
        if len(set(e.temas)) != len(e.temas):
            erros.append(f"{nome}: tema repetido")
        for oc in e.ocasioes:
            if oc not in OCASIOES:
                erros.append(f"{nome}: ocasião desconhecida: {oc!r}")
        for v in e.versiculos:
            if v in usados and usados[v] != nome:
                erros.append(f"{nome}: sobrepõe {usados[v]}")
                break
            usados[v] = nome
    if len(set(acervo.temas)) != len(acervo.temas):
        erros.append("lista de temas com repetição")
    if exigir_minimos:
        if len(acervo.entradas) < MIN_ENTRADAS:
            erros.append(f"{len(acervo.entradas)} entradas (mínimo {MIN_ENTRADAS})")
        for codigo in sorted(ativas):
            n = sum(codigo in e.ocasioes for e in acervo.entradas)
            if n < MIN_POR_OCASIAO:
                erros.append(f"ocasião {codigo}: {n} entradas (mínimo {MIN_POR_OCASIAO})")
    return erros
