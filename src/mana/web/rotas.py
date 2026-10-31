"""Rotas do site."""

from functools import cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from mana.biblia.referencias import (
    canonico,
    formatar,
    parse_canonico,
    parse_referencia,
    url_referencia,
)
from mana.biblia.repositorio import LIMITE_VERSICULOS, RepositorioBiblia
from mana.config import obter_configuracao

router = APIRouter()

SIGLA_EDICAO = "BLIVRE"


@cache
def _repositorio() -> RepositorioBiblia:
    return RepositorioBiblia(obter_configuracao().biblia_db)


def repositorio_biblia() -> RepositorioBiblia:
    """Dependência do FastAPI (substituível nos testes)."""
    return _repositorio()


@router.get("/saude")
def saude() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/passagem")
def passagem(
    ref: Annotated[str, Query(min_length=1, max_length=80)],
    repo: Annotated[RepositorioBiblia, Depends(repositorio_biblia)],
) -> dict:
    """Texto de uma passagem, para o popover. Aceita `rom.8.28` ou `Romanos 8:28`."""
    referencia = parse_canonico(ref) or parse_referencia(ref)
    if referencia is None:
        raise HTTPException(400, "Referência inválida")
    if not repo.existe(referencia):
        raise HTTPException(404, "Passagem não encontrada")
    versiculos = repo.passagem(referencia)
    if len(versiculos) > LIMITE_VERSICULOS:
        raise HTTPException(400, "Passagem longa demais")
    return {
        "referencia": formatar(referencia),
        "ref": canonico(referencia),
        "url": url_referencia(referencia),
        "edicao": SIGLA_EDICAO,
        "versiculos": [
            {"capitulo": v.capitulo, "numero": v.numero, "texto": v.texto} for v in versiculos
        ],
    }
