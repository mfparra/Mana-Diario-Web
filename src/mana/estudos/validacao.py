"""Regras de conteúdo do estudo gerado pela LLM (docs/LLM.md §5).

O esquema (tamanhos, quantidades) é checado pelo Pydantic em `EstudoGerado`; aqui ficam as
regras que dependem da Bíblia local e do histórico.
"""

import re
from dataclasses import dataclass, field

from mana.biblia.referencias import (
    Referencia,
    canonico,
    encontrar_referencias,
    formatar,
    parse_referencia,
    referencias_invalidas,
)
from mana.biblia.repositorio import RepositorioBiblia
from mana.estudos.modelos import EstudoGerado

MAX_PALAVRAS_TITULO = 6
MAX_PALAVRAS_FRASE = 18
MIN_PALAVRAS_TOTAL, MAX_PALAVRAS_TOTAL = 220, 420
MAX_PALAVRAS_ASPAS = 6
MAX_VERSICULOS_COMPLEMENTAR = 6
PALAVRAS_COPIA = 8  # 8 palavras seguidas iguais a um versículo = texto bíblico "citado"

_ASPAS = re.compile(r"[“\"«]([^”\"»]+)[”\"»]")


@dataclass
class Historico:
    """O que já foi usado, para não repetir (últimos 30 dias)."""

    complementares: set[str] = field(default_factory=set)  # forma canônica
    palavras_chave: set[str] = field(default_factory=set)


@dataclass
class Resultado:
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    complementar: Referencia | None = None
    palavras_chave: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.erros


def _palavras(texto: str) -> int:
    return len(texto.split())


def _versiculos(ref: Referencia, biblia: RepositorioBiblia) -> set[tuple[int, int, int]]:
    return {(t.livro_id, v.capitulo, v.numero) for t in ref.trechos for v in biblia.versiculos(t)}


def _escolher_complementar(
    g: EstudoGerado, principal: Referencia, historico: Historico, biblia: RepositorioBiblia
) -> tuple[Referencia | None, list[str]]:
    """Primeira candidata válida (existe, não sobrepõe o principal, não é recente, ≤ 6 versos)."""
    do_principal = _versiculos(principal, biblia)
    motivos: list[str] = []
    for texto in g.complementares:
        ref = parse_referencia(texto)
        if ref is None or not biblia.existe(ref):
            motivos.append(f"{texto!r} não existe")
            continue
        versos = _versiculos(ref, biblia)
        if versos & do_principal:
            motivos.append(f"{texto!r} repete o versículo do dia")
        elif canonico(ref) in historico.complementares:
            motivos.append(f"{texto!r} foi usada nos últimos 30 dias")
        elif len(versos) > MAX_VERSICULOS_COMPLEMENTAR:
            motivos.append(f"{texto!r} tem mais de {MAX_VERSICULOS_COMPLEMENTAR} versículos")
        else:
            return ref, motivos
    return None, motivos


def validar(
    g: EstudoGerado, principal: Referencia, historico: Historico, biblia: RepositorioBiblia
) -> Resultado:
    r = Resultado()
    if _palavras(g.titulo) > MAX_PALAVRAS_TITULO:
        r.erros.append(f"título com mais de {MAX_PALAVRAS_TITULO} palavras")
    if _palavras(g.frase_do_dia) > MAX_PALAVRAS_FRASE:
        r.erros.append(f"frase do dia com mais de {MAX_PALAVRAS_FRASE} palavras")
    total = sum(_palavras(p) for p in g.paragrafos)
    if not MIN_PALAVRAS_TOTAL <= total <= MAX_PALAVRAS_TOTAL:
        r.erros.append(
            f"estudo com {total} palavras (deve ter entre {MIN_PALAVRAS_TOTAL} e "
            f"{MAX_PALAVRAS_TOTAL})"
        )

    complementar, motivos = _escolher_complementar(g, principal, historico, biblia)
    if complementar is None:
        r.erros.append("nenhuma referência complementar válida: " + "; ".join(motivos))
    r.complementar = complementar

    texto = " ".join([g.titulo, g.frase_do_dia, *g.paragrafos])
    for invalida in referencias_invalidas(texto):
        r.erros.append(f"a referência {invalida!r} não existe na Bíblia")
    for achada in encontrar_referencias(texto):
        if not biblia.existe(achada.referencia):
            r.erros.append(f"a referência {formatar(achada.referencia)!r} não existe na Bíblia")

    for citado in _ASPAS.findall(texto):
        if _palavras(citado) > MAX_PALAVRAS_ASPAS:
            r.erros.append(
                f"citação longa entre aspas ({_palavras(citado)} palavras): não cite o texto "
                "bíblico, só a referência"
            )
    copias = biblia.frases_na_biblia(texto, PALAVRAS_COPIA)
    if copias:
        r.erros.append(
            f"trecho idêntico ao texto bíblico (…{copias[0]}…): não escreva versículos, "
            "só a referência"
        )

    vistas: set[str] = set()
    for palavra in (p.strip().lower() for p in g.palavras_chave):
        if palavra and palavra not in vistas:
            vistas.add(palavra)
            r.palavras_chave.append(palavra)
    if len(r.palavras_chave) < 3:
        r.erros.append("menos de 3 palavras-chave diferentes")
    repetidas = sorted(set(r.palavras_chave) & historico.palavras_chave)
    if repetidas:
        r.avisos.append("palavras-chave já usadas recentemente: " + ", ".join(repetidas))
    return r
