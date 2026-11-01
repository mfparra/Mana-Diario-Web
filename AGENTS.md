# AGENTS.md — Maná Diário

Instruções para agentes de código (Claude Code e outros) que trabalham neste repositório.
Leia este arquivo inteiro antes de qualquer alteração. Detalhes ficam em `docs/` e o
andamento em `PLANO.md`.

## 1. O que é o projeto

**Maná Diário** é um site que publica, todo dia, um pequeno estudo bíblico baseado em um
versículo. A página do dia mostra:

- o nome do site com o logo (maná em uma tigela, nome em arco por cima) — `assets/logo-mana.svg`;
- o **versículo do dia** (texto vindo da Bíblia local, nunca da LLM);
- um **título** e um **estudo curto** (3–4 parágrafos);
- uma **frase do dia** em destaque na coluna lateral;
- um **versículo complementar** (indicação de leitura);
- **palavras-chave** do estudo.

Toda referência bíblica exibida no site (no versículo do dia, no corpo do estudo, no
versículo complementar) é um link: **ao passar o mouse** aparece o texto do versículo; **ao
clicar** abre a interface de leitura da Bíblia naquele capítulo, com o versículo destacado.

O design segue a página de devocional usada como referência — ver `docs/DESIGN.md`.

## 2. Regras inegociáveis

1. **Texto bíblico só vem da Bíblia local** (`data/biblia/biblia.sqlite`). A LLM nunca
   escreve, cita ou "completa" texto de versículo. Ela produz apenas referências
   (ex.: `Romanos 8.28`), que o código resolve contra o banco local.
2. **Tudo que não é versículo é gerado pela LLM** (título, estudo, frase, palavras-chave,
   escolha do versículo complementar), validado pelo código antes de ser publicado.
3. **Edição da Bíblia: Bíblia Livre (BLIVRE)**, revisão da Almeida de 1819, licença
   CC BY 4.0 — com crédito visível em todas as páginas. Nunca baixe ARA, ARC (SBB), NAA,
   ACF, NVI, NVT, "Almeida Atualizada", "Almeida Recebida" nem o arquivo
   `por-almeida.usfx.xml` do open-bibles (é a Almeida Revisada de 1967 com direitos,
   divulgada como se fosse domínio público). Ver `docs/BIBLIA.md`.
4. **A LLM atual é temporária, só para testes.** É o `llm-server` compartilhado com outro
   projeto, em
   `/home/marcos/OneDriveLocalSync/LinguagensProgramacao/Android/CacaPalavras2/llm-server`.
   **Não edite nada nessa pasta.** Leia-a para entender a API; se precisar de mudança lá,
   pare e proponha ao Marcos. O código deve permitir trocar de provedor só por
   configuração (`.env`), sem mexer no gerador. Ver `docs/LLM.md`.
5. Conteúdo, interface, mensagens de commit e comentários em **português do Brasil**.
   Nomes de identificadores em código podem ser em português (preferido) ou inglês, mas
   sem misturar dentro do mesmo módulo.
6. "Hoje" é sempre calculado em `America/Sao_Paulo`.
7. Nunca exponha estudos de datas futuras no site público.
8. Segredos só em `.env` (nunca commitado). Mantenha `.env.example` atualizado.
9. Nada no código depende de estar num container ou fora dele: caminhos e URLs vêm do `.env`.
10. Containers só com **Podman** e **podman compose** (rootless). Não use comandos `docker`
    nem recursos que só existem no Docker. Ver seção 13.

## 3. Stack

| Camada | Escolha |
|---|---|
| Linguagem | Python 3.12, gerenciado com `uv` |
| Web | FastAPI + Jinja2 (renderização no servidor) |
| Front-end | HTML + CSS + JavaScript puro (sem framework, sem build step) |
| Banco | SQLite: `data/biblia/biblia.sqlite` (Bíblia, com FTS5) e `data/mana.sqlite` (estudos e calendário) |
| Cliente LLM | `httpx` (assíncrono), atrás de uma interface `ClienteLLM` com um adaptador por provedor |
| Validação | Pydantic v2 |
| CLI | Typer (`uv run mana ...`) |
| Dados e datas | PyYAML; `zoneinfo`; `python-dateutil` (cálculo da Páscoa) |
| Agendamento | serviço `agendador` no podman compose (`mana agendador`, laço em Python, sem cron) |
| Testes | pytest, pytest-asyncio, respx (mock HTTP); Playwright opcional para o hover |
| Qualidade | ruff (lint + format) |
| Execução e deploy | **Podman + podman compose** (rootless) — o mesmo `compose.yaml` roda local e no servidor; ver seção 13 |

Não adicione dependências fora desta lista sem justificar no PR/commit.

## 4. Estrutura de pastas (alvo)

```
mana-diario/
├── AGENTS.md            # este arquivo
├── CLAUDE.md            # importa o AGENTS.md para o Claude Code
├── PLANO.md             # fases e checklist do trabalho
├── pyproject.toml
├── .env.example
├── assets/
│   └── logo-mana.svg    # logo pronto (texto já em curvas)
├── docs/
│   ├── DESIGN.md        # layout, cores, tipografia, responsividade
│   ├── BIBLIA.md        # fonte da Bíblia, esquema do banco, parser de referências
│   └── LLM.md           # integração com o llm-server, contrato, validação
├── prompts/
│   └── estudo_diario.v1.md
├── data/
│   ├── livros.json              # 66 livros: nome, slug, abreviações, nº de capítulos
│   ├── versiculos.yaml          # acervo curado do versículo do dia (só referências, ~1.100+)
│   ├── calendarios/             # AAAA.yaml gerado a partir do acervo, para revisão
│   └── biblia/                  # gerado pelo script (raw/ fica fora do git)
├── src/mana/
│   ├── __init__.py
│   ├── config.py        # pydantic-settings, lê .env
│   ├── cli.py           # Typer: biblia, acervo, calendario, llm, gerar, servir, agendador
│   ├── agendador.py     # laço diário (gerar, backup, calendário do ano seguinte)
│   ├── biblia/
│   │   ├── importar.py  # download + conversão para SQLite
│   │   ├── repositorio.py
│   │   └── referencias.py  # parser e formatador de referências pt-BR
│   ├── tempo.py         # hoje() no fuso America/Sao_Paulo
│   ├── estudos/
│   │   ├── acervo.py          # lê e valida data/versiculos.yaml
│   │   ├── calendario.py      # monta o calendário anual a partir do acervo
│   │   ├── datas_especiais.py # datas fixas e móveis (Páscoa e derivadas)
│   │   ├── gerador.py   # monta prompt, chama LLM, valida, tenta de novo
│   │   ├── modelos.py   # Pydantic: EstudoGerado, Estudo
│   │   └── repositorio.py
│   ├── llm/
│   │   ├── base.py        # interface ClienteLLM
│   │   ├── llm_server.py  # adaptador temporário (testes)
│   │   └── fabrica.py     # escolhe o adaptador por LLM_PROVEDOR
│   └── web/
│       ├── app.py
│       ├── rotas.py
│       ├── templates/   # base, estudo, biblia_*, 404
│       └── static/      # css/, js/ref-popover.js, fonts/, img/
├── Containerfile             # a criar na Fase 0 (seção 13)
├── .containerignore          # a criar na Fase 0
├── compose.yaml              # a criar: base comum (web + agendador, volume de dados)
├── compose.local.yaml        # a criar: ambiente local (reload, código montado)
├── compose.prod.yaml         # a criar: servidor definitivo
└── tests/
```

## 5. Comandos

```bash
uv sync                                   # instala dependências
uv run mana biblia baixar                 # baixa a Bíblia Livre para data/biblia/raw/
uv run mana biblia importar               # converte para data/biblia/biblia.sqlite e valida
uv run mana acervo validar                # confere o acervo (--sem-minimos enquanto ele cresce)
uv run mana calendario gerar --ano 2027   # monta o calendário do ano (data/calendarios/2027.yaml)
                                          #   --refazer: refaz os dias futuros que já existem
uv run mana calendario importar --ano 2027  # aplica as edições feitas no YAML do ano
uv run mana llm testar                    # faz uma chamada mínima ao provedor configurado
uv run mana gerar --data hoje             # gera (ou regenera com --forcar) o estudo do dia
uv run mana gerar --proximos 7            # pré-gera os próximos 7 dias
uv run mana gerar --regerar-modelo X      # refaz estudos futuros/sem revisão feitos pelo modelo X
uv run mana servir                        # sobe o site em http://localhost:8000
uv run mana agendador                     # laço diário (o mesmo que roda no container)
uv run pytest                             # testes
uv run playwright install chromium        # uma vez, para o teste do popover (opcional)
uv run ruff check . && uv run ruff format .

# podman compose (local) — é assim que o projeto é testado de ponta a ponta
podman compose -f compose.yaml -f compose.local.yaml up --build    # site em http://localhost:8000 + agendador
podman compose -f compose.yaml -f compose.local.yaml run --rm web mana gerar --data hoje
podman compose -f compose.yaml -f compose.local.yaml logs -f agendador

# Servidor definitivo
podman compose -f compose.yaml -f compose.prod.yaml up -d --build
```

Desenvolvimento rápido (testes, lint) pode ser com `uv run` no host; toda fase termina
com o projeto funcionando via `podman compose ... up`.

Mantenha esta seção sincronizada com a CLI real.

## 6. Fluxo do estudo diário

1. **Seleção** (`estudos/calendario.py`): o versículo do dia vem do **calendário anual**
   (tabela `calendario` em `data/mana.sqlite`), montado a partir do acervo curado
   `data/versiculos.yaml` (só referências, com temas e ocasiões). Regras na seção 6.1.
   A LLM não escolhe o versículo principal.
2. **Prompt** (`prompts/estudo_diario.v1.md`): recebe referência, texto do versículo (do
   banco), data, a ocasião do dia (se houver — o estudo deve tratar dela) e as referências
   complementares e palavras-chave usadas nos últimos 30 dias (para evitar repetição).
   O comentário `<!-- ... -->` do topo do arquivo é removido antes de preencher os campos.
3. **Chamada à LLM**: saída em JSON restrito por esquema (ver `docs/LLM.md`).
4. **Validação** (Pydantic + regras): tamanhos, referências existentes no banco, versículo
   complementar diferente do principal e não repetido nos últimos 30 dias, nenhuma citação
   longa entre aspas (indício de texto bíblico inventado). Até 3 tentativas.
5. **Gravação** no banco de estudos (`MANA_DB`) com `ocasiao`, `provedor`, `modelo`,
   `versao_prompt`, `tentativas`, `revisado` e o JSON bruto.
6. **Falha**: se nada passar na validação, grava `status = 'falhou'` e a página mostra o
   versículo do dia com a mensagem "Estudo em preparação". Nunca publique conteúdo inválido.

O serviço `agendador` (`mana agendador`) roda num laço: ao iniciar, faz uma rodada de
recuperação; depois dorme até 00:10 (America/Sao_Paulo) e, a cada dia, pré-gera 7 dias à
frente — assim uma queda da LLM não deixa o site sem estudo —, faz backup do
`mana.sqlite` (API de backup do SQLite, guarda 14 cópias em `/dados/backups`) e, em 1º de
dezembro, monta o calendário do ano seguinte se ainda não existir. Encerra limpo com SIGTERM.
Os dois containers abrem o mesmo `mana.sqlite`: use modo WAL e `busy_timeout`, e crie o
esquema de forma idempotente (qualquer um dos dois pode subir primeiro).

### 6.1 Acervo e calendário (vários anos sem repetir)

- `data/versiculos.yaml`: cada entrada tem `ref` (1 a 3 versículos), `temas` (1–3, de uma
  lista fechada no topo do arquivo) e, opcionalmente, `ocasioes` (códigos da tabela
  abaixo). Meta inicial: **≥ 1.100 entradas** (3 anos sem repetição); o acervo pode crescer
  à vontade.
- **Datas especiais** (`estudos/datas_especiais.py`, calculadas para qualquer ano; móveis a
  partir da Páscoa de `dateutil.easter`):

  | Código | Ocasião | Regra |
  |---|---|---|
  | `ano-novo` | Ano-Novo | 1/1 |
  | `epifania` | Epifania | 6/1 |
  | `cinzas` | Quarta-feira de Cinzas | Páscoa − 46 |
  | `ramos` | Domingo de Ramos | Páscoa − 7 |
  | `quinta-santa` | Quinta-feira Santa | Páscoa − 3 |
  | `sexta-santa` | Sexta-feira Santa | Páscoa − 2 |
  | `pascoa` | Páscoa | `easter(ano)` |
  | `ascensao` | Ascensão | Páscoa + 39 |
  | `pentecostes` | Pentecostes | Páscoa + 49 |
  | `dia-das-maes` | Dia das Mães | 2º domingo de maio |
  | `trindade` | Santíssima Trindade | Páscoa + 56 |
  | `corpus-christi` | Corpus Christi | Páscoa + 60 |
  | `dia-dos-pais` | Dia dos Pais | 2º domingo de agosto |
  | `advento` | 1º Domingo do Advento | 1º domingo a partir de 27/11 |
  | `vespera-natal` | Véspera de Natal | 24/12 |
  | `natal` | Natal | 25/12 |
  | `fim-de-ano` | Último dia do ano | 31/12 |

  A lista fica num dicionário único (código → nome, regra) para poder ligar/desligar
  ocasiões por configuração (`OCASIOES_ATIVAS`, padrão: todas). Teste com datas conhecidas:
  Páscoa 2026 = 05/04, Corpus Christi 2026 = 04/06, Páscoa 2027 = 28/03,
  Corpus Christi 2027 = 27/05, Advento 2028 = 03/12, Dia das Mães 2027 = 09/05,
  Dia dos Pais 2027 = 08/08.
  Se duas ocasiões caírem no mesmo dia (ex.: Dia das Mães e Pentecostes), vale a de maior
  prioridade: datas do calendário cristão antes das civis (Mães, Pais).
- `mana calendario gerar --ano AAAA` monta o ano de forma determinística (semente = ano):
  - nenhuma referência repete dentro de **1.095 dias** (3 anos); se o acervo não bastar,
    a janela diminui e o comando avisa;
  - datas especiais primeiro: cada uma recebe uma referência do acervo marcada com aquela
    ocasião (a janela de não repetição vale também aqui, por isso cada ocasião precisa de
    ≥ 3 entradas no acervo);
  - o mesmo livro no máximo 2 dias seguidos; o mesmo tema nunca em dias seguidos;
  - proporção aproximada de 45% AT / 55% NT; Salmos + Provérbios ≤ 25% do ano.
- O resultado vai para a tabela `calendario` e é exportado em `CALENDARIOS_DIR/AAAA.yaml`
  (padrão `data/calendarios/`)
  para o Marcos revisar e editar; `mana calendario importar --ano AAAA` aplica as edições.
  Um dia já publicado nunca muda de versículo: `importar` recusa (e não grava nada) qualquer
  mudança em dia que já exista e seja de hoje ou anterior; `gerar --refazer` só apaga dias futuros.
- Entradas do acervo com `ocasioes` são **reservadas** a elas: nunca caem em dia comum.
  Em anos de empate (ex.: Pentecostes = 2º domingo de maio, em 2035) a ocasião civil some.
- A escolha entre candidatas é sorteada com peso pelo tempo desde o último uso (as menos
  usadas primeiro), com a semente do ano; tudo é checado de novo por `calendario.verificar()`.

## 7. Referências bíblicas no site

- O parser (`biblia/referencias.py`) entende o formato brasileiro e variações:
  `Romanos 5.3,4`, `Tiago 1.2-4`, `Rm 8:28`, `1 Coríntios 13`, `I Co 13.4-7`, `Jo 3.16; 14.6`.
- No servidor, o texto gerado passa por `linkar_referencias()`, que transforma cada
  referência válida em
  `<a class="ref" href="/biblia/romanos/8#v28" data-ref="rom.8.28">Romanos 8.28</a>`.
  O `data-ref` usa o código USFM do livro em minúsculas (`rom`, `exo`, `1co`, `job`), sempre
  ASCII. Referências que não resolvem ficam como texto puro (e são registradas em log).
- Em texto livre, abreviações só viram link quando seguidas de capítulo **e** versículo
  (`Os 6.6` sim; "os 12 discípulos" e "Is 40" não). Nomes completos aceitam só o capítulo
  (`Isaías 40`). Detalhes em `docs/BIBLIA.md` §5.
- No cliente, `static/js/ref-popover.js` busca `/api/passagem?ref=rom.8.28` (com cache em
  memória), mostra o popover após ~150 ms de hover ou ao focar pelo teclado, e esconde ao
  sair. Em toque: o primeiro toque abre o popover com o botão "Abrir na Bíblia"; o link
  navega no segundo toque.
- Formato de exibição padrão: `Livro capítulo.versículo` (ex.: `Romanos 5.3,4`).

## 8. Rotas

| Rota | Conteúdo |
|---|---|
| `/` | estudo de hoje |
| `/estudo/AAAA-MM-DD` | estudo de uma data passada (404 para datas futuras) |
| `/estudos` | arquivo, por mês |
| `/biblia` | lista de livros (AT/NT) |
| `/biblia/{slug}/{capitulo}` | leitura do capítulo; `#vN` destaca o versículo |
| `/biblia/busca?q=` | busca no texto (FTS5) |
| `/api/passagem?ref=` | JSON `{referencia, url, versiculos: [{numero, texto}]}` |
| `/saude` | healthcheck |

## 9. Convenções

- Funções pequenas, tipadas, com docstring curta em português quando o nome não basta.
- Acesso a banco somente pelos módulos `repositorio.py`.
- Nada de lógica de negócio nos templates.
- CSS com variáveis em `:root` (tokens do `docs/DESIGN.md`), modo escuro via
  `prefers-color-scheme`. Fontes servidas localmente em `static/fonts/` (sem CDN).
- Commits pequenos, mensagem em português no imperativo (`Adiciona parser de referências`).

## 10. Testes obrigatórios

- Parser de referências: tabela de casos (todos os formatos da seção 7, abreviações com e
  sem acento, numerais romanos e arábicos, intervalos que cruzam capítulos, referências
  inválidas, `Jó 3.1` × `Jo 3.16`, e falsos positivos em texto livre como "os 12
  discípulos", "na 1ª carta", "Am 3" sem versículo).
- Integridade da Bíblia: 66 livros, 1.189 capítulos, nº de capítulos por livro igual a
  `data/livros.json`, nenhum versículo vazio.
- `versiculos.yaml`: todas as referências resolvem no banco, sem duplicatas, temas da
  lista fechada; a partir do fim da Fase 4, ≥ 1.100 entradas e ≥ 3 por ocasião ativa.
- Calendário: determinístico para a mesma semente; respeita a janela sem repetição, as
  datas especiais e os limites de livro/tema; anos bissextos.
- Validador da saída da LLM com fixtures boas e ruins.
- Gerador com LLM mockada (respx): sucesso, JSON inválido, referência inexistente, timeout.
- Rotas: `/`, `/estudo/<futuro>` → 404, `/api/passagem` com ref válida e inválida.

## 11. Definição de pronto (por tarefa)

- Testes passando e `ruff` limpo.
- `PLANO.md` atualizado (checkbox marcado, decisões anotadas).
- Se mudou comando, rota ou contrato com a LLM: este arquivo ou o `docs/` correspondente
  atualizado no mesmo commit.
- Para mudanças visuais: conferir em 375 px e 1280 px de largura, claro e escuro.

## 12. Quando parar e perguntar

- Qualquer alteração necessária no `llm-server`.
- Antes de ligar o provedor de LLM definitivo (custo e chave de API são decisão do Marcos).
- Escolha final da edição da Bíblia, se a licença não estiver clara.
- Mudança de stack ou de hospedagem.
- Conteúdo teológico sensível que o validador não consegue decidir.

## 13. Podman e podman compose (local → servidor definitivo)

O projeto roda em containers com **Podman rootless** e **podman compose** desde a Fase 0:
primeiro na máquina do Marcos, para testes, depois no servidor definitivo com os mesmos
arquivos. Esses arquivos ainda **não existem**; crie-os na Fase 0 seguindo isto.

### 13.1 Antes de começar

- Rode `podman --version`, `podman compose version` e `podman info --format
  '{{.Host.NetworkBackend}} {{.Host.Security.Rootless}}'` e anote as versões aqui (Podman
  5.x esperado). `podman compose` é um invólucro: confirme que o provedor por trás dele é o
  `podman-compose` (pacote da distribuição). Se não for, pare e pergunte ao Marcos.
- Não presuma recursos do Docker Compose: o `podman-compose` não cobre tudo. Prefira o
  subconjunto simples descrito abaixo e valide cada arquivo com `podman compose ... config`.

### 13.2 Imagem (`Containerfile`)

- Base com nome **totalmente qualificado** (o Podman não resolve nomes curtos sem perguntar):
  `docker.io/library/python:3.12-slim`; `uv` copiado de `ghcr.io/astral-sh/uv:<versão fixa>`.
- Instalar `tzdata`; `TZ=America/Sao_Paulo`; `uv sync --frozen --no-dev` em duas etapas
  (dependências antes do código, para cache); usuário sem root com **uid 1000**.
- **Não use `HEALTHCHECK` no Containerfile**: o Podman constrói no formato OCI, que descarta
  essa instrução. O healthcheck vai no `compose.yaml`.
- Dentro da imagem: `src/`, `prompts/`, `data/` (inclui `data/biblia/biblia.sqlite`,
  versionado no git — a licença CC BY permite). Fora (`.containerignore`): `.env`, `.git`,
  `.venv`, `tests/`, `docs/`, `data/biblia/raw/`, `data/mana.sqlite*`.
- Tag local: `localhost/mana-diario:${MANA_TAG}`.

### 13.3 Serviços e arquivos

- **Uma imagem, dois serviços**:
  - `web` — `uvicorn mana.web.app:app` na porta 8000, com `--proxy-headers` (no servidor
    fica atrás de um proxy reverso com HTTPS); healthcheck no compose chamando `/saude`
    com Python (`urllib`), sem depender de `curl` na imagem;
  - `agendador` — `mana agendador` (seção 6).
- **Sem `depends_on` com `condition: service_healthy`** (suporte irregular no
  `podman-compose`); os dois serviços se viram sozinhos (esquema idempotente, seção 6).
- **Dados que mudam** num volume nomeado montado em `/dados`: `MANA_DB=/dados/mana.sqlite`,
  `/dados/backups/`, `CALENDARIOS_DIR=/dados/calendarios`. Volume em disco local, nunca em
  compartilhamento de rede (SQLite).
- **Arquivos** (sempre com `-f` explícito; não conte com carga automática de override):
  - `compose.yaml` — base comum: os dois serviços (bloco `x-app` reutilizado com âncora
    YAML), `build` com `context: .` e `dockerfile: Containerfile`, `env_file: .env`,
    volume, `restart: unless-stopped`, porta publicada só em
    `127.0.0.1:${PORTA_HOST:-8000}`.
  - `compose.local.yaml` — **local**: `--reload`; `src/` e `prompts/` montados só leitura
    (`:ro,z`); `./data/calendarios` montado em `CALENDARIOS_DIR` (`:z`) para o Marcos
    editar; `userns_mode: keep-id` para que arquivos criados nos bind mounts fiquem com o
    usuário do Marcos (uid 1000) e não com um subuid.
  - `compose.prod.yaml` — **servidor**: sem código montado, sem reload, imagem com tag
    explícita (`MANA_TAG` obrigatório, ex. `2026.11.01`), logs no `journald`.
- **Acesso ao `llm-server` da máquina local**: dentro do container, `localhost` é o próprio
  container. Use `LLM_BASE_URL=http://host.containers.internal:8080` (nome que o Podman
  injeta no `/etc/hosts`). O llama-server precisa escutar em `0.0.0.0`. Teste antes de
  codificar:
  `podman run --rm docker.io/library/python:3.12-slim python -c "import urllib.request;print(urllib.request.urlopen('http://host.containers.internal:8080/health').status)"`.
  Se falhar (rede `pasta` com o serviço só em loopback, por exemplo), registre o erro aqui
  e pergunte ao Marcos antes de mudar a rede.
- **SELinux**: em hosts com SELinux (comum em servidores Fedora/RHEL), bind mounts precisam
  de `:Z`; em hosts sem SELinux a opção é ignorada — use sempre.

### 13.4 Subida automática e servidor

- Rootless não sobe sozinho no boot. No servidor (e na máquina local, se o Marcos quiser):
  `loginctl enable-linger <usuário>` e `systemctl --user enable --now podman-restart.service`
  (reinicia containers com `restart: unless-stopped`/`always`). Documente isso no README;
  não rode comandos de sistema sem pedir.
- Levar ao servidor: `git clone`/`git pull`, criar o `.env` de produção (com o provedor de
  LLM definitivo quando houver), `podman compose -f compose.yaml -f compose.prod.yaml up -d
  --build` e apontar o proxy reverso para `127.0.0.1:${PORTA_HOST}`.
- Migrar estudos já revisados: `podman volume export <projeto>_mana-dados -o dados.tar`
  na máquina local e `podman volume import <projeto>_mana-dados dados.tar` no servidor,
  antes de subir (confira o nome real com `podman volume ls`).
- Alternativa para depois, se o `podman-compose` limitar a operação no servidor: Quadlet
  (unidades systemd geradas a partir de `.container`/`.volume`). Só com aprovação do Marcos.

### 13.5 Validação

- `podman compose -f compose.yaml -f compose.local.yaml config` e
  `podman compose -f compose.yaml -f compose.prod.yaml config` sem erro fazem parte da
  definição de pronto de qualquer mudança nesses arquivos.
- Ao fim de cada fase, a subida local com `podman compose ... up --build` precisa funcionar
  e `/saude` responder.

### 13.6 Ambiente verificado (Fase 0, 31/10/2026)

- Podman 5.8.9, rede netavark, rootless. O shell do Claude Code roda num distrobox: `podman`
  é um atalho (`distrobox-host-exec`) para o host; `podman compose` e
  `distrobox-host-exec podman compose` dão o mesmo resultado — use `podman compose`.
- **O provedor é o Docker Compose v5.6.1** (`~/.docker/cli-plugins/docker-compose`), não o
  `podman-compose`; aprovado pelo Marcos. Ele usa o socket do Podman (`podman.socket` ativo).
- Com dois serviços montando as mesmas pastas, use `:z` (compartilhado), não `:Z`: com `:Z`
  o último container a subir reetiqueta a pasta e o outro recebe "Permission denied".
- A mensagem de `${VAR:?...}` no compose não pode conter `:` sem aspas.
- Acesso ao llm-server: `host.containers.internal:8081` dá *Connection refused* (o llm-server
  publica a porta só em loopback). Funciona entrando na rede externa `llm-net`
  (`compose.local.yaml`) e usando `LLM_BASE_URL=http://llm:8081/v1`. Subir o llm-server:
  `podman compose up -d` na pasta dele (a rede `llm-net` já existe). Ver `docs/LLM.md` §6.
