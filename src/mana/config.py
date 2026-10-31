"""Configuração lida do .env (AGENTS.md §2, regra 8 e 9)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracao(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provedor: str = "llm-server"
    modo_teste: bool = True
    llm_base_url: str = "http://localhost:8081/v1"
    llm_api_key: str = ""
    llm_modelo: str = ""
    llm_timeout_s: int = 120
    llm_pensar: bool = False
    llm_versao_prompt: str = "estudo_diario.v1"

    biblia_db: str = "data/biblia/biblia.sqlite"
    mana_db: str = "data/mana.sqlite"
    calendarios_dir: str = "data/calendarios"

    ocasioes_ativas: str = "todas"

    fuso_horario: str = "America/Sao_Paulo"
    host: str = "0.0.0.0"
    porta: int = 8000
    url_publica: str = "http://localhost:8000"


@lru_cache
def obter_configuracao() -> Configuracao:
    return Configuracao()
