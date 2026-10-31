"""Adaptador do llm-server compartilhado (llama.cpp, API compatível com OpenAI).

Temporário, só para testes (docs/LLM.md §0).
"""

import asyncio
import json
import time

import httpx

from mana.llm.base import ErroLLM, RespostaLLM, TempoEsgotado

TENTATIVAS = 3


def extrair_json(texto: str) -> dict:
    """Parsing tolerante: remove cercas ```json e pega do primeiro { ao último }."""
    texto = texto.strip()
    ini, fim = texto.find("{"), texto.rfind("}")
    if ini < 0 or fim <= ini:
        raise ErroLLM("a resposta não contém um objeto JSON")
    try:
        dados = json.loads(texto[ini : fim + 1])
    except json.JSONDecodeError as e:
        raise ErroLLM(f"JSON inválido: {e}") from e
    if not isinstance(dados, dict):
        raise ErroLLM("a resposta JSON não é um objeto")
    return dados


class ClienteLLMServer:
    provedor = "llm-server"

    def __init__(
        self,
        base_url: str,
        modelo: str = "",
        api_key: str = "",
        timeout_s: float = 120,
        pensar: bool = False,
        cliente: httpx.AsyncClient | None = None,
        espera_base_s: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.modelo = modelo
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.pensar = pensar
        self._cliente = cliente
        self._espera_base_s = espera_base_s

    async def gerar_json(
        self,
        sistema: str,
        usuario: str,
        esquema: dict,
        temperatura: float = 0.7,
        max_tokens: int = 1200,
    ) -> RespostaLLM:
        corpo = {
            "model": self.modelo,
            "messages": [
                {"role": "system", "content": sistema},
                {"role": "user", "content": usuario},
            ],
            "temperature": temperatura,
            "max_tokens": max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "estudo", "strict": True, "schema": esquema},
            },
            "chat_template_kwargs": {"enable_thinking": self.pensar},
        }
        cabecalhos = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        cliente = self._cliente or httpx.AsyncClient(timeout=self.timeout_s)
        inicio = time.monotonic()
        ultimo: Exception | None = None
        try:
            for n in range(TENTATIVAS):
                try:
                    r = await cliente.post(
                        f"{self.base_url}/chat/completions", json=corpo, headers=cabecalhos
                    )
                    if r.status_code >= 500:
                        raise ErroLLM(f"HTTP {r.status_code}: {r.text[:200]}")
                    r.raise_for_status()
                    d = r.json()
                    texto = d["choices"][0]["message"].get("content") or ""
                    return RespostaLLM(
                        dados=extrair_json(texto),
                        modelo=d.get("model") or self.modelo,
                        latencia_s=time.monotonic() - inicio,
                        tokens_saida=d.get("usage", {}).get("completion_tokens", 0),
                    )
                except httpx.TimeoutException as e:
                    raise TempoEsgotado(str(e) or "tempo esgotado") from e
                except (httpx.TransportError, ErroLLM) as e:
                    ultimo = e
                    if n < TENTATIVAS - 1:
                        await asyncio.sleep(self._espera_base_s * 2**n)
                except httpx.HTTPStatusError as e:
                    raise ErroLLM(f"HTTP {e.response.status_code}: {e.response.text[:200]}") from e
        finally:
            if self._cliente is None:
                await cliente.aclose()
        raise ErroLLM(f"falhou após {TENTATIVAS} tentativas: {ultimo}")
