import asyncio
import sqlite3
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from mana.agendador import (
    BACKUPS_GUARDADOS,
    DIAS_A_FRENTE,
    Agendador,
    proxima_rodada,
)
from mana.config import Configuracao
from mana.estudos.gerador import SemCalendario
from mana.estudos.modelos import Estudo
from mana.estudos.repositorio import LinhaCalendario, RepositorioEstudos

FUSO = ZoneInfo("America/Sao_Paulo")


def em(ano, mes, dia, h=0, m=0):
    return datetime(ano, mes, dia, h, m, tzinfo=FUSO)


class Relogio:
    def __init__(self, agora):
        self.agora = agora

    def __call__(self):
        return self.agora


def estudo(data, status="ok", motivos=()):
    return Estudo(
        data=data, status=status, ref="rom.8.28", motivos=list(motivos),
        gerado_em=em(2026, 1, 1),
    )  # fmt: skip


class GeradorFalso:
    """Imita Gerador.gerar_dia: grava o estudo no banco como o de verdade."""

    def __init__(self, estudos, resultados=None):
        self.estudos = estudos
        self.chamadas: list[date] = []
        self.resultados = resultados or {}

    async def __call__(self, dia):
        self.chamadas.append(dia)
        r = self.resultados.get(dia, "ok")
        if r == "sem-calendario":
            raise SemCalendario(str(dia))
        e = estudo(dia, "ok" if r == "ok" else "falhou", [] if r == "ok" else [r])
        self.estudos.gravar_estudo(e)
        return e


@pytest.fixture
def cfg(tmp_path):
    return Configuracao(
        mana_db=str(tmp_path / "mana.sqlite"), calendarios_dir=str(tmp_path / "cal")
    )


@pytest.fixture
def estudos(cfg):
    return RepositorioEstudos(cfg.mana_db)


def montar(cfg, estudos, agora, gerador=None):
    relogio = Relogio(agora)
    g = gerador or GeradorFalso(estudos)
    return Agendador(cfg, estudos, g, agora=relogio), g, relogio


@pytest.mark.parametrize(
    ("agora", "esperado"),
    [
        (em(2026, 11, 3, 0, 0), em(2026, 11, 3, 0, 10)),
        (em(2026, 11, 3, 0, 9), em(2026, 11, 3, 0, 10)),
        (em(2026, 11, 3, 0, 10), em(2026, 11, 4, 0, 10)),
        (em(2026, 11, 3, 15, 30), em(2026, 11, 4, 0, 10)),
        (em(2026, 12, 31, 23, 59), em(2027, 1, 1, 0, 10)),
    ],
)
def test_proxima_rodada(agora, esperado):
    assert proxima_rodada(agora) == esperado


async def test_rodada_gera_hoje_e_os_sete_dias_seguintes_em_ordem(cfg, estudos):
    ag, g, _ = montar(cfg, estudos, em(2026, 11, 3, 0, 10))
    assert await ag.rodada() is True
    assert g.chamadas == [date(2026, 11, 3) + timedelta(days=i) for i in range(DIAS_A_FRENTE + 1)]


async def test_dia_sem_calendario_nao_derruba_a_rodada(cfg, estudos):
    g = GeradorFalso(estudos, {date(2026, 11, 4): "sem-calendario"})
    ag, _, _ = montar(cfg, estudos, em(2026, 11, 3), g)
    assert await ag.rodada() is True
    assert len(g.chamadas) == DIAS_A_FRENTE + 1  # seguiu para os outros dias


async def test_provedor_fora_encerra_a_rodada_cedo_e_hoje_fica_pendente(cfg, estudos):
    g = GeradorFalso(estudos, {date(2026, 11, 3): "tentativa 1: provedor: Connection refused"})
    ag, _, _ = montar(cfg, estudos, em(2026, 11, 3), g)
    assert await ag.rodada() is False
    assert g.chamadas == [date(2026, 11, 3)]


async def test_falha_de_conteudo_nao_interrompe_os_outros_dias(cfg, estudos):
    g = GeradorFalso(estudos, {date(2026, 11, 4): "tentativa 3: título com mais de 6 palavras"})
    ag, _, _ = montar(cfg, estudos, em(2026, 11, 3), g)
    assert await ag.rodada() is True and len(g.chamadas) == DIAS_A_FRENTE + 1


def test_tenta_de_novo_em_30_min_se_hoje_nao_ficou_pronto(cfg, estudos):
    ag, _, _ = montar(cfg, estudos, em(2026, 11, 3, 10, 0))
    assert ag.quando_acordar(False) == em(2026, 11, 3, 10, 30)
    assert ag.quando_acordar(True) == em(2026, 11, 4, 0, 10)
    ag.agora = lambda: em(2026, 11, 3, 23, 50)
    assert ag.quando_acordar(False) == em(2026, 11, 4, 0, 10)  # a rodada da noite vem antes


# --------------------------------------------------------------------- backup


async def test_backup_e_copia_valida_do_banco(cfg, estudos):
    estudos.gravar([LinhaCalendario(date(2026, 11, 3), "rom.8.28")])
    ag, _, _ = montar(cfg, estudos, em(2026, 11, 3))
    await ag.rodada()
    copia = ag.backups_dir / "mana-2026-11-03.sqlite"
    assert copia.exists()
    con = sqlite3.connect(copia)
    assert con.execute("SELECT ref FROM calendario").fetchone() == ("rom.8.28",)
    assert con.execute("SELECT COUNT(*) FROM estudos").fetchone()[0] == DIAS_A_FRENTE + 1


def test_backup_guarda_so_as_ultimas_14(cfg, estudos):
    ag, _, _ = montar(cfg, estudos, em(2026, 11, 30))
    for i in range(20):
        ag.fazer_backup(date(2026, 11, 1) + timedelta(days=i))
    nomes = sorted(p.name for p in ag.backups_dir.glob("mana-*.sqlite"))
    assert len(nomes) == BACKUPS_GUARDADOS
    assert nomes[0] == "mana-2026-11-07.sqlite" and nomes[-1] == "mana-2026-11-20.sqlite"


def test_backup_do_mesmo_dia_sobrescreve(cfg, estudos):
    ag, _, _ = montar(cfg, estudos, em(2026, 11, 3))
    ag.fazer_backup(date(2026, 11, 3))
    ag.fazer_backup(date(2026, 11, 3))
    assert len(list(ag.backups_dir.glob("mana-*.sqlite"))) == 1


# ------------------------------------------------------- calendário do ano seguinte


async def test_em_dezembro_monta_o_calendario_do_ano_seguinte_uma_vez(cfg, estudos, tmp_path):
    ag, g, _ = montar(cfg, estudos, em(2026, 12, 1, 0, 10))
    await ag.rodada()
    do_ano = estudos.calendario(date(2027, 1, 1), date(2027, 12, 31))
    assert len(do_ano) == 365 and (tmp_path / "cal" / "2027.yaml").exists()
    primeira = list(do_ano)
    await ag.rodada()  # 2ª rodada: não refaz
    assert estudos.calendario(date(2027, 1, 1), date(2027, 12, 31)) == primeira


async def test_fora_de_dezembro_so_garante_o_ano_corrente(cfg, estudos):
    ag, _, _ = montar(cfg, estudos, em(2026, 11, 30))
    await ag.rodada()
    assert estudos.calendario(date(2027, 1, 1), date(2027, 12, 31)) == []
    assert estudos.calendario(date(2026, 11, 30), date(2026, 12, 31))  # ano corrente existe


async def test_banco_novo_importa_o_yaml_revisado_em_vez_de_gerar(cfg, estudos, tmp_path):
    yaml = tmp_path / "cal" / "2026.yaml"
    yaml.parent.mkdir()
    yaml.write_text(
        'ano: 2026\ndias:\n  - {data: "2026-11-03", ref: "João 3.16"}\n'
        '  - {data: "2026-11-04", ref: "Salmos 23.1,2"}\n',
        encoding="utf-8",
    )
    ag, _, _ = montar(cfg, estudos, em(2026, 11, 3))
    assert ag.garantir_calendario(2026, date(2026, 11, 3)) == "importado"
    assert [(x.data.day, x.ref) for x in estudos.calendario()] == [
        (3, "jhn.3.16"),
        (4, "psa.23.1-2"),
    ]
    assert ag.garantir_calendario(2026, date(2026, 11, 3)) == "existente"


async def test_yaml_invalido_cai_para_calendario_gerado(cfg, estudos, tmp_path):
    yaml = tmp_path / "cal" / "2026.yaml"
    yaml.parent.mkdir()
    yaml.write_text('ano: 2026\ndias:\n  - {data: "2026-11-03", ref: "lixo"}\n', encoding="utf-8")
    ag, _, _ = montar(cfg, estudos, em(2026, 11, 3))
    assert ag.garantir_calendario(2026, date(2026, 11, 3)) == "gerado"
    assert len(estudos.calendario(date(2026, 11, 3), date(2026, 12, 31))) == 59


async def test_dezembro_respeita_calendario_ja_editado(cfg, estudos):
    estudos.gravar([LinhaCalendario(date(2027, 1, 1), "jhn.3.16", "ano-novo", "editado")])
    ag, _, _ = montar(cfg, estudos, em(2026, 12, 15))
    await ag.rodada()
    assert len(estudos.calendario(date(2027, 1, 1), date(2027, 12, 31))) == 1


# ----------------------------------------------------------------------- o laço


async def test_laco_faz_recuperacao_ao_iniciar_dorme_e_encerra_com_sigterm(cfg, estudos):
    ag, g, _ = montar(cfg, estudos, em(2026, 11, 3, 15, 0))
    tarefa = asyncio.create_task(ag.executar())
    for _ in range(100):
        await asyncio.sleep(0.01)
        if len(g.chamadas) == DIAS_A_FRENTE + 1:
            break
    assert len(g.chamadas) == DIAS_A_FRENTE + 1  # rodada de recuperação já aconteceu
    assert not tarefa.done()  # agora dorme até 00:10
    ag.parar.set()  # o que o SIGTERM faz
    await asyncio.wait_for(tarefa, timeout=2)


async def test_sigterm_no_meio_da_rodada_para_entre_os_dias(cfg, estudos):
    g = GeradorFalso(estudos)
    ag, _, _ = montar(cfg, estudos, em(2026, 11, 3), g)
    original = g.__call__

    async def parando(dia):
        r = await original(dia)
        if len(g.chamadas) == 2:
            ag.parar.set()
        return r

    ag.gerar_dia = parando
    await asyncio.wait_for(ag.executar(), timeout=2)
    assert len(g.chamadas) == 2


async def test_laco_acorda_para_nova_tentativa_quando_hoje_falhou(cfg, estudos, monkeypatch):
    g = GeradorFalso(estudos, {date(2026, 11, 3): "tentativa 1: provedor: fora"})
    ag, _, relogio = montar(cfg, estudos, em(2026, 11, 3, 9, 0), g)
    dormiu = []

    async def dorme(momento):
        dormiu.append(momento)
        g.resultados.clear()  # a LLM voltou
        relogio.agora = momento
        if len(dormiu) == 2:
            ag.parar.set()

    monkeypatch.setattr(ag, "_dormir_ate", dorme)
    await asyncio.wait_for(ag.executar(), timeout=2)
    assert dormiu[0] == em(2026, 11, 3, 9, 30)  # nova tentativa em 30 min
    assert dormiu[1] == em(2026, 11, 4, 0, 10)  # deu certo: volta à rotina da madrugada


async def test_sigterm_cancela_chamada_demorada_a_llm(cfg, estudos):
    iniciou = asyncio.Event()

    async def lento(dia):
        iniciou.set()
        await asyncio.sleep(3600)  # LLM "pendurada"

    ag, _, _ = montar(cfg, estudos, em(2026, 11, 3), lento)
    tarefa = asyncio.create_task(ag.executar())
    await asyncio.wait_for(iniciou.wait(), timeout=2)
    ag.parar.set()
    await asyncio.wait_for(tarefa, timeout=2)  # sai na hora, sem esperar a LLM
    assert estudos.estudo(date(2026, 11, 3)) is None
