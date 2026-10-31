# Design — Maná Diário

A referência visual é uma página de devocional impresso (formato de livro, uma página por
dia). Reproduza a **estrutura e o clima** da página — não copie textos, ilustrações nem a
marca da referência. O logo de xícara de café da referência é substituído pelo **maná em
uma tigela** (`assets/logo-mana.svg`).

> Se o Marcos colocar a imagem de referência em `docs/referencia/`, use-a só para conferir
> proporções. Ela não vai para o site nem para o repositório público.

## 1. Clima

Papel creme, tinta marrom-escura, títulos em terracota. Sensação de livro devocional:
calmo, legível, com bastante respiro. Nada de cards com sombra pesada, gradientes
chamativos ou ícones coloridos.

## 2. Layout desktop (≥ 900 px) — a "página" do dia

```
┌──────────────────────────────────────────────────────────────┐
│ 31 | OUT                              TÍTULO DO ESTUDO        │  ← linha 1
│  ╭────────╮ ┌──────────────────────────────────────────────┐ │
│  │  LOGO  │ │        Texto do versículo do dia, em itálico,│ │  ← faixa do versículo
│  │ (tigela)│ │        alinhado à direita, serifado.         │ │    (fundo bege mais escuro)
│  ╰────────╯ │                              ROMANOS 5.3,4   │ │
│ ┌────────┐  └──────────────────────────────────────────────┘ │
│ │  Frase │  C erta vez, ... (capitular de 3 linhas)          │
│ │  do dia│  parágrafo justificado, serifado ...              │
│ │ grande │                                                   │
│ │ em     │  segundo parágrafo ...                            │
│ │terracota│                                                  │
│ │────────│  terceiro parágrafo, com referências (Romanos      │
│ │ESTUDO  │  8.28) sublinhadas em pontilhado → hover/clique   │
│ │305/365 │                                                   │
│ │LEITURA │                                                   │
│ │COMPLEM.✝│                                                  │
│ │Tg 1.2-4│                                                   │
│ ╰────────╯                                                   │
│ PALAVRAS-CHAVE                                               │
│ [fé] [perseverança] [esperança]                              │
│ ─────────────────────────── ◯ ───────────────────────────── │  ← rodapé com selo
└──────────────────────────────────────────────────────────────┘
```

Detalhes, de cima para baixo:

- **Data** no canto superior esquerdo: `31 | OUT`, caixa alta, sans bold pequeno,
  espaçamento entre letras largo (`letter-spacing: .3em`), cor `--tinta`. Em datas
  especiais, logo ao lado: `· PÁSCOA` / `· CORPUS CHRISTI` em terracota, mesmo estilo.
- **Título** no canto superior direito: sans geométrica arredondada, *extra-bold*, caixa
  alta, terracota, ~2.2rem. Máximo 6 palavras (a LLM respeita isso).
- **Faixa do versículo**: bloco com fundo `--papel-escuro` ocupando a largura da coluna de
  texto e entrando por trás do logo. Texto em serifada itálica, alinhado à direita,
  ~1.15rem, entrelinha 1.45. Abaixo, a referência em versalete/caixa alta, serifada,
  `letter-spacing: .08em`, alinhada à direita. A referência também é link com popover.
- **Logo**: círculo de ~180 px sobreposto à borda esquerda da faixa (como a xícara da
  referência, vista de cima). Usar o SVG; com leve sombra difusa só no círculo.
- **Coluna lateral** (~260 px): começa logo abaixo do logo e tem formato de "cápsula" —
  contorno fino (`1px solid --linha`), cantos superiores retos, base totalmente
  arredondada (`border-radius: 0 0 130px 130px`). Conteúdo:
  - **Frase do dia**: sans arredondada bold, ~1.6rem, terracota, alinhada à direita,
    entrelinha 1.25. Máx. ~18 palavras.
  - divisor horizontal fino;
  - `ESTUDO` + `305/365` (número do dia no ano), sans bold pequena, marrom;
  - `LEITURA COMPLEMENTAR` + ícone de cruz em terracota + a referência (link com popover).
- **Corpo do estudo**: serifada, ~1.06rem, entrelinha 1.55, justificado com
  `hyphens: auto` e `lang="pt-BR"`. Primeiro parágrafo com **capitular** de 3 linhas
  (`::first-letter`, serifada, ~4.2em, cor `--tinta`). Parágrafos separados por espaço,
  sem recuo.
- **Palavras-chave**: abaixo da coluna lateral (no lugar do bloco "Anotações" da
  referência). Rótulo `PALAVRAS-CHAVE` em sans bold pequena; palavras como "pílulas" com
  contorno fino e texto em versalete — nada de fundo colorido forte.
- **Rodapé**: linha fina horizontal de ponta a ponta com um selo circular pequeno no
  centro (versão mini da tigela). Abaixo, navegação discreta: `‹ dia anterior` ·
  `arquivo` · `Bíblia` · `dia seguinte ›` (este só se não for futuro).
- Largura máxima da "página": 960 px, centralizada, com margem de papel.

## 3. Layout mobile (< 900 px)

Ordem: data · logo (120 px) centralizado · título · faixa do versículo (largura total,
alinhado à direita) · frase do dia (em destaque, sem a cápsula, com fio fino acima e abaixo)
· corpo do estudo · leitura complementar · palavras-chave · rodapé. Gutter lateral de 16 px,
sem rolagem horizontal. Popover vira uma "folha" fixa na base da tela.

## 4. Tokens de cor

```css
:root {
  --papel:        #F7F2E9;  /* fundo da página */
  --papel-escuro: #EDE3D4;  /* faixa do versículo */
  --tinta:        #2A221D;  /* texto */
  --tinta-suave:  #5B4D43;  /* metadados */
  --terracota:    #965220;  /* títulos, frase do dia, cruz */
  --terracota-2:  #A15C29;  /* hover dos links */
  --linha:        #CDBFAE;  /* contornos e divisores */
  --mana:         #FBF7EE;  /* flocos do maná no logo */
  --madeira:      #8A5A33;  /* tigela */
}
@media (prefers-color-scheme: dark) {
  :root {
    --papel: #1E1915; --papel-escuro: #2A231D; --tinta: #EDE4D8;
    --tinta-suave: #B9AC9E; --terracota: #E0995F; --terracota-2: #F0B27D;
    --linha: #4A3F36;
  }
}
```

Contraste mínimo AA para texto do corpo (≥ 4.5:1) nos dois temas — teste.

> Verificado na Fase 3: os valores originais `#9C5524`/`#B8713A` davam 4,42:1 (terracota sobre
> `--papel-escuro`) e 3,45:1 (hover); foram escurecidos para os valores acima (≥ 4,6:1). No tema
> escuro, texto sobre fundo terracota usa `--papel` (o branco dava 2,36:1).

## 5. Tipografia (servir localmente em `static/fonts/`, licença OFL)

- **Títulos, frase do dia, rótulos**: Nunito (700/800/900) — sans arredondada como a da
  referência. Alternativa: Baloo 2.
- **Corpo, versículos, capitular**: Crimson Pro (400, 400 itálico, 600). Alternativa: Lora.
- Use `font-display: swap` e subsetting latin + latin-ext.

## 6. Referências bíblicas (links com popover)

- No texto: cor herdada, sublinhado pontilhado em `--terracota` (`text-decoration-style:
  dotted; text-underline-offset: 3px`); hover → `--terracota-2`.
- **Popover**: caixa `--papel` com contorno `--linha`, raio 10 px, sombra suave,
  largura máx. 360 px, seta apontando para o link. Conteúdo: referência em caixa alta
  (sans bold pequena), texto do(s) versículo(s) em serifada com número sobrescrito,
  e no rodapé `Abrir na Bíblia →`. Para passagens longas, mostrar até 6 versículos e
  "… continuar lendo".
- Acessível: `role="tooltip"`, abre no `focus`, fecha com `Esc`.

## 7. Interface da Bíblia

Mesma paleta e tipografia, sem a coluna lateral.

- `/biblia`: duas seções (Antigo e Novo Testamento), livros em grade de pílulas.
- `/biblia/{livro}/{cap}`: título `ROMANOS 8` em terracota; seletor de livro/capítulo;
  texto corrido em parágrafo com números de versículo sobrescritos (`<sup id="v28">`),
  versículo alvo (`:target` ou `?destacar=3-5`) com fundo `--papel-escuro` e rolagem
  suave até ele; botões `‹ capítulo anterior` / `próximo capítulo ›`.
- Crédito da edição e licença no rodapé de todas as páginas da Bíblia.

## 8. Logo

`assets/logo-mana.svg`: círculo creme, tigela de madeira vista em ¾ com o maná (flocos
pequenos, brancos, arredondados — "como semente de coentro", Êx 16.31) amontoado, e o
nome **Maná Diário** em arco por cima. O texto já está convertido em curvas (Nunito Black,
OFL), então o SVG não depende de fonte instalada. Falta gerar `favicon.svg` só com a
tigela (sem o texto, que fica ilegível em 32 px).
