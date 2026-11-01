"""Páginas dos estudos: o do dia, os de datas passadas e o arquivo."""

from dataclasses import dataclass
from datetime import date
from html import escape

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from mana import tempo
from mana.biblia.referencias import (
    link_referencia,
    linkar_referencias,
    parse_canonico,
)
from mana.biblia.repositorio import RepositorioBiblia
from mana.estudos.datas_especiais import OCASIOES
from mana.estudos.modelos import Estudo
from mana.estudos.repositorio import RepositorioEstudos
from mana.web.rotas import Repo, RepoEstudos, pagina

router = APIRouter()

MESES_ABREV = ("JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ")
MESES_NOME = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
    "outubro", "novembro", "dezembro",
)  # fmt: skip


@dataclass
class Resumo:
    data: date
    url: str
    titulo: str
    referencia_html: str


def _total_dias(ano: int) -> int:
    return 366 if (ano % 4 == 0 and (ano % 100 != 0 or ano % 400 == 0)) else 365


def _visao(
    data: date,
    estudo: Estudo | None,
    ref_canonica: str | None,
    ocasiao: str | None,
    biblia: RepositorioBiblia,
    estudos: RepositorioEstudos,
    hoje: date,
) -> dict:
    """Tudo o que o template precisa, já pronto (nada de lógica nos templates)."""
    ref = parse_canonico(ref_canonica) if ref_canonica else None
    pronto = estudo is not None and estudo.status == "ok"
    visao: dict = {
        "data": data,
        "dia": data.day,
        "mes": MESES_ABREV[data.month - 1],
        "mes_nome": MESES_NOME[data.month - 1],
        "ocasiao": OCASIOES[ocasiao].nome.upper() if ocasiao in OCASIOES else None,
        "numero": data.timetuple().tm_yday,
        "total_dias": _total_dias(data.year),
        "pronto": pronto,
        "versiculo": " ".join(v.texto for v in biblia.passagem(ref)) if ref else None,
        "ref_html": link_referencia(ref) if ref else None,
    }
    anterior = estudos.vizinho(data, hoje, anterior=True)
    seguinte = estudos.vizinho(data, hoje, anterior=False)
    visao["anterior"] = f"/estudo/{anterior}" if anterior else None
    visao["seguinte"] = f"/estudo/{seguinte}" if seguinte else None
    if pronto:
        visao.update(
            titulo=estudo.titulo,
            frase=estudo.frase_do_dia,
            paragrafos=[linkar_referencias(p, existe=biblia.existe) for p in estudo.paragrafos],
            complementar_html=link_referencia(parse_canonico(estudo.complementar)),
            palavras_chave=estudo.palavras_chave,
        )
    return visao


def _pagina_do_dia(
    request: Request, data: date, biblia: RepositorioBiblia, estudos: RepositorioEstudos
):
    hoje = tempo.hoje()
    estudo = estudos.estudo(data)
    dia = estudos.dia(data)
    if estudo is None and dia is None and data != hoje:
        raise HTTPException(404, "Não há estudo para essa data.")
    ref = dia.ref if dia else (estudo.ref if estudo else None)
    ocasiao = dia.ocasiao if dia else (estudo.ocasiao if estudo else None)
    visao = _visao(data, estudo, ref, ocasiao, biblia, estudos, hoje)
    caminho = "/" if data == hoje else f"/estudo/{data}"
    return pagina(
        request,
        biblia,
        "estudo.html",
        secao="estudo",
        eh_hoje=data == hoje,
        caminho=caminho,
        **visao,
    )


@router.get("/", response_class=HTMLResponse)
def estudo_de_hoje(request: Request, biblia: Repo, estudos: RepoEstudos):
    return _pagina_do_dia(request, tempo.hoje(), biblia, estudos)


@router.get("/estudo/{data}", response_class=HTMLResponse)
def estudo_da_data(request: Request, data: str, biblia: Repo, estudos: RepoEstudos):
    try:
        alvo = date.fromisoformat(data)
    except ValueError:
        raise HTTPException(404, "Data inválida.") from None
    if alvo > tempo.hoje():  # estudos futuros nunca aparecem no site público
        raise HTTPException(404, "Esse estudo ainda não foi publicado.")
    return _pagina_do_dia(request, alvo, biblia, estudos)


@router.get("/estudos", response_class=HTMLResponse)
def arquivo(request: Request, biblia: Repo, estudos: RepoEstudos):
    meses: dict[tuple[int, int], list[Resumo]] = {}
    for e in reversed(estudos.publicados(tempo.hoje())):
        meses.setdefault((e.data.year, e.data.month), []).append(
            Resumo(
                e.data,
                f"/estudo/{e.data}",
                escape(e.titulo or ""),
                link_referencia(parse_canonico(e.ref)),
            )
        )
    grupos = [
        {"titulo": f"{MESES_NOME[mes - 1].capitalize()} de {ano}", "estudos": itens}
        for (ano, mes), itens in meses.items()
    ]
    return pagina(request, biblia, "arquivo.html", secao="arquivo", grupos=grupos)
