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
    """Chamada mínima ao provedor configurado: mostra latência e modelo."""
    import asyncio

    from mana.llm.base import ErroLLM
    from mana.llm.fabrica import criar_cliente

    esquema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["resposta"],
        "properties": {"resposta": {"type": "string", "maxLength": 40}},
    }
    cliente = criar_cliente()
    try:
        r = asyncio.run(
            cliente.gerar_json(
                "Responda somente em JSON.",
                'Diga "olá" em português no campo "resposta".',
                esquema,
                temperatura=0.2,
                max_tokens=200,
            )
        )
    except ErroLLM as e:
        typer.secho(f"Falhou: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e
    typer.echo(
        f"OK provedor={cliente.provedor} modelo={r.modelo} "
        f"latência={r.latencia_s:.1f}s tokens={r.tokens_saida} resposta={r.dados}"
    )


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
