# PLANO — Maná Diário

Marque `[x]` ao concluir. Anote decisões no fim de cada fase. Um commit (ou mais) por item.

## Fase 0 — Esqueleto
- [x] `git init`, `pyproject.toml` com `uv`, ruff, pytest; pacote `src/mana`
- [x] `config.py` com pydantic-settings e `.env.example`
- [x] CLI Typer com subcomandos vazios (`biblia`, `llm`, `gerar`, `servir`)
- [x] FastAPI mínimo com `/saude`
- [x] Verificar Podman (llm-server estava desligado: repetir o teste na Fase 1)/podman compose e o acesso ao llm-server de dentro de um container
      (AGENTS.md §13.1 e §13.3); anotar versões e resultado no AGENTS.md
- [x] Criar `Containerfile`, `.containerignore`, `compose.yaml`, `compose.local.yaml` e
      `compose.prod.yaml` conforme AGENTS.md §13; a subida local sobe o `/saude` em
      http://localhost:8000
- [x] `mana agendador` (laço vazio por enquanto, só log) rodando no serviço `agendador`

## Fase 1 — Contrato com o llm-server (somente leitura)
- [x] Ler a pasta do `llm-server` e preencher "Contrato observado" em `docs/LLM.md`
- [x] Se não houver endpoint genérico: parar e propor opções ao Marcos
- [x] Interface `ClienteLLM`, adaptador `llm_server.py`, `fabrica.py` + `mana llm testar`
- [x] Testes do cliente com respx

## Fase 2 — Bíblia local
- [x] Baixar a Bíblia Livre (eBible `porbr2018`, USFX), registrar `data/biblia/FONTE.md`
- [x] Crédito BLIVRE no rodapé e no popover
- [x] Importador USFX → SQLite com FTS5
- [x] Testes de integridade contra `data/livros.json`
- [x] Parser de referências + `linkar_referencias()` + tabela de testes
- [x] `/api/passagem`

## Fase 3 — Interface da Bíblia
- [x] Fontes locais (Nunito, Crimson Pro) e tokens de cor
- [x] `/biblia`, `/biblia/{livro}/{cap}` com destaque de versículo e navegação
- [x] `ref-popover.js` (hover, foco, toque, Esc, cache)
- [x] `/biblia/busca`

## Fase 4 — Acervo e calendário
- [x] Definir a lista fechada de temas (~25) no topo de `data/versiculos.yaml`
- [x] Montar o acervo em lotes de ~200 referências (1 a 3 versículos), até ≥ 1.100,
      cobrindo os 66 livros com peso maior em Salmos, Provérbios, Evangelhos e Epístolas;
      ≥ 3 entradas por ocasião especial (tabela do AGENTS.md §6.1)
- [x] `datas_especiais.py` (fixas + móveis a partir da Páscoa) + testes com datas conhecidas
- [x] `mana acervo validar` + testes (resolvem no banco, sem duplicatas, temas válidos)
- [x] `mana calendario gerar/importar` com as regras do AGENTS.md §6.1 + testes
- [x] Gerar 2026 (restante) e 2027 e entregar `data/calendarios/` para revisão do Marcos

## Fase 5 — Geração diária
- [x] Modelos Pydantic, repositório de estudos (`data/mana.sqlite`)
- [x] Gerador: prompt v1, validações de `docs/LLM.md`, até 3 tentativas, registro de falhas
- [x] `mana gerar --data`, `--proximos N`, `--forcar`
- [x] Campos `provedor`, `modelo`, `revisado`; `mana gerar --regerar-modelo`
- [ ] Gerar 7 dias reais com a LLM de teste e revisar com o Marcos; ajustar prompt (v2 se preciso)
      (7 dias gerados em 31/10–06/11 com `gemma-4-e4b-it`; falta a revisão do Marcos — ver Decisões)
- [x] Faixa "ambiente de testes" quando `MODO_TESTE=true`

## Fase 6 — Página do dia
- [ ] Template conforme `docs/DESIGN.md` (desktop e mobile, claro e escuro)
- [ ] Favicon a partir da tigela do logo (`assets/logo-mana.svg` já está pronto)
- [ ] `/`, `/estudo/{data}` (404 no futuro), `/estudos`, navegação no rodapé
- [ ] Estado "Estudo em preparação" quando `status='falhou'` ou ausente
- [ ] Metadados Open Graph (título, frase do dia) para compartilhamento

## Fase 7 — Operação
- [ ] `mana agendador` completo: recuperação, 00:10, backup, calendário em 1º/12 + testes
      com relógio falso
- [ ] Testar `compose.prod.yaml` localmente (sem código montado) antes de levar ao servidor
- [ ] README: linger + `podman-restart.service` para subir no boot
- [ ] Levar ao servidor definitivo seguindo AGENTS.md §13 (Marcos acompanha)
- [ ] README curto com instalação e operação

## Fase 8 — Provedor definitivo (quando o Marcos escolher)
- [ ] Adaptador do novo provedor, prompt v2 se necessário, regerar estudos de teste

## Decisões
- Fase 5: 7 dias gerados com o gemma-4-e4b-it (sem thinking): ~31 s por estudo, 6 de 7 aprovados na 1ª tentativa; o 7º foi recusado 2× por título > 6 palavras e estudo < 220 palavras e passou na 3ª (o motivo vai no prompt seguinte). Os estudos têm ~240–290 palavras (o prompt pede ~300). Se o Marcos quiser mais corpo ou títulos mais curtos, criar `prompts/estudo_diario.v2.md` (não editar a v1). Revisar com `mana revisar --data AAAA-MM-DD`.
- Fase 4: acervo com 1.594 entradas (AT 670 / NT 924; 66 livros; 116 de ocasiões, de 5 a 8 por ocasião), 30 temas. Cinco anos seguidos (2026–2030) gerados sem aviso e sem violar nenhuma regra. O NT ficou maior que o AT no acervo para a janela de 3 anos não apertar o NT (o calendário usa ~55% NT).
- Fase 4: entradas com ocasião são reservadas a ela (não caem em dia comum); empate entre ocasiões: vale a cristã sobre a civil (ex.: 2035, sem Dia das Mães).
- Fase 4: `data/calendarios/2026.yaml` (31/10 a 31/12) e `2027.yaml` gerados para revisão do Marcos; o banco `data/mana.sqlite` fica fora do git, então no servidor basta rodar `calendario importar` com esses YAMLs.
- Fase 3: terracota escurecida para `#965220` / `#A15C29` (os valores do DESIGN.md originais ficavam abaixo de AA); detalhes no DESIGN.md. Fontes `woff2` latin + latin-ext em `static/fonts/`.
- Fase 3: o seletor de livro/capítulo funciona sem JavaScript (`/biblia/ir`); `?destacar=3-5` destaca a faixa no servidor e `:target` cobre o `#vN`.
- Fase 3: Playwright (já previsto como opcional) entrou no grupo `dev` para testar o popover; o teste é pulado se o Chromium não estiver instalado (`uv run playwright install chromium`).
- Fase 2: texto do USFX sem notas de rodapé (`f`) nem referências cruzadas (`rq`); palavras acrescentadas (`add`) mantidas como texto simples. 31.102 versículos. Versão da BLIVRE: fevereiro de 2018 (eBible atualizou o pacote em 08/03/2022).
- Referências: duas formas — canônica (`rom.5.3-4`, vários trechos separados por `;`) e de exibição (`Romanos 5.3,4`; 2 versículos seguidos viram `3,4`, 3 ou mais `3-5`).
- Bíblia: Bíblia Livre (CC BY 4.0, linhagem Almeida 1819). A "Almeida" do open-bibles foi descartada (texto com direitos).
- LLM atual (llm-server) é temporária; provedor trocável por `.env`.
- Versículo principal vem de acervo curado (≥ 1.100, 3 anos sem repetir) via calendário anual; a LLM só escolhe o complementar (dentre 3 candidatas validadas).
- Texto bíblico nunca passa pela LLM como saída.
