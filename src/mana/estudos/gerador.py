"""Gera o estudo do dia: monta o prompt, chama a LLM, valida e grava (AGENTS.md §6)."""

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from mana.biblia.referencias import canonico, formatar, parse_canonico
from mana.biblia.repositorio import RepositorioBiblia
from mana.config import Configuracao
from mana.estudos import validacao
from mana.estudos.datas_especiais import OCASIOES
from mana.estudos.modelos import Estudo, EstudoGerado
from mana.estudos.repositorio import RepositorioEstudos
from mana.llm.base import ClienteLLM, ErroLLM
from mana.tempo import data_extenso

log = logging.getLogger("mana.gerador")

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
MAX_TENTATIVAS = 3
TEMPERATURA = 0.7
MAX_TOKENS = 1500
MAX_TOKENS_PENSANDO = 3200  # o "thinking" gasta tokens antes do JSON
DIAS_HISTORICO = 30


class SemCalendario(Exception):
    """A data não tem versículo no calendário (rode `mana calendario gerar`)."""


@dataclass(frozen=True)
class Prompt:
    sistema: str
    usuario: str


def carregar_prompt(versao: str, pasta: Path = PROMPTS_DIR) -> Prompt:
    """Lê `prompts/<versao>.md`, tirando o comentário do topo e separando SISTEMA/USUÁRIO."""
    texto = (pasta / f"{versao}.md").read_text(encoding="utf-8")
    texto = re.sub(r"<!--.*?-->", "", texto, flags=re.DOTALL)
    m = re.search(r"##\s*SISTEMA\s*(.*?)\s*##\s*USUÁRIO\s*(.*)", texto, re.DOTALL)
    if not m:
        raise ValueError(f"Prompt {versao!r} sem as seções '## SISTEMA' e '## USUÁRIO'")
    return Prompt(m.group(1).strip(), m.group(2).strip())


def preencher(modelo: str, campos: dict[str, str]) -> str:
    for nome, valor in campos.items():
        modelo = modelo.replace("{" + nome + "}", valor)
    return modelo


def _resumo_erro_pydantic(e: ValidationError) -> str:
    partes = [f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()[:4]]
    return "formato inválido (" + "; ".join(partes) + ")"


class Gerador:
    def __init__(
        self,
        cliente: ClienteLLM,
        biblia: RepositorioBiblia,
        estudos: RepositorioEstudos,
        cfg: Configuracao,
        prompts_dir: Path = PROMPTS_DIR,
    ) -> None:
        self.cliente = cliente
        self.biblia = biblia
        self.estudos = estudos
        self.cfg = cfg
        self.versao_prompt = cfg.llm_versao_prompt
        self.prompt = carregar_prompt(self.versao_prompt, prompts_dir)
        self.esquema = EstudoGerado.esquema()

    def _historico(self, data: date) -> tuple[validacao.Historico, str, str]:
        recentes = self.estudos.recentes(data, DIAS_HISTORICO)
        comp = {e.complementar for e in recentes if e.complementar}
        palavras = {p for e in recentes for p in e.palavras_chave}
        historico = validacao.Historico(comp, palavras)
        comp_txt = ", ".join(formatar(parse_canonico(c)) for c in sorted(comp)) or "nenhuma"
        pal_txt = ", ".join(sorted(palavras)[:40]) or "nenhuma"
        return historico, comp_txt, pal_txt

    def _prompt(self, data: date, ref, ocasiao: str | None, erros: list[str]) -> tuple[str, str]:
        historico, comp_txt, pal_txt = self._historico(data)
        texto = " ".join(v.texto for v in self.biblia.passagem(ref))
        linha = ""
        if ocasiao:
            linha = (
                f"Ocasião: {OCASIOES[ocasiao].nome}. O estudo deve tratar do sentido bíblico "
                "desta data, sem polêmicas denominacionais e sem tradições que não estejam "
                "no texto bíblico."
            )
        retry = ""
        if erros:
            retry = (
                "ATENÇÃO: sua resposta anterior foi rejeitada porque: "
                + " | ".join(erros)
                + ". Corrija isso e responda de novo somente com o JSON."
            )
        campos = {
            "data_extenso": data_extenso(data),
            "linha_ocasiao": linha,
            "referencia": formatar(ref),
            "texto_versiculo": texto,
            "complementares_recentes": comp_txt,
            "palavras_recentes": pal_txt,
            "erro_tentativa_anterior": retry,
        }
        return preencher(self.prompt.sistema, campos), preencher(self.prompt.usuario, campos)

    async def gerar_dia(self, data: date, forcar: bool = False) -> Estudo:
        """Gera (ou devolve o já existente) o estudo de `data`. Nunca publica conteúdo inválido."""
        existente = self.estudos.estudo(data)
        if existente and existente.status == "ok" and not forcar:
            return existente
        dia = self.estudos.dia(data)
        if dia is None:
            raise SemCalendario(f"{data} não tem versículo no calendário")
        ref = parse_canonico(dia.ref)
        historico, _, _ = self._historico(data)

        motivos: list[str] = []
        erros_anteriores: list[str] = []
        tempo = 0.0
        bruto = None
        modelo = ""
        base = dict(
            data=data,
            ref=dia.ref,
            ocasiao=dia.ocasiao,
            provedor=self.cliente.provedor,
            versao_prompt=self.versao_prompt,
            gerado_em=datetime.now(ZoneInfo(self.cfg.fuso_horario)),
        )
        for tentativa in range(1, MAX_TENTATIVAS + 1):
            sistema, usuario = self._prompt(data, ref, dia.ocasiao, erros_anteriores)
            try:
                resposta = await self.cliente.gerar_json(
                    sistema,
                    usuario,
                    self.esquema,
                    TEMPERATURA,
                    MAX_TOKENS_PENSANDO if self.cfg.llm_pensar else MAX_TOKENS,
                )
            except ErroLLM as e:  # rede, timeout, 5xx, JSON ilegível: não é culpa do conteúdo
                motivos.append(f"tentativa {tentativa}: provedor: {e}")
                log.warning("%s: provedor falhou: %s", data, e)
                return self._falha(base, tentativa, motivos, tempo, bruto, modelo)
            tempo += resposta.latencia_s
            modelo = resposta.modelo
            bruto = _json(resposta.dados)
            try:
                gerado = EstudoGerado.model_validate(resposta.dados)
            except ValidationError as e:
                erros_anteriores = [_resumo_erro_pydantic(e)]
            else:
                resultado = validacao.validar(gerado, ref, historico, self.biblia)
                if resultado.ok:
                    for aviso in resultado.avisos:
                        log.info("%s: %s", data, aviso)
                    estudo = Estudo(
                        **base,
                        status="ok",
                        titulo=gerado.titulo.strip(),
                        frase_do_dia=gerado.frase_do_dia.strip(),
                        paragrafos=[p.strip() for p in gerado.paragrafos],
                        complementar=canonico(resultado.complementar),
                        palavras_chave=resultado.palavras_chave,
                        modelo=modelo,
                        tentativas=tentativa,
                        json_bruto=bruto,
                        motivos=motivos,
                        tempo_s=round(tempo, 2),
                    )
                    self.estudos.gravar_estudo(estudo)
                    return estudo
                erros_anteriores = resultado.erros
            motivos.append(f"tentativa {tentativa}: " + "; ".join(erros_anteriores))
            log.info("%s: tentativa %d rejeitada: %s", data, tentativa, erros_anteriores)
        return self._falha(base, MAX_TENTATIVAS, motivos, tempo, bruto, modelo)

    def _falha(self, base, tentativas, motivos, tempo, bruto, modelo) -> Estudo:
        estudo = Estudo(
            **base,
            status="falhou",
            modelo=modelo,
            tentativas=tentativas,
            json_bruto=bruto,
            motivos=motivos,
            tempo_s=round(tempo, 2),
        )
        self.estudos.gravar_estudo(estudo)
        return estudo


def _json(dados: dict) -> str:
    return json.dumps(dados, ensure_ascii=False)
