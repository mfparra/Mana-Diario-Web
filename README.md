# Maná Diário

Um pequeno estudo bíblico por dia, baseado em um versículo. O texto bíblico vem sempre da
Bíblia local (Bíblia Livre, CC BY 4.0); título, estudo, frase do dia e palavras-chave são
gerados por uma LLM e validados pelo código antes de aparecerem no site.

- Regras e arquitetura: [`AGENTS.md`](AGENTS.md) · andamento: [`PLANO.md`](PLANO.md)
- Design: [`docs/DESIGN.md`](docs/DESIGN.md) · Bíblia: [`docs/BIBLIA.md`](docs/BIBLIA.md) · LLM: [`docs/LLM.md`](docs/LLM.md)

## Desenvolvimento (no host)

Requer Python 3.12 e [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env          # e troque LLM_BASE_URL para http://127.0.0.1:8081/v1 se rodar fora do container
uv run mana acervo validar    # confere data/versiculos.yaml contra a Bíblia local
uv run mana calendario gerar --ano 2027
uv run mana gerar --data hoje # precisa da LLM no ar (ver docs/LLM.md §6)
uv run mana servir            # http://localhost:8000
uv run pytest && uv run ruff check .
```

A Bíblia (`data/biblia/biblia.sqlite`) já vem no repositório. Para refazê-la:
`uv run mana biblia baixar && uv run mana biblia importar`.

## Com Podman (local → servidor)

Só **Podman rootless + `podman compose`**; os mesmos arquivos servem local e servidor.

```bash
# local: reload, código montado, calendários editáveis em data/calendarios/
podman compose -f compose.yaml -f compose.local.yaml up --build
curl localhost:8000/saude

# servidor
MANA_TAG=2026.11.01 podman compose -f compose.yaml -f compose.prod.yaml up -d --build
```

Dois serviços, uma imagem: `web` (site, porta 8000 só em `127.0.0.1`) e `agendador`.
Os dados (`mana.sqlite`, backups, calendários) ficam no volume `mana-dados`, em `/dados`.

> Não alterne `local` e `prod` sobre o **mesmo volume** (o modo local usa `keep-id` e os arquivos
> ficam com outro dono: o banco passa a "somente leitura"). Em testes, use `-p outro-nome`.

### O que o agendador faz

Ao iniciar faz uma rodada de recuperação; depois, todo dia às 00:10 (America/Sao_Paulo):

1. garante o calendário do ano (importa `/dados/calendarios/AAAA.yaml` se existir; senão gera) e,
   em dezembro, o do ano seguinte;
2. gera o estudo de hoje e dos 7 dias seguintes (os que já estão prontos são pulados);
3. faz backup do banco em `/dados/backups/` (guarda 14).

Se o estudo de hoje não ficar pronto (ex.: a LLM caiu), tenta de novo a cada 30 minutos.
Encerra limpo com SIGTERM. Logs: `podman compose ... logs -f agendador`.

### Rotina de conteúdo

```bash
# revisar o calendário: editar data/calendarios/AAAA.yaml e aplicar
uv run mana calendario importar --ano 2027          # (no container: ... run --rm web mana calendario importar --ano 2027)
# marcar um estudo como revisado (não será refeito ao trocar de LLM)
uv run mana revisar --data 2026-11-02
# trocar de provedor de LLM: refazer o que não foi revisado
uv run mana gerar --regerar-modelo gemma-4-e4b-it
```

### Subir no servidor (uma vez)

```bash
git clone <repo> && cd mana-diario
cp .env.example .env     # preencher: provedor/URL da LLM definitiva, URL_PUBLICA, MODO_TESTE=false
# levar os calendários já revisados para o volume (opcional; sem isso o agendador gera novos)
podman volume create mana-dados   # (o compose cria sozinho se faltar)
podman run --rm -v mana-dados:/dados:z -v ./data/calendarios:/seed:ro,z \
  docker.io/library/python:3.12-slim sh -c 'mkdir -p /dados/calendarios && cp /seed/*.yaml /dados/calendarios/'
MANA_TAG=2026.11.01 podman compose -f compose.yaml -f compose.prod.yaml up -d --build
```

Para o site e o agendador **subirem sozinhos no boot** (Podman rootless não faz isso por padrão):

```bash
loginctl enable-linger "$USER"
systemctl --user enable --now podman-restart.service   # reinicia os containers com restart: unless-stopped
```

Aponte o proxy reverso (com HTTPS) para `127.0.0.1:${PORTA_HOST}` (padrão 8000).
O `compose.prod.yaml` ainda **não** liga os serviços à LLM: defina `LLM_BASE_URL` para o provedor
definitivo (ou acrescente a rede do llm-server, como em `compose.local.yaml`).

Migrar estudos já revisados da máquina local para o servidor (antes de subir):

```bash
podman volume export mana-diario_mana-dados -o dados.tar     # local (confira o nome com `podman volume ls`)
podman volume import mana-diario_mana-dados dados.tar        # servidor
```

Restaurar um backup: copie `/dados/backups/mana-AAAA-MM-DD.sqlite` para `/dados/mana.sqlite` com os
containers parados.

## Créditos

Textos bíblicos: Bíblia Livre (BLIVRE), © Diego Santos, Mario Sérgio e Marco Teles, licença
Creative Commons Atribuição 4.0 ([`data/biblia/FONTE.md`](data/biblia/FONTE.md)).
Fontes Nunito e Crimson Pro: SIL OFL 1.1 ([`static/fonts/LICENCAS.md`](src/mana/web/static/fonts/LICENCAS.md)).
