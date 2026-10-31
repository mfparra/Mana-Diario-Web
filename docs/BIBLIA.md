# Bíblia local — Bíblia Livre (linhagem Almeida)

## 1. Qual edição usar

As edições Almeida usadas nas igrejas hoje (ARC e ARA da SBB, NAA, ACF da SBTB, Almeida
Século 21) **têm direitos autorais**. Não existe uma Almeida moderna e popular que seja
livre. As opções realmente livres são:

| Edição | Situação | Prós | Contras |
|---|---|---|---|
| **Bíblia Livre (BLIVRE)** — escolhida | CC BY 4.0; © Diego Santos, Mario Sérgio e Marco Teles | Linhagem Almeida (revisão da edição de 1819), ortografia atual, 66 livros, usada em projetos livres (eBible, Sword) | Exige crédito; é "trabalho em andamento" (indicar a data da versão) |
| Almeida 1911 (Revista e Corrigida, reimpressão da edição de 1900) | Domínio público; módulo Sword `PorAlmeida1911` | Texto ancestral da ARC atual, soa familiar | Ortografia antiga ("Portuguez"); modernizar seria trabalho editorial |

**Use a Bíblia Livre.** Fonte: eBible.org, id `porbr2018`, pacote USFX
(`https://ebible.org/Scriptures/porbr2018_usfx.zip`; se mudar, ache em
`https://ebible.org/details.php?id=porbr2018`).

**Crédito obrigatório** (rodapé das páginas da Bíblia e do estudo, e no popover em forma
curta "BLIVRE"):

> Textos bíblicos: Bíblia Livre (BLIVRE), © Diego Santos, Mario Sérgio e Marco Teles,
> versão de <data da versão>. Licença Creative Commons Atribuição 4.0.

Se algum dia o texto for alterado (correções, ortografia), a licença exige dizer que houve
alteração e que os autores não necessariamente a endossam. Por padrão, **não altere o texto**.

**Proibido**, mesmo aparecendo como "domínio público" em repositórios:
- `por-almeida.usfx.xml` do `seven1m/open-bibles` — o texto é a "Almeida Atualizada", cópia
  da Almeida Revisada da Imprensa Bíblica/JUERP (1967), que tem direitos; CrossWire e
  Wikisource já a retiraram;
- "Almeida Recebida";
- os JSON `aa`, `acf`, `nvi` do `thiagobodruk/biblia` e derivados.

Registre em `data/biblia/FONTE.md`: URL, data do download, SHA-256 do arquivo bruto, data
da versão da BLIVRE, licença e o texto de crédito exibido no site.

## 2. Pipeline

```
uv run mana biblia baixar    → data/biblia/raw/<arquivo>   (fora do git)
uv run mana biblia importar  → data/biblia/biblia.sqlite   (pode ir para o git; ~5 MB)
```

O importador:

- lê o USFX com `xml.etree` (sem dependência extra);
- mapeia o código do livro (GEN, EXO, …, REV) para `data/livros.json`;
- normaliza espaços, remove marcações de nota de rodapé e de Strong, mantém itálicos de
  palavras acrescentadas como `<i>` se existirem (opcional);
- grava e roda as verificações de integridade (abaixo). Falhou → aborta sem substituir o
  banco anterior.

## 3. Esquema SQLite

```sql
CREATE TABLE livros (
  id INTEGER PRIMARY KEY,          -- 1..66, ordem canônica
  codigo TEXT NOT NULL UNIQUE,     -- GEN, EXO, ... (USFM)
  nome TEXT NOT NULL,              -- "Gênesis"
  slug TEXT NOT NULL UNIQUE,       -- "genesis"
  abrev TEXT NOT NULL,             -- "Gn"
  testamento TEXT NOT NULL CHECK (testamento IN ('AT','NT')),
  capitulos INTEGER NOT NULL
);
CREATE TABLE versiculos (
  livro_id INTEGER NOT NULL REFERENCES livros(id),
  capitulo INTEGER NOT NULL,
  versiculo INTEGER NOT NULL,
  texto TEXT NOT NULL,
  PRIMARY KEY (livro_id, capitulo, versiculo)
);
CREATE VIRTUAL TABLE versiculos_fts USING fts5(
  texto, content='versiculos', tokenize='unicode61 remove_diacritics 2'
);
CREATE TABLE metadados (chave TEXT PRIMARY KEY, valor TEXT);  -- edicao, versao, licenca, credito, sha256
```

## 4. Verificações de integridade (testes)

- 66 livros; 929 capítulos no AT, 260 no NT, 1.189 no total.
- Nº de capítulos de cada livro igual ao de `data/livros.json`.
- Total de versículos por volta de 31.100 (registre o número exato da edição).
- Nenhum versículo vazio; nenhum capítulo sem o versículo 1.
- Amostras conhecidas existem: Gn 1.1, Sl 23.1, Jo 3.16, Rm 8.28, Ap 22.21.

## 5. Referências (parser — `biblia/referencias.py`)

Entrada aceita (case-insensitive, com ou sem acento):

| Exemplo | Significado |
|---|---|
| `Romanos 5.3,4` | Rm 5:3 e 5:4 |
| `Tiago 1.2-4` | Tg 1:2 a 1:4 |
| `Rm 8:28` | dois-pontos também vale |
| `1 Coríntios 13` / `1Co 13` / `I Co 13` | capítulo inteiro |
| `Jo 3.16; 14.6` | lista; o livro se mantém após `;` |
| `Gn 1.1-2.3` | intervalo entre capítulos |
| `Sl 23` / `Salmo 23` / `Salmos 23` | singular e plural |
| `Obadias 4` / `Judas 3` | livros de 1 capítulo: o número é versículo |

Saída: lista de `Trecho(livro_id, cap_ini, vers_ini, cap_fim, vers_fim)` + forma canônica
para `data-ref`/API, com o código USFM do livro em minúsculas, sempre ASCII
(`rom.5.3-4`, `gen.1.1-2.3`, `1co.13.4-7`) + forma de exibição (`Romanos 5.3,4`).

**Jó × João:** sem acento as duas formas viram "jo". Regra: `Jó` (com acento) e `Job` são
Jó; `Jo` sem acento é sempre João. Por isso a comparação de nomes **não** pode remover o
acento desse par (use remoção de acentos para todo o resto).

`data/livros.json` tem nome, slug, abreviação padrão e variantes aceitas de cada livro;
amplie as variantes se aparecerem novas formas na saída da LLM.

Para encontrar referências dentro de texto livre, monte uma regex a partir de todas as
variantes (mais longas primeiro), exigindo fronteira de palavra e um número logo depois.
Várias abreviações são palavras comuns em português (`Os`, `Is`, `At`, `Am`, `Na`, `Ag`,
`Ml`…), então em texto livre:
- **abreviação** só é referência se vier com capítulo **e** versículo (`Os 6.6`, `At 2:38`)
  e começar com maiúscula;
- **nome completo** pode vir só com capítulo (`Isaías 40`, `Salmo 23`);
- nada vira link sem número ("Atos" sozinho, "os 12 discípulos", "na 1ª carta").
O parser de referência isolada (campo `complementares`, `/api/passagem`) pode ser mais
tolerante, porque ali o texto já é uma referência.
