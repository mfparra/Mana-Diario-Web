"""CLI do Maná Diário (`uv run mana ...`)."""

import logging

import typer

from mana.config import obter_configuracao

app = typer.Typer(help="Maná Diário", no_args_is_help=True)
biblia = typer.Typer(help="Bíblia local.", no_args_is_help=True)
llm = typer.Typer(help="Provedor de LLM.", no_args_is_help=True)
app.add_typer(biblia, name="biblia")
app.add_typer(llm, name="llm")


@biblia.command("baixar")
def biblia_baixar() -> None:
    """Baixa a Bíblia Livre (Fase 2)."""
    typer.echo("Ainda não implementado.")


@biblia.command("importar")
def biblia_importar() -> None:
    """Converte a Bíblia para SQLite (Fase 2)."""
    typer.echo("Ainda não implementado.")


@llm.command("testar")
def llm_testar() -> None:
    """Chamada mínima ao provedor configurado (Fase 1)."""
    typer.echo("Ainda não implementado.")


@app.command()
def gerar(data: str = "hoje") -> None:
    """Gera o estudo do dia (Fase 5)."""
    typer.echo("Ainda não implementado.")


@app.command()
def servir() -> None:
    """Sobe o site."""
    import uvicorn

    cfg = obter_configuracao()
    uvicorn.run("mana.web.app:app", host=cfg.host, port=cfg.porta)


@app.command()
def agendador() -> None:
    """Laço diário (gerar, backup, calendário)."""
    from mana import agendador as ag

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    ag.executar()
