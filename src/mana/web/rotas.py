"""Rotas do site."""

import re
from functools import cache
from html import escape
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from mana.biblia.referencias import (
    Livro,
    canonico,
    formatar,
    livro_por_id,
    livros,
    parse_canonico,
    parse_referencia,
    url_referencia,
)
from mana.biblia.repositorio import LIMITE_VERSICULOS, RepositorioBiblia
from mana.config import obter_configuracao

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

SIGLA_EDICAO = "BLIVRE"
POR_PAGINA = 20


@cache
def _repositorio() -> RepositorioBiblia:
    return RepositorioBiblia(obter_configuracao().biblia_db)


def repositorio_biblia() -> RepositorioBiblia:
    """Dependência do FastAPI (substituível nos testes)."""
    return _repositorio()


Repo = Annotated[RepositorioBiblia, Depends(repositorio_biblia)]


def pagina(request: Request, repo: RepositorioBiblia, nome: str, status: int = 200, **contexto):
    """Renderiza um template com o contexto comum (crédito da edição, modo de teste)."""
    contexto.setdefault("credito", repo.metadado("credito"))
    contexto.setdefault("modo_teste", obter_configuracao().modo_teste)
    return templates.TemplateResponse(request, nome, contexto, status_code=status)


@router.get("/saude")
def saude() -> dict[str, str]:
    return {"status": "ok"}


# --------------------------------------------------------------------------- API


@router.get("/api/passagem")
def passagem(ref: Annotated[str, Query(min_length=1, max_length=80)], repo: Repo) -> dict:
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


# ------------------------------------------------------------------------ Bíblia


def _livro_por_slug(slug: str) -> Livro | None:
    return next((livro for livro in livros() if livro.slug == slug), None)


def _vizinho(livro: Livro, capitulo: int, passo: int) -> dict | None:
    """Capítulo anterior (-1) ou seguinte (+1), atravessando de um livro para outro."""
    novo = capitulo + passo
    if 1 <= novo <= livro.capitulos:
        return {"url": f"/biblia/{livro.slug}/{novo}", "rotulo": f"{livro.nome} {novo}"}
    outro = livro.id + passo
    if outro < 1 or outro > len(livros()):
        return None
    vizinho = livro_por_id(outro)
    cap = vizinho.capitulos if passo < 0 else 1
    return {"url": f"/biblia/{vizinho.slug}/{cap}", "rotulo": f"{vizinho.nome} {cap}"}


def _faixa_destacada(texto: str | None) -> range:
    m = re.fullmatch(r"(\d{1,3})(?:-(\d{1,3}))?", texto or "")
    if not m:
        return range(0)
    ini = int(m[1])
    return range(ini, int(m[2] or ini) + 1)


def _marcar(snippet: str) -> str:
    """Escapa o trecho da busca e mantém só os <mark> que o FTS5 colocou."""
    return escape(snippet).replace("&lt;mark&gt;", "<mark>").replace("&lt;/mark&gt;", "</mark>")


@router.get("/biblia", response_class=HTMLResponse)
def biblia_livros(request: Request, repo: Repo):
    testamentos = [
        {"nome": nome, "livros": [x for x in livros() if x.testamento == sigla]}
        for nome, sigla in (("Antigo Testamento", "AT"), ("Novo Testamento", "NT"))
    ]
    return pagina(request, repo, "biblia_livros.html", secao="biblia", testamentos=testamentos)


@router.get("/biblia/ir")
def biblia_ir(livro: str = "", cap: int = 1):
    """Destino do seletor de livro/capítulo (funciona sem JavaScript)."""
    alvo = _livro_por_slug(livro)
    if alvo is None:
        return RedirectResponse("/biblia", status_code=303)
    return RedirectResponse(f"/biblia/{alvo.slug}/{min(max(cap, 1), alvo.capitulos)}", 303)


@router.get("/biblia/busca", response_class=HTMLResponse)
def biblia_busca(request: Request, repo: Repo, q: str = "", p: int = 1):
    q = q.strip()[:100]
    p = max(p, 1)
    total = repo.contar_busca(q) if q else 0
    resultados = []
    for r in repo.buscar(q, POR_PAGINA, (p - 1) * POR_PAGINA) if q else []:
        livro = livro_por_id(r.livro_id)
        resultados.append(
            {
                "rotulo": f"{livro.nome} {r.capitulo}.{r.numero}",
                "url": f"/biblia/{livro.slug}/{r.capitulo}?destacar={r.numero}#v{r.numero}",
                "trecho": _marcar(r.trecho),
            }
        )

    def link(n: int) -> str:
        return "/biblia/busca?" + urlencode({"q": q, "p": n})

    return pagina(
        request,
        repo,
        "biblia_busca.html",
        secao="biblia",
        q=q,
        total=total,
        resultados=resultados,
        pagina_anterior=link(p - 1) if p > 1 else None,
        pagina_proxima=link(p + 1) if p * POR_PAGINA < total else None,
    )


@router.get("/biblia/{slug}", response_class=RedirectResponse)
def biblia_livro(slug: str):
    if _livro_por_slug(slug) is None:
        raise HTTPException(404, "Livro não encontrado.")
    return RedirectResponse(f"/biblia/{slug}/1", status_code=307)


@router.get("/biblia/{slug}/{capitulo}", response_class=HTMLResponse)
def biblia_capitulo(
    request: Request, repo: Repo, slug: str, capitulo: int, destacar: str | None = None
):
    livro = _livro_por_slug(slug)
    if livro is None or not 1 <= capitulo <= livro.capitulos:
        raise HTTPException(404, "Esse capítulo não existe na Bíblia.")
    faixa = _faixa_destacada(destacar)
    versiculos = [
        {"numero": v.numero, "texto": v.texto, "destacado": v.numero in faixa}
        for v in repo.capitulo(livro.id, capitulo)
    ]
    return pagina(
        request,
        repo,
        "biblia_capitulo.html",
        secao="biblia",
        livro=livro,
        capitulo=capitulo,
        versiculos=versiculos,
        todos_livros=livros(),
        anterior=_vizinho(livro, capitulo, -1),
        proximo=_vizinho(livro, capitulo, +1),
    )
