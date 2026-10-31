"""Escolhe o adaptador de LLM pela configuração (LLM_PROVEDOR)."""

from mana.config import Configuracao, obter_configuracao
from mana.llm.base import ClienteLLM
from mana.llm.llm_server import ClienteLLMServer


def criar_cliente(cfg: Configuracao | None = None) -> ClienteLLM:
    cfg = cfg or obter_configuracao()
    if cfg.llm_provedor == "llm-server":
        return ClienteLLMServer(
            base_url=cfg.llm_base_url,
            modelo=cfg.llm_modelo,
            api_key=cfg.llm_api_key,
            timeout_s=cfg.llm_timeout_s,
            pensar=cfg.llm_pensar,
        )
    raise ValueError(f"Provedor de LLM desconhecido: {cfg.llm_provedor!r}")
