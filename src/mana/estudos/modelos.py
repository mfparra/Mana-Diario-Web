"""Modelos do estudo: o que a LLM devolve e o que fica gravado (docs/LLM.md §4)."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Paragrafo = Annotated[str, StringConstraints(min_length=200, max_length=900)]
Referencia40 = Annotated[str, StringConstraints(max_length=40)]
Palavra = Annotated[str, StringConstraints(max_length=24)]


class EstudoGerado(BaseModel):
    """Saída bruta da LLM. As regras de conteúdo ficam em `validacao.py`."""

    model_config = ConfigDict(extra="forbid")

    titulo: str = Field(min_length=3, max_length=48)
    frase_do_dia: str = Field(min_length=20, max_length=140)
    paragrafos: list[Paragrafo] = Field(min_length=3, max_length=4)
    complementares: list[Referencia40] = Field(min_length=3, max_length=3)
    palavras_chave: list[Palavra] = Field(min_length=3, max_length=5)

    @classmethod
    def esquema(cls) -> dict:
        """JSON Schema enviado ao provedor (sem os campos `title` que o Pydantic acrescenta)."""

        def limpar(no):
            if isinstance(no, dict):
                return {k: limpar(v) for k, v in no.items() if k != "title"}
            if isinstance(no, list):
                return [limpar(x) for x in no]
            return no

        return limpar(cls.model_json_schema())


class Estudo(BaseModel):
    """Estudo gravado no banco (um por data)."""

    data: date
    status: Literal["ok", "falhou"]
    ref: str  # versículo do dia, forma canônica
    ocasiao: str | None = None
    titulo: str | None = None
    frase_do_dia: str | None = None
    paragrafos: list[str] = []
    complementar: str | None = None  # forma canônica
    palavras_chave: list[str] = []
    provedor: str = ""
    modelo: str = ""
    versao_prompt: str = ""
    tentativas: int = 0
    revisado: bool = False
    json_bruto: str | None = None
    motivos: list[str] = []  # motivo de cada rejeição, para ajustar o prompt
    tempo_s: float = 0.0
    gerado_em: datetime
