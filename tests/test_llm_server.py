import json

import httpx
import pytest
import respx

from mana.llm.base import ErroLLM, TempoEsgotado
from mana.llm.fabrica import criar_cliente
from mana.llm.llm_server import ClienteLLMServer, extrair_json

URL = "http://llm.teste/v1"
ESQUEMA = {"type": "object"}


def cliente(**kw):
    return ClienteLLMServer(URL, modelo="m", espera_base_s=0, **kw)


def resposta(texto, status=200):
    corpo = {
        "model": "m",
        "choices": [{"message": {"content": texto}}],
        "usage": {"completion_tokens": 7},
    }
    return httpx.Response(status, json=corpo)


@pytest.mark.parametrize(
    "texto",
    ['{"a": 1}', '```json\n{"a": 1}\n```', 'Aqui está: {"a": 1} pronto'],
)
def test_extrair_json_tolerante(texto):
    assert extrair_json(texto) == {"a": 1}


@pytest.mark.parametrize("texto", ["sem json", "{quebrado", "[1, 2]"])
def test_extrair_json_invalido(texto):
    with pytest.raises(ErroLLM):
        extrair_json(texto)


@respx.mock
async def test_sucesso_envia_esquema_e_sem_thinking():
    rota = respx.post(f"{URL}/chat/completions").mock(return_value=resposta('{"a": 1}'))
    r = await cliente().gerar_json("s", "u", ESQUEMA)
    assert r.dados == {"a": 1} and r.modelo == "m" and r.tokens_saida == 7
    corpo = json.loads(rota.calls[0].request.read())
    assert corpo["response_format"]["type"] == "json_schema"
    assert corpo["chat_template_kwargs"] == {"enable_thinking": False}


@respx.mock
async def test_json_invalido_vira_erro():
    respx.post(f"{URL}/chat/completions").mock(return_value=resposta("nada de json"))
    with pytest.raises(ErroLLM):
        await cliente().gerar_json("s", "u", ESQUEMA)


@respx.mock
async def test_5xx_tenta_de_novo_e_recupera():
    rota = respx.post(f"{URL}/chat/completions").mock(
        side_effect=[httpx.Response(503, text="Loading model"), resposta('{"a": 1}')]
    )
    r = await cliente().gerar_json("s", "u", ESQUEMA)
    assert r.dados == {"a": 1} and rota.call_count == 2


@respx.mock
async def test_5xx_persistente_esgota_tentativas():
    rota = respx.post(f"{URL}/chat/completions").mock(return_value=httpx.Response(500))
    with pytest.raises(ErroLLM):
        await cliente().gerar_json("s", "u", ESQUEMA)
    assert rota.call_count == 3


@respx.mock
async def test_timeout_nao_e_retentado():
    rota = respx.post(f"{URL}/chat/completions").mock(side_effect=httpx.ReadTimeout("lento"))
    with pytest.raises(TempoEsgotado):
        await cliente().gerar_json("s", "u", ESQUEMA)
    assert rota.call_count == 1


@respx.mock
async def test_erro_4xx_nao_e_retentado():
    rota = respx.post(f"{URL}/chat/completions").mock(return_value=httpx.Response(400))
    with pytest.raises(ErroLLM):
        await cliente().gerar_json("s", "u", ESQUEMA)
    assert rota.call_count == 1


def test_fabrica_provedor_desconhecido():
    from mana.config import Configuracao

    with pytest.raises(ValueError):
        criar_cliente(Configuracao(llm_provedor="inexistente"))
