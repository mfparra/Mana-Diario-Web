"""Interface comum a todos os provedores de LLM."""

from dataclasses import dataclass
from typing import Protocol


class ErroLLM(Exception):
    """Falha ao falar com o provedor (rede, 5xx, resposta inútil)."""


class TempoEsgotado(ErroLLM):
    """O provedor não respondeu a tempo (não é erro de validação do conteúdo)."""


@dataclass
class RespostaLLM:
    dados: dict
    modelo: str
    latencia_s: float
    tokens_saida: int = 0


class ClienteLLM(Protocol):
    provedor: str

    async def gerar_json(
        self,
        sistema: str,
        usuario: str,
        esquema: dict,
        temperatura: float = 0.7,
        max_tokens: int = 1200,
    ) -> RespostaLLM: ...
