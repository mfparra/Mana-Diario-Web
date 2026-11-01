import json
from datetime import date, datetime

import httpx
import pytest
import respx

from mana.biblia.referencias import parse_canonico, parse_referencia
from mana.config import Configuracao
from mana.estudos import validacao
from mana.estudos.gerador import Gerador, SemCalendario, carregar_prompt, preencher
from mana.estudos.modelos import Estudo, EstudoGerado
from mana.estudos.repositorio import LinhaCalendario, RepositorioEstudos
from mana.llm.llm_server import ClienteLLMServer

URL = "http://llm.teste/v1"
DIA = date(2026, 11, 3)

P1 = (
    "Pense numa casa pequena no fim da rua, onde a luz da cozinha continua acesa até tarde "
    "porque alguém espera por você. Ninguém ali pede explicações demoradas, basta chegar "
    "cansado, deixar a bolsa num canto e sentar à mesa. Essa imagem simples ajuda a entender "
    "como é viver sob o cuidado de Deus, que não nos cobra desempenho antes de nos receber "
    "e conhece o peso que carregamos. Quem chega assim descobre que descansar não é "
    "desistir, e sim aceitar que existe um lugar seguro para recomeçar a cada manhã."
)
P2 = (
    "O versículo de hoje nos lembra que o cuidado divino não depende da nossa força, e sim da "
    "fidelidade dele. Quando o texto foi escrito, o povo atravessava dias incertos, e mesmo "
    "assim a mensagem era de firmeza. Deus sabe o que acontece por trás das portas fechadas, "
    "conhece nossos medos mais discretos e age com paciência, sem pressa e sem esquecer "
    "ninguém pelo caminho. Por isso, o que parecia um peso grande demais pode ser entregue "
    "em partes, uma de cada vez, até que a gente perceba que nunca esteve sozinho."
)
P3 = (
    "Hoje, você pode fazer uma pausa curta antes de resolver tudo sozinho. Respire fundo, "
    "entregue a primeira preocupação do dia em oração e escolha uma pequena atitude de "
    "confiança, como agradecer por algo concreto. Se precisar de mais ânimo, releia "
    "Filipenses 4.6 e deixe que a paz tome conta do seu coração durante as tarefas comuns. "
    "Ao fim do dia, olhe para trás e note quantas vezes o cuidado de Deus chegou antes de "
    "você, discreto como a luz acesa na cozinha."
)


def corpo(**sobre):
    base = {
        "titulo": "Descanso no cuidado de Deus",
        "frase_do_dia": "O cuidado de Deus sustenta cada passo do nosso dia comum.",
        "paragrafos": [P1, P2, P3],
        "complementares": ["Salmos 23.1,2", "Filipenses 4.6,7", "Isaías 41.10"],
        "palavras_chave": ["cuidado", "confiança", "descanso"],
    }
    base.update(sobre)
    return base


def resposta(dados):
    return httpx.Response(
        200,
        json={
            "model": "modelo-teste",
            "choices": [{"message": {"content": json.dumps(dados, ensure_ascii=False)}}],
            "usage": {"completion_tokens": 300},
        },
    )


@pytest.fixture
def estudos(tmp_path):
    repo = RepositorioEstudos(tmp_path / "mana.sqlite")
    repo.gravar(
        [LinhaCalendario(DIA, "rom.8.28"), LinhaCalendario(date(2026, 12, 25), "isa.7.14", "natal")]
    )
    return repo


@pytest.fixture
def gerador(repo, estudos):
    cliente = ClienteLLMServer(URL, modelo="m", espera_base_s=0)
    return Gerador(cliente, repo, estudos, Configuracao())


def chamada_n(rota, n):
    return json.loads(rota.calls[n].request.read())


# ----------------------------------------------------------------------- prompt


def test_prompt_remove_comentario_e_separa_secoes():
    p = carregar_prompt("estudo_diario.v1")
    assert "<!--" not in p.sistema + p.usuario
    assert p.sistema.startswith("Você escreve") and "{referencia}" in p.usuario


def test_preencher_substitui_todas_as_ocorrencias():
    assert preencher("{a} e {a} e {b}", {"a": "1", "b": "2"}) == "1 e 1 e 2"


# ---------------------------------------------------------------------- sucesso


@respx.mock
async def test_sucesso_grava_estudo_completo(gerador, estudos):
    rota = respx.post(f"{URL}/chat/completions").mock(return_value=resposta(corpo()))
    e = await gerador.gerar_dia(DIA)
    assert e.status == "ok" and e.tentativas == 1
    assert e.titulo == "Descanso no cuidado de Deus" and len(e.paragrafos) == 3
    assert e.complementar == "psa.23.1-2"
    assert (e.provedor, e.modelo, e.versao_prompt) == (
        "llm-server", "modelo-teste", "estudo_diario.v1"
    )  # fmt: skip
    assert e.revisado is False and e.json_bruto and e.motivos == []
    assert estudos.estudo(DIA) == e
    # o prompt leva o texto do versículo, vindo da Bíblia local
    usuario = chamada_n(rota, 0)["messages"][1]["content"]
    assert "Romanos 8.28" in usuario and "E sabemos que todas as coisas" in usuario
    assert "terça-feira, 3 de novembro de 2026" in usuario
    assert "Ocasião:" not in usuario and "{" not in usuario


@respx.mock
async def test_prompt_de_ocasiao_e_historico(gerador, estudos):
    estudos.gravar([LinhaCalendario(date(2026, 12, 24), "luk.1.30-31")])
    estudos.gravar_estudo(
        Estudo(
            data=date(2026, 12, 20), status="ok", ref="rom.8.28", complementar="psa.23.1-2",
            palavras_chave=["cuidado", "paz"], gerado_em=datetime(2026, 12, 20, 6),
        )
    )  # fmt: skip
    rota = respx.post(f"{URL}/chat/completions").mock(return_value=resposta(corpo()))
    e = await gerador.gerar_dia(date(2026, 12, 25))
    usuario = chamada_n(rota, 0)["messages"][1]["content"]
    assert "Ocasião: Natal." in usuario
    assert "Salmos 23.1,2" in usuario and "cuidado, paz" in usuario
    assert (
        e.ocasiao == "natal" and e.complementar == "php.4.6-7"
    )  # a 1ª candidata foi usada há pouco


@respx.mock
async def test_esquema_enviado_e_valido_para_o_provedor(gerador):
    rota = respx.post(f"{URL}/chat/completions").mock(return_value=resposta(corpo()))
    await gerador.gerar_dia(DIA)
    esquema = chamada_n(rota, 0)["response_format"]["json_schema"]["schema"]
    assert esquema["additionalProperties"] is False
    assert set(esquema["required"]) == set(EstudoGerado.model_fields)
    assert "title" not in json.dumps(esquema)


@respx.mock
async def test_nao_refaz_estudo_existente_sem_forcar(gerador):
    rota = respx.post(f"{URL}/chat/completions").mock(return_value=resposta(corpo()))
    primeiro = await gerador.gerar_dia(DIA)
    de_novo = await gerador.gerar_dia(DIA)
    assert de_novo == primeiro and rota.call_count == 1
    await gerador.gerar_dia(DIA, forcar=True)
    assert rota.call_count == 2


async def test_sem_calendario(gerador):
    with pytest.raises(SemCalendario):
        await gerador.gerar_dia(date(2030, 1, 1))


# ------------------------------------------------------------------ falhas e retry


@respx.mock
async def test_json_invalido_do_provedor_vira_falhou(gerador, estudos):
    respx.post(f"{URL}/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "nada"}}]})
    )
    e = await gerador.gerar_dia(DIA)
    assert e.status == "falhou" and "provedor" in e.motivos[0]
    assert estudos.estudo(DIA).status == "falhou"


@respx.mock
async def test_timeout_vira_falhou_sem_retentar(gerador):
    rota = respx.post(f"{URL}/chat/completions").mock(side_effect=httpx.ReadTimeout("lento"))
    e = await gerador.gerar_dia(DIA)
    assert e.status == "falhou" and e.tentativas == 1 and rota.call_count == 1
    assert "provedor" in e.motivos[0]


@respx.mock
async def test_esquema_violado_tenta_de_novo(gerador):
    rota = respx.post(f"{URL}/chat/completions").mock(
        side_effect=[resposta(corpo(titulo="x")), resposta(corpo())]
    )
    e = await gerador.gerar_dia(DIA)
    assert e.status == "ok" and e.tentativas == 2
    assert "formato inválido" in chamada_n(rota, 1)["messages"][1]["content"]
    assert "titulo" in e.motivos[0]


@respx.mock
async def test_referencia_inexistente_tenta_de_novo_e_cita_o_erro(gerador):
    ruim = corpo(paragrafos=[P1, P2, P3.replace("Filipenses 4.6", "Romanos 99.1")])
    rota = respx.post(f"{URL}/chat/completions").mock(
        side_effect=[resposta(ruim), resposta(corpo())]
    )
    e = await gerador.gerar_dia(DIA)
    assert e.status == "ok" and e.tentativas == 2
    assert "Romanos 99.1" in chamada_n(rota, 1)["messages"][1]["content"]


@respx.mock
async def test_tres_rejeicoes_gravam_falhou_com_os_motivos(gerador, estudos):
    ruim = corpo(titulo="Um título muito comprido demais para o estudo")
    rota = respx.post(f"{URL}/chat/completions").mock(return_value=resposta(ruim))
    e = await gerador.gerar_dia(DIA)
    assert e.status == "falhou" and e.tentativas == 3 and rota.call_count == 3
    assert len(e.motivos) == 3 and all("título" in m for m in e.motivos)
    assert e.paragrafos == [] and e.titulo is None  # nada inválido é guardado como estudo
    assert estudos.estudo(DIA).status == "falhou"


@respx.mock
async def test_falhou_e_refeito_na_proxima_rodada(gerador, estudos):
    respx.post(f"{URL}/chat/completions").mock(
        side_effect=[httpx.ReadTimeout("x"), resposta(corpo())]
    )
    assert (await gerador.gerar_dia(DIA)).status == "falhou"
    assert (await gerador.gerar_dia(DIA)).status == "ok"  # sem --forcar


# --------------------------------------------------------------------- validação


@pytest.fixture
def principal():
    return parse_canonico("rom.8.28")


def gerado(**sobre):
    return EstudoGerado.model_validate(corpo(**sobre))


def checar(repo, principal, historico=None, **sobre):
    return validacao.validar(gerado(**sobre), principal, historico or validacao.Historico(), repo)


def test_estudo_bom_passa(repo, principal):
    r = checar(repo, principal)
    assert r.ok and r.erros == [] and canonico_de(r.complementar) == "psa.23.1-2"


def canonico_de(ref):
    from mana.biblia.referencias import canonico

    return canonico(ref)


@pytest.mark.parametrize(
    ("sobre", "trecho"),
    [
        ({"titulo": "Um título com sete palavras bem longas"}, "título"),
        ({"frase_do_dia": "casas " * 19}, "frase do dia"),
        ({"paragrafos": ["ab " * 150] * 4}, "600 palavras"),
        ({"paragrafos": ["ab " * 70] * 3}, "210 palavras"),
    ],
)
def test_limites_de_palavras(repo, principal, sobre, trecho):
    r = checar(repo, principal, **sobre)
    assert any(trecho in e for e in r.erros), r.erros


def test_complementar_pula_a_que_repete_o_principal(repo, principal):
    r = checar(repo, principal, complementares=["Rm 8.28", "Romanos 8.27,28", "Salmos 46.1"])
    assert r.ok and canonico_de(r.complementar) == "psa.46.1"


def test_complementar_pula_inexistente_recente_e_longa(repo, principal):
    historico = validacao.Historico(complementares={"psa.23.1-2"})
    r = checar(
        repo, principal, historico,
        complementares=["Salmos 23.1,2", "Romanos 99.1", "Salmos 119.1-20"],
    )  # fmt: skip
    assert not r.ok
    msg = " ".join(r.erros)
    assert "últimos 30 dias" in msg and "não existe" in msg and "mais de 6" in msg


def test_citacao_longa_entre_aspas_e_rejeitada(repo, principal):
    p3 = P3 + " O texto diz “o amor tudo sofre e tudo crê e tudo espera sempre”."
    r = checar(repo, principal, paragrafos=[P1, P2, p3])
    assert any("citação longa" in e for e in r.erros)
    ok = checar(repo, principal, paragrafos=[P1, P2, P3 + " É uma “paz que transborda” mesmo."])
    assert not any("citação" in e for e in ok.erros)


def test_versiculo_copiado_sem_aspas_e_rejeitado(repo, principal):
    copiado = (
        P3
        + " Lembre que todas as coisas juntamente contribuem para o bem daqueles que amam a Deus."
    )
    r = checar(repo, principal, paragrafos=[P1, P2, copiado])
    assert any("idêntico ao texto bíblico" in e for e in r.erros)


def test_palavras_chave_minusculas_sem_duplicatas_e_aviso_de_repeticao(repo, principal):
    historico = validacao.Historico(palavras_chave={"cuidado"})
    r = checar(
        repo, principal, historico,
        palavras_chave=["Cuidado", "cuidado", "Confiança", "descanso"],
    )  # fmt: skip
    assert r.ok and r.palavras_chave == ["cuidado", "confiança", "descanso"]
    assert any("cuidado" in a for a in r.avisos)


def test_palavras_chave_insuficientes_depois_de_deduplicar(repo, principal):
    r = checar(repo, principal, palavras_chave=["paz", "Paz", "PAZ"])
    assert any("palavras-chave" in e for e in r.erros)


def test_referencia_em_texto_precisa_existir(repo, principal):
    r = checar(repo, principal, paragrafos=[P1, P2, P3 + " Veja também Judas 99 hoje."])
    assert any("Judas 99" in e for e in r.erros)


# ------------------------------------------------------------------ repositório


def estudo_ok(data, **sobre):
    base = dict(
        data=data, status="ok", ref="rom.8.28", titulo="T", frase_do_dia="F",
        paragrafos=["a"], complementar="psa.23.1-2", palavras_chave=["x"], modelo="m1",
        gerado_em=datetime(2026, 11, 1, 6),
    )  # fmt: skip
    return Estudo(**{**base, **sobre})


def test_repositorio_de_estudos(estudos):
    estudos.gravar_estudo(estudo_ok(date(2026, 11, 1)))
    estudos.gravar_estudo(estudo_ok(date(2026, 11, 2), modelo="m2"))
    estudos.gravar_estudo(estudo_ok(date(2026, 11, 3), status="falhou"))
    assert estudos.estudo(date(2026, 11, 1)).paragrafos == ["a"]
    assert estudos.estudo(date(2027, 1, 1)) is None
    assert [e.data.day for e in estudos.recentes(date(2026, 11, 4), 30)] == [1, 2]  # sem falhados
    assert [e.data.day for e in estudos.recentes(date(2026, 11, 2), 30)] == [1]
    assert [e.data.day for e in estudos.do_modelo_nao_revisados("m1")] == [1, 3]
    assert estudos.marcar_revisado(date(2026, 11, 1)) is True
    assert [e.data.day for e in estudos.do_modelo_nao_revisados("m1")] == [3]
    assert estudos.marcar_revisado(date(2026, 11, 1), False) is True
    assert estudos.marcar_revisado(date(2026, 11, 3)) is False  # falhou não se revisa
    assert estudos.marcar_revisado(date(2030, 1, 1)) is False


def test_referencias_usadas_nos_testes_existem(repo):
    for ref in ("Rm 8.28", "Sl 23.1,2", "Fp 4.6,7", "Is 41.10", "Lc 1.30,31"):
        assert repo.existe(parse_referencia(ref))
