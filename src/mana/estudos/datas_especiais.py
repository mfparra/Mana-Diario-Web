"""Datas fixas e móveis do calendário cristão e civil (AGENTS.md §6.1)."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from dateutil.easter import easter

CRISTA, CIVIL = 0, 1  # prioridade: calendário cristão vence o civil no mesmo dia


@dataclass(frozen=True)
class Ocasiao:
    codigo: str
    nome: str
    prioridade: int
    regra: Callable[[int], date]


def _fixa(mes: int, dia: int) -> Callable[[int], date]:
    return lambda ano: date(ano, mes, dia)


def _pascoa(dias: int) -> Callable[[int], date]:
    return lambda ano: easter(ano) + timedelta(days=dias)


def _domingo_a_partir(mes: int, dia: int, n: int = 1) -> Callable[[int], date]:
    """N-ésimo domingo a partir de mes/dia (inclusive)."""

    def regra(ano: int) -> date:
        inicio = date(ano, mes, dia)
        primeiro = inicio + timedelta(days=(6 - inicio.weekday()) % 7)
        return primeiro + timedelta(weeks=n - 1)

    return regra


OCASIOES: dict[str, Ocasiao] = {
    o.codigo: o
    for o in (
        Ocasiao("ano-novo", "Ano-Novo", CIVIL, _fixa(1, 1)),
        Ocasiao("epifania", "Epifania", CRISTA, _fixa(1, 6)),
        Ocasiao("cinzas", "Quarta-feira de Cinzas", CRISTA, _pascoa(-46)),
        Ocasiao("ramos", "Domingo de Ramos", CRISTA, _pascoa(-7)),
        Ocasiao("quinta-santa", "Quinta-feira Santa", CRISTA, _pascoa(-3)),
        Ocasiao("sexta-santa", "Sexta-feira Santa", CRISTA, _pascoa(-2)),
        Ocasiao("pascoa", "Páscoa", CRISTA, _pascoa(0)),
        Ocasiao("ascensao", "Ascensão", CRISTA, _pascoa(39)),
        Ocasiao("pentecostes", "Pentecostes", CRISTA, _pascoa(49)),
        Ocasiao("dia-das-maes", "Dia das Mães", CIVIL, _domingo_a_partir(5, 8)),
        Ocasiao("trindade", "Santíssima Trindade", CRISTA, _pascoa(56)),
        Ocasiao("corpus-christi", "Corpus Christi", CRISTA, _pascoa(60)),
        Ocasiao("dia-dos-pais", "Dia dos Pais", CIVIL, _domingo_a_partir(8, 8)),
        Ocasiao("advento", "1º Domingo do Advento", CRISTA, _domingo_a_partir(11, 27)),
        Ocasiao("vespera-natal", "Véspera de Natal", CRISTA, _fixa(12, 24)),
        Ocasiao("natal", "Natal", CRISTA, _fixa(12, 25)),
        Ocasiao("fim-de-ano", "Último dia do ano", CIVIL, _fixa(12, 31)),
    )
}


def interpretar_ativas(texto: str) -> frozenset[str]:
    """`OCASIOES_ATIVAS`: "todas" ou códigos separados por vírgula (desconhecido dá erro)."""
    texto = texto.strip().lower()
    if texto in ("", "todas"):
        return frozenset(OCASIOES)
    codigos = {c.strip() for c in texto.split(",") if c.strip()}
    desconhecidos = codigos - OCASIOES.keys()
    if desconhecidos:
        raise ValueError(f"Ocasiões desconhecidas em OCASIOES_ATIVAS: {sorted(desconhecidos)}")
    return frozenset(codigos)


def ocasioes_do_ano(ano: int, ativas: Iterable[str] | None = None) -> dict[date, Ocasiao]:
    """Data → ocasião do ano. Em caso de empate no mesmo dia, vale a de maior prioridade."""
    ativas = frozenset(OCASIOES if ativas is None else ativas)
    do_ano: dict[date, Ocasiao] = {}
    for o in OCASIOES.values():
        if o.codigo not in ativas:
            continue
        d = o.regra(ano)
        atual = do_ano.get(d)
        if atual is None or o.prioridade < atual.prioridade:
            do_ano[d] = o
    return dict(sorted(do_ano.items()))
