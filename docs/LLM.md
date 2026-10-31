# Integração com a LLM

## 0. Provedor temporário × definitivo

O `llm-server` abaixo é **temporário, só para testes**. A versão final usará uma LLM mais
confiável, ainda a definir. Por isso:

- o gerador só conhece a interface `ClienteLLM` (`llm/base.py`); cada provedor é um
  adaptador (`llm/llm_server.py` agora; outro depois), escolhido por `LLM_PROVEDOR`;
- o prompt, o esquema e todas as validações são independentes do provedor;
- cada estudo grava `provedor` e `modelo`; o campo `revisado` (bool) marca o que o Marcos
  aprovou. Ao trocar de provedor, `mana gerar --regerar-modelo <nome>` refaz os estudos
  futuros e os não revisados gerados pelo modelo de teste — nunca os já revisados;
- enquanto `LLM_PROVEDOR=llm-server`, o site mostra uma faixa discreta "ambiente de
  testes" (configurável por `MODO_TESTE=true`).

Os limites de tamanho abaixo foram pensados para um modelo pequeno; com o provedor final,
podem ser revistos em `prompts/estudo_diario.v2.md` sem tocar no código.

## 1. Onde está (provedor temporário)

```
/home/marcos/OneDriveLocalSync/LinguagensProgramacao/Android/CacaPalavras2/llm-server
```

Esse servidor é **compartilhado** com o app BuscaPalavras. Pelo que se sabe, é um
`llama-server` (llama.cpp) com um modelo Qwen quantizado e uma camada FastAPI na frente.
**Confirme lendo a pasta — não presuma.**

**Regra:** somente leitura. Nenhum arquivo daquela pasta é alterado por este projeto.
Mudanças lá (novo endpoint, outro modelo, outra porta) são propostas ao Marcos.

## 2. Primeira tarefa: descobrir o contrato

1. Leia README, arquivos de compose/scripts de start, `.env.example` e o código FastAPI do
   `llm-server`.
2. Responda e registre na seção 6 deste arquivo ("Contrato observado"):
   - URL base e porta; se roda local ou no servidor na nuvem;
   - autenticação (header, token, variável de ambiente);
   - endpoints disponíveis: existe um genérico (`/v1/chat/completions` do llama-server,
     ou um `/gerar` próprio) ou só endpoints específicos do caça-palavras?
   - suporte a saída estruturada: `response_format` com `json_schema`, `grammar` (GBNF)
     ou nada;
   - modelo carregado, tamanho de contexto, limites de taxa/timeout.
3. Se **só** houver endpoints específicos do caça-palavras, pare e proponha ao Marcos uma
   das opções: (a) usar diretamente a porta do `llama-server` por trás do FastAPI, ou
   (b) ele adicionar um endpoint genérico. Não contorne sozinho.

## 3. Interface e adaptadores (`src/mana/llm/`)

```python
class ClienteLLM(Protocol):
    async def gerar_json(
        self,
        sistema: str,
        usuario: str,
        esquema: dict,
        temperatura: float = 0.7,
        max_tokens: int = 1200,
    ) -> dict: ...
```

- `llm_server.py` implementa o contrato observado; configuração via `.env`
  (`LLM_PROVEDOR=llm-server`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODELO`,
  `LLM_TIMEOUT_S=120`).
- Novos provedores entram como novo arquivo + uma linha em `fabrica.py`. Não implemente o
  provedor definitivo antes de o Marcos escolher.
- Se o servidor aceitar `json_schema`, use-o (no llama-server, o esquema é convertido em
  gramática e o JSON sai sempre válido). Se não, peça JSON no prompt e faça parsing
  tolerante (remover cercas ```json, pegar do primeiro `{` ao último `}`).
- Retentativas com backoff para erros de rede/5xx (3x); timeout não é erro de validação.
- `uv run mana llm testar` faz uma chamada mínima e mostra latência e modelo.

## 4. Esquema da resposta

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["titulo", "frase_do_dia", "paragrafos", "complementares", "palavras_chave"],
  "properties": {
    "titulo":         {"type": "string", "minLength": 3, "maxLength": 48},
    "frase_do_dia":   {"type": "string", "minLength": 20, "maxLength": 140},
    "paragrafos":     {"type": "array", "minItems": 3, "maxItems": 4,
                       "items": {"type": "string", "minLength": 200, "maxLength": 900}},
    "complementares": {"type": "array", "minItems": 3, "maxItems": 3,
                       "items": {"type": "string", "maxLength": 40}},
    "palavras_chave": {"type": "array", "minItems": 3, "maxItems": 5,
                       "items": {"type": "string", "maxLength": 24}}
  }
}
```

`complementares` são **três candidatas em ordem de preferência** — só referências, sem
texto. O código escolhe a primeira válida (ver regras).

## 5. Regras de validação (além do esquema)

1. Título com no máximo 6 palavras; frase do dia com no máximo 18.
2. Total do estudo entre 220 e 420 palavras.
3. Cada candidata complementar é parseada e resolvida no banco. Escolhe-se a primeira que:
   existe; não sobrepõe o versículo principal; não foi usada nos últimos 30 dias; tem no
   máximo 6 versículos. Nenhuma válida → nova tentativa.
4. Todas as referências citadas nos parágrafos são resolvidas; se alguma não existir,
   nova tentativa (mencionando no prompt qual referência estava errada).
5. Nenhum trecho entre aspas com mais de 6 palavras (sinal de versículo "citado de cabeça"
   pela LLM). Se houver, nova tentativa.
6. Palavras-chave: minúsculas, sem duplicatas, sem repetir as 30 mais recentes de forma
   idêntica quando possível (aviso, não erro).
7. Até **3 tentativas** por data; depois `status='falhou'`.

Grave no banco: JSON bruto, modelo, `versao_prompt` (ex.: `estudo_diario.v1`), tentativas,
tempo de geração e motivo de cada rejeição — isso orienta ajustes no prompt.

## 6. Contrato observado

> Preencher na Fase 1, depois de ler o `llm-server`.

- URL base:
- Autenticação:
- Endpoint usado:
- Saída estruturada:
- Modelo / contexto:
- Observações:
