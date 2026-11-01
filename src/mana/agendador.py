"""Laço diário (AGENTS.md §6): recuperação ao iniciar; depois, todo dia às 00:10 (fuso do site)
pré-gera 7 dias à frente, faz backup do banco e, em dezembro, monta o calendário do ano seguinte.

Se o estudo de hoje não ficar pronto (ex.: a LLM caiu), tenta de novo a cada 30 minutos.
Encerra limpo com SIGTERM/SIGINT.
"""

import asyncio
import logging
import signal
from collections.abc import Awaitable, Callable
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from mana.biblia.repositorio import RepositorioBiblia
from mana.config import Configuracao
from mana.estudos import calendario as cal
from mana.estudos.acervo import carregar as carregar_acervo
from mana.estudos.datas_especiais import interpretar_ativas
from mana.estudos.gerador import SemCalendario
from mana.estudos.modelos import Estudo
from mana.estudos.repositorio import RepositorioEstudos

log = logging.getLogger("mana.agendador")

HORA_DA_RODADA = time(0, 10)
DIAS_A_FRENTE = 7
BACKUPS_GUARDADOS = 14
NOVA_TENTATIVA = timedelta(minutes=30)


def proxima_rodada(agora: datetime) -> datetime:
    """Próximo 00:10 estritamente depois de `agora` (no mesmo fuso)."""
    candidata = datetime.combine(agora.date(), HORA_DA_RODADA, tzinfo=agora.tzinfo)
    return candidata if candidata > agora else candidata + timedelta(days=1)


class Agendador:
    def __init__(
        self,
        cfg: Configuracao,
        estudos: RepositorioEstudos,
        gerar_dia: Callable[[date], Awaitable[Estudo]],
        agora: Callable[[], datetime] | None = None,
        backups_dir: Path | None = None,
    ) -> None:
        fuso = ZoneInfo(cfg.fuso_horario)
        self.cfg = cfg
        self.estudos = estudos
        self.gerar_dia = gerar_dia
        self.agora = agora or (lambda: datetime.now(fuso))
        self.backups_dir = backups_dir or Path(cfg.mana_db).parent / "backups"
        self.parar = asyncio.Event()

    # --- passos da rodada

    def garantir_calendario(self, ano: int, hoje: date) -> str:
        """Se o banco não tem nenhum dia de `ano`: importa o YAML revisado, ou gera um novo.

        Devolve "existente", "importado" ou "gerado".
        """
        if self.estudos.calendario(date(ano, 1, 1), date(ano, 12, 31)):
            return "existente"
        acervo = carregar_acervo()
        yaml = Path(self.cfg.calendarios_dir) / f"{ano}.yaml"
        if yaml.exists():
            rel = cal.importar_yaml(
                ano, yaml, self.estudos, RepositorioBiblia(self.cfg.biblia_db), acervo, hoje
            )
            if not rel.erros:
                log.info(
                    "Calendário de %d importado de %s (%d dias)", ano, yaml, len(rel.alterados)
                )
                return "importado"
            log.error("%s inválido (%s); vou gerar um calendário novo", yaml, rel.erros[:3])
        resultado = cal.montar_ano(
            ano,
            self.estudos,
            acervo,
            interpretar_ativas(self.cfg.ocasioes_ativas),
            hoje,
            Path(self.cfg.calendarios_dir),
        )
        for aviso in resultado.avisos:
            log.warning("Calendário %d: %s", ano, aviso)
        log.info("Calendário de %d gerado (%d dias)", ano, len(resultado.linhas))
        return "gerado"

    def garantir_calendarios(self, hoje: date) -> None:
        """Ano corrente sempre; o seguinte a partir de 1º de dezembro."""
        anos = [hoje.year] + ([hoje.year + 1] if hoje.month == 12 else [])
        for ano in anos:
            try:
                self.garantir_calendario(ano, hoje)
            except Exception:
                log.exception("Falha ao garantir o calendário de %d", ano)

    async def gerar_proximos(self, hoje: date) -> None:
        for i in range(DIAS_A_FRENTE + 1):
            if self.parar.is_set():
                return
            dia = hoje + timedelta(days=i)
            try:
                estudo = await self.gerar_dia(dia)
            except SemCalendario as e:
                log.warning("%s", e)
                continue
            except Exception:  # qualquer surpresa não derruba o laço
                log.exception("Não consegui gerar %s", dia)
                continue
            if estudo.status == "ok":
                continue
            log.warning("%s: falhou (%s)", dia, estudo.motivos[-1] if estudo.motivos else "?")
            if any("provedor" in m for m in estudo.motivos):
                log.warning("Provedor de LLM indisponível; encerro a rodada.")
                return

    def fazer_backup(self, hoje: date) -> Path:
        destino = self.backups_dir / f"mana-{hoje.isoformat()}.sqlite"
        self.estudos.copiar_para(destino)
        antigos = sorted(self.backups_dir.glob("mana-*.sqlite"))[:-BACKUPS_GUARDADOS]
        for velho in antigos:
            velho.unlink(missing_ok=True)
        return destino

    async def rodada(self) -> bool:
        """Uma rodada completa. Devolve True se o estudo de hoje está pronto."""
        hoje = self.agora().date()
        log.info("Rodada de %s", hoje)
        self.garantir_calendarios(hoje)
        await self.gerar_proximos(hoje)
        try:
            log.info("Backup: %s", self.fazer_backup(hoje))
        except Exception:
            log.exception("Falha no backup")
        estudo = self.estudos.estudo(hoje)
        return bool(estudo and estudo.status == "ok")

    # --- laço

    def quando_acordar(self, hoje_pronto: bool) -> datetime:
        agora = self.agora()
        amanha = proxima_rodada(agora)
        return amanha if hoje_pronto else min(amanha, agora + NOVA_TENTATIVA)

    async def _dormir_ate(self, momento: datetime) -> None:
        segundos = max((momento - self.agora()).total_seconds(), 0)
        try:
            await asyncio.wait_for(self.parar.wait(), timeout=segundos)
        except TimeoutError:
            pass

    async def _rodada_interrompivel(self) -> bool | None:
        """Roda a rodada, mas a cancela se vier o pedido de parada (None = parou).

        Cancelar no meio de uma chamada à LLM é seguro: o estudo só é gravado depois de validado.
        """
        rodada = asyncio.ensure_future(self.rodada())
        parada = asyncio.ensure_future(self.parar.wait())
        await asyncio.wait({rodada, parada}, return_when=asyncio.FIRST_COMPLETED)
        parada.cancel()
        if self.parar.is_set() and not rodada.done():
            rodada.cancel()
            await asyncio.gather(rodada, return_exceptions=True)
            log.info("Rodada interrompida pelo pedido de parada.")
            return None
        return rodada.result()

    async def executar(self) -> None:
        log.info("Agendador iniciado (rodada diária às %s).", HORA_DA_RODADA.strftime("%H:%M"))
        while not self.parar.is_set():
            pronto = await self._rodada_interrompivel()  # a 1ª é a rodada de recuperação
            if pronto is None:
                break
            proximo = self.quando_acordar(pronto)
            log.info("Próxima rodada: %s", proximo.isoformat(timespec="minutes"))
            await self._dormir_ate(proximo)
        log.info("Agendador encerrado.")


async def principal(cfg: Configuracao) -> None:
    from mana.estudos.gerador import Gerador
    from mana.llm.fabrica import criar_cliente

    estudos = RepositorioEstudos(cfg.mana_db)
    gerador = Gerador(criar_cliente(cfg), RepositorioBiblia(cfg.biblia_db), estudos, cfg)
    agendador = Agendador(cfg, estudos, gerador.gerar_dia)
    laco = asyncio.get_running_loop()
    for sinal in (signal.SIGTERM, signal.SIGINT):
        laco.add_signal_handler(sinal, agendador.parar.set)
    await agendador.executar()
