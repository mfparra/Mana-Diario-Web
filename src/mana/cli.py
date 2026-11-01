"""CLI do Maná Diário (`uv run mana ...`)."""

import logging
from pathlib import Path

import typer

from mana.config import obter_configuracao

app = typer.Typer(help="Maná Diário", no_args_is_help=True)
biblia = typer.Typer(help="Bíblia local.", no_args_is_help=True)
llm = typer.Typer(help="Provedor de LLM.", no_args_is_help=True)
app.add_typer(biblia, name="biblia")
acervo = typer.Typer(help="Acervo curado de versículos.", no_args_is_help=True)
calendario = typer.Typer(help="Calendário anual do versículo do dia.", no_args_is_help=True)
app.add_typer(llm, name="llm")
app.add_typer(acervo, name="acervo")
app.add_typer(calendario, name="calendario")


@biblia.command("baixar")
def biblia_baixar() -> None:
    """Baixa a Bíblia Livre (eBible, USFX) para data/biblia/raw/."""
    from mana.biblia import importar as imp

    xml = imp.baixar(Path(obter_configuracao().biblia_db).parent / "raw")
    typer.echo(f"Baixado e extraído: {xml}")


@biblia.command("importar")
def biblia_importar() -> None:
    """Converte a Bíblia para SQLite e valida a integridade."""
    from mana.biblia import importar as imp

    destino = Path(obter_configuracao().biblia_db)
    xml = destino.parent / "raw" / "usfx" / imp.NOME_XML
    try:
        total = imp.importar(xml, Path("data/livros.json"), destino)
    except (imp.ErroImportacao, FileNotFoundError) as e:
        typer.secho(f"Falhou: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e
    typer.echo(f"Importados {total} versículos em {destino}")


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


@acervo.command("validar")
def acervo_validar(
    minimos: bool = typer.Option(True, "--minimos/--sem-minimos", help="Exige ≥ 1.100 entradas."),
) -> None:
    """Confere todas as referências de data/versiculos.yaml."""
    from collections import Counter

    from mana.biblia.referencias import livro_por_id
    from mana.biblia.repositorio import RepositorioBiblia
    from mana.estudos import acervo as ac
    from mana.estudos.datas_especiais import interpretar_ativas

    cfg = obter_configuracao()
    dados = ac.carregar()
    ativas = interpretar_ativas(cfg.ocasioes_ativas)
    erros = ac.validar(dados, RepositorioBiblia(cfg.biblia_db), ativas, exigir_minimos=minimos)
    n = len(dados.entradas)
    por_livro = Counter(livro_por_id(e.livro_id).nome for e in dados.entradas)
    at = sum(e.testamento == "AT" for e in dados.entradas)
    sp = sum(e.livro_id in (19, 20) for e in dados.entradas)
    typer.echo(
        f"{n} entradas | AT {at} / NT {n - at} | Salmos+Provérbios {sp} | {len(por_livro)} livros"
    )
    por_ocasiao = Counter(o for e in dados.entradas for o in e.ocasioes)
    typer.echo("Ocasiões: " + ", ".join(f"{c}={por_ocasiao[c]}" for c in sorted(ativas)))
    for erro in erros:
        typer.secho(f"  ✗ {erro}", fg=typer.colors.RED, err=True)
    if erros:
        typer.secho(f"{len(erros)} problema(s).", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    typer.echo("Acervo íntegro.")


@calendario.command("gerar")
def calendario_gerar(
    ano: int = typer.Option(..., help="Ano do calendário."),
    refazer: bool = typer.Option(False, help="Refaz os dias futuros que já existem."),
) -> None:
    """Monta o calendário do ano (grava no banco e exporta o YAML para revisão)."""
    from datetime import date, timedelta

    from mana import tempo
    from mana.estudos import acervo as ac
    from mana.estudos import calendario as cal
    from mana.estudos.datas_especiais import interpretar_ativas
    from mana.estudos.repositorio import RepositorioEstudos

    cfg = obter_configuracao()
    hoje = tempo.hoje()
    if ano < hoje.year:
        typer.secho("Esse ano já passou.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    repo = RepositorioEstudos(cfg.mana_db)
    primeiro = date(ano, 1, 1)
    if refazer:
        apagados = repo.apagar_calendario(
            max(primeiro, hoje + timedelta(days=1)), date(ano, 12, 31)
        )
        typer.echo(f"{apagados} dia(s) futuro(s) apagado(s) para refazer.")
    try:
        resultado = cal.gerar(
            ano,
            ac.carregar(),
            interpretar_ativas(cfg.ocasioes_ativas),
            repo.calendario(),
            inicio=max(primeiro, hoje) if ano == hoje.year else primeiro,
        )
    except cal.ErroCalendario as e:
        typer.secho(f"Falhou: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e
    repo.gravar(resultado.linhas)
    do_ano = repo.calendario(primeiro, date(ano, 12, 31))
    destino = Path(cfg.calendarios_dir) / f"{ano}.yaml"
    cal.exportar_yaml(ano, do_ano, destino)
    est = cal.estatisticas(do_ano)
    typer.echo(
        f"{len(resultado.linhas)} dia(s) novo(s); {est['dias']} no ano | "
        f"AT {est['pct_at']:.0f}% | Salmos+Provérbios {est['pct_salmos_proverbios']:.0f}% | "
        f"{destino}"
    )
    for aviso in resultado.avisos:
        typer.secho(f"  aviso: {aviso}", fg=typer.colors.YELLOW)


@calendario.command("importar")
def calendario_importar(ano: int = typer.Option(..., help="Ano do calendário.")) -> None:
    """Aplica as edições feitas no YAML do ano."""
    from mana import tempo
    from mana.biblia.repositorio import RepositorioBiblia
    from mana.estudos import acervo as ac
    from mana.estudos import calendario as cal
    from mana.estudos.repositorio import RepositorioEstudos

    cfg = obter_configuracao()
    caminho = Path(cfg.calendarios_dir) / f"{ano}.yaml"
    if not caminho.exists():
        typer.secho(f"Não encontrei {caminho}.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    rel = cal.importar_yaml(
        ano,
        caminho,
        RepositorioEstudos(cfg.mana_db),
        RepositorioBiblia(cfg.biblia_db),
        ac.carregar(),
        tempo.hoje(),
    )
    for erro in rel.erros:
        typer.secho(f"  ✗ {erro}", fg=typer.colors.RED, err=True)
    if rel.erros:
        typer.secho("Nada foi gravado.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    typer.echo(f"{len(rel.alterados)} dia(s) alterado(s).")
    for aviso in rel.avisos:
        typer.secho(f"  aviso: {aviso}", fg=typer.colors.YELLOW)


def _data_cli(texto: str):
    from datetime import date

    from mana import tempo

    try:
        return tempo.hoje() if texto == "hoje" else date.fromisoformat(texto)
    except ValueError as e:
        raise typer.BadParameter(f"use 'hoje' ou AAAA-MM-DD, não {texto!r}") from e


@app.command()
def gerar(
    data: str = typer.Option("hoje", help="'hoje' ou AAAA-MM-DD."),
    proximos: int = typer.Option(0, help="Além da data, gera também os N dias seguintes."),
    forcar: bool = typer.Option(False, help="Refaz mesmo que já exista estudo válido."),
    regerar_modelo: str = typer.Option(
        "", help="Refaz os estudos não revisados feitos por este modelo (ignora --data)."
    ),
) -> None:
    """Gera (ou regenera) o estudo do dia."""
    import asyncio
    from datetime import timedelta

    from mana.biblia.repositorio import RepositorioBiblia
    from mana.estudos.gerador import Gerador, SemCalendario
    from mana.estudos.repositorio import RepositorioEstudos
    from mana.llm.fabrica import criar_cliente

    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    cfg = obter_configuracao()
    estudos = RepositorioEstudos(cfg.mana_db)
    if regerar_modelo:
        datas = [e.data for e in estudos.do_modelo_nao_revisados(regerar_modelo)]
        forcar = True
        if not datas:
            typer.echo(f"Nenhum estudo não revisado do modelo {regerar_modelo!r}.")
            return
    else:
        inicio = _data_cli(data)
        datas = [inicio + timedelta(days=i) for i in range(proximos + 1)]
    gerador = Gerador(criar_cliente(cfg), RepositorioBiblia(cfg.biblia_db), estudos, cfg)

    async def rodar() -> int:
        falhas = 0
        for d in datas:
            try:
                e = await gerador.gerar_dia(d, forcar=forcar)
            except SemCalendario as erro:
                typer.secho(f"{d}: {erro}", fg=typer.colors.RED, err=True)
                falhas += 1
                continue
            if e.status == "ok":
                typer.echo(f"{d} ok  [{e.tentativas} tentativa(s), {e.tempo_s:.0f}s] {e.titulo}")
            else:
                falhas += 1
                typer.secho(
                    f"{d} FALHOU: {e.motivos[-1] if e.motivos else '?'}", fg=typer.colors.RED
                )
        return falhas

    if asyncio.run(rodar()):
        raise typer.Exit(1)


@app.command()
def revisar(
    data: str = typer.Option(..., help="'hoje' ou AAAA-MM-DD."),
    desmarcar: bool = typer.Option(False, help="Tira a marca de revisado."),
) -> None:
    """Marca o estudo de uma data como revisado (ele deixa de ser refeito por --regerar-modelo)."""
    from mana.estudos.repositorio import RepositorioEstudos

    d = _data_cli(data)
    if not RepositorioEstudos(obter_configuracao().mana_db).marcar_revisado(d, not desmarcar):
        typer.secho(f"Não há estudo válido em {d}.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    typer.echo(f"{d}: " + ("revisão desmarcada." if desmarcar else "marcado como revisado."))


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
