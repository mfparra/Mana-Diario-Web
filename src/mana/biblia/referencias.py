"""Parser e formatador de referências bíblicas em pt-BR (docs/BIBLIA.md §5).

Trabalha só com o catálogo de livros (`data/livros.json`); a existência dos versículos
é conferida à parte, no repositório.
"""

import json
import logging
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from html import escape
from pathlib import Path

log = logging.getLogger(__name__)

LIVROS_JSON = Path(__file__).resolve().parents[3] / "data" / "livros.json"

# Formas por extenso aceitas além do `nome` do livro (o resto das variantes é abreviação).
_ALIAS_EXTRA = {"Cantares de Salomão": "SNG"}
_COMPLETOS_EXTRA = {"salmo", "atosdosapostolos", "canticodoscanticos", "cantaresdesalomao"}


@dataclass(frozen=True)
class Livro:
    id: int
    codigo: str
    nome: str
    slug: str
    abrev: str
    testamento: str
    capitulos: int
    variantes: tuple[str, ...]

    @property
    def usfm(self) -> str:
        """Código USFM em minúsculas, ASCII (`rom`, `1co`)."""
        return self.codigo.lower()


@dataclass(frozen=True)
class Trecho:
    """Intervalo contínuo. `vers_ini`/`vers_fim` são None quando é capítulo(s) inteiro(s)."""

    livro_id: int
    cap_ini: int
    vers_ini: int | None
    cap_fim: int
    vers_fim: int | None


@dataclass(frozen=True)
class Referencia:
    trechos: tuple[Trecho, ...]


@dataclass(frozen=True)
class Encontrada:
    """Referência achada em texto livre, com a posição no texto."""

    inicio: int
    fim: int
    referencia: Referencia


@cache
def livros() -> tuple[Livro, ...]:
    dados = json.loads(LIVROS_JSON.read_text(encoding="utf-8"))["livros"]
    return tuple(Livro(**{**d, "variantes": tuple(d["variantes"])}) for d in dados)


@cache
def _por_id() -> dict[int, Livro]:
    return {livro.id: livro for livro in livros()}


def livro_por_id(livro_id: int) -> Livro:
    return _por_id()[livro_id]


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def chave(nome: str) -> str:
    """Forma de comparação: minúsculas, sem acento, sem espaços/pontos, romano → arábico.

    `Jó` (com acento) vira `job`; `Jo` sem acento continua `jo` (João).
    """
    s = nome.lower().strip()
    s = re.sub(r"\bjó\b", "job", s)
    s = _sem_acento(s)
    s = re.sub(r"^(iii|ii|i)\s+(?=[a-z])", lambda m: str(len(m.group(1))), s)
    return re.sub(r"[\s.]", "", s)


@cache
def _tabela() -> tuple[dict[str, Livro], frozenset[str]]:
    """(chave → livro, conjunto das chaves que são nome por extenso)."""
    tabela: dict[str, Livro] = {}
    completos = set(_COMPLETOS_EXTRA)
    por_codigo = {livro.codigo: livro for livro in livros()}

    def adicionar(texto: str, livro: Livro) -> None:
        k = chave(texto)
        if tabela.setdefault(k, livro) is not livro:
            raise ValueError(f"Nome ambíguo {texto!r}: {tabela[k].nome} × {livro.nome}")

    for livro in livros():
        for forma in (livro.nome, livro.abrev, *livro.variantes):
            adicionar(forma, livro)
        completos.add(chave(livro.nome))
    for forma, codigo in _ALIAS_EXTRA.items():
        adicionar(forma, por_codigo[codigo])
    return tabela, frozenset(completos)


def buscar_livro(nome: str) -> Livro | None:
    return _tabela()[0].get(chave(nome))


# --------------------------------------------------------------------------- análise

_ITEM = re.compile(r"^(\d{1,3})(?:[.:](\d{1,3}))?(?:\s*[-–]\s*(\d{1,3})(?:[.:](\d{1,3}))?)?$")
_PARTE = re.compile(
    r"^\s*(?P<nome>(?:[123]|i{1,3})?\s*\.?\s*[^\W\d_][^\d]*?)\s*\.?\s*(?P<spec>\d.*)$",
    re.IGNORECASE,
)


def _montar(livro: Livro, items: list[str]) -> list[Trecho] | None:
    """Converte os itens separados por vírgula de uma parte (ex.: ['3.16', '18-20'])."""
    trechos: list[Trecho] = []
    cap_atual: int | None = None
    modo_verso = False
    for item in items:
        m = _ITEM.match(item.strip())
        if not m:
            return None
        a, b, c, d = (int(x) if x is not None else None for x in m.groups())
        if b is not None or (livro.capitulos == 1 and b is None):
            if b is not None:
                cap, v1 = a, b
            else:  # livro de um capítulo: o número é versículo
                cap, v1 = 1, a
            if c is None:
                cap2, v2 = cap, v1
            elif d is None:
                cap2, v2 = cap, c
            else:
                cap2, v2 = c, d
            t = Trecho(livro.id, cap, v1, cap2, v2)
            cap_atual, modo_verso = cap2, True
        elif modo_verso and cap_atual is not None:
            t = Trecho(livro.id, cap_atual, a, cap_atual, c if c is not None else a)
        else:
            t = Trecho(livro.id, a, None, c if c is not None else a, None)
        trechos.append(t)
    return trechos


def _valido(t: Trecho, livro: Livro) -> bool:
    if not (1 <= t.cap_ini <= t.cap_fim <= livro.capitulos):
        return False
    if t.vers_ini is None:
        return t.vers_fim is None
    if t.vers_fim is None or t.vers_ini < 1 or t.vers_fim < 1:
        return False
    return (t.cap_ini, t.vers_ini) <= (t.cap_fim, t.vers_fim)


def _juntar_adjacentes(trechos: list[Trecho]) -> tuple[Trecho, ...]:
    saida: list[Trecho] = []
    for t in trechos:
        p = saida[-1] if saida else None
        if (
            p
            and p.livro_id == t.livro_id
            and p.vers_fim is not None
            and t.vers_ini is not None
            and p.cap_fim == t.cap_ini
            and t.vers_ini == p.vers_fim + 1
        ):
            saida[-1] = Trecho(p.livro_id, p.cap_ini, p.vers_ini, t.cap_fim, t.vers_fim)
        else:
            saida.append(t)
    return tuple(saida)


def parse_referencia(texto: str) -> Referencia | None:
    """Referência isolada (`Rm 8:28`, `Jo 3.16; 14.6`, `Gn 1.1-2.3`). None se inválida."""
    trechos: list[Trecho] = []
    livro: Livro | None = None
    for parte in texto.split(";"):
        parte = parte.strip()
        if not parte:
            return None
        m = _PARTE.match(parte)
        if m:
            livro = buscar_livro(m["nome"])
            spec = m["spec"]
            if livro is None:
                return None
        elif livro is not None and parte[0].isdigit():
            spec = parte
        else:
            return None
        novos = (
            _montar(livro, spec.replace(" ", "").split(","))
            if "," in spec
            else _montar(livro, [spec])
        )
        if not novos or not all(_valido(t, livro) for t in novos):
            return None
        trechos.extend(novos)
    return Referencia(_juntar_adjacentes(trechos)) if trechos else None


# ----------------------------------------------------------------- forma canônica

_CANON = re.compile(r"^([0-9a-z]{3})\.(\d+)(?:\.(\d+))?(?:-(\d+)(?:\.(\d+))?)?$")


def canonico(ref: Referencia) -> str:
    """`rom.5.3-4`, `gen.1.1-2.3`, `1co.13`, `gen.1-3`; vários trechos separados por `;`."""
    partes = []
    for t in ref.trechos:
        cod = livro_por_id(t.livro_id).usfm
        if t.vers_ini is None:
            s = f"{cod}.{t.cap_ini}" + (f"-{t.cap_fim}" if t.cap_fim != t.cap_ini else "")
        elif (t.cap_fim, t.vers_fim) == (t.cap_ini, t.vers_ini):
            s = f"{cod}.{t.cap_ini}.{t.vers_ini}"
        elif t.cap_fim == t.cap_ini:
            s = f"{cod}.{t.cap_ini}.{t.vers_ini}-{t.vers_fim}"
        else:
            s = f"{cod}.{t.cap_ini}.{t.vers_ini}-{t.cap_fim}.{t.vers_fim}"
        partes.append(s)
    return ";".join(partes)


def parse_canonico(texto: str) -> Referencia | None:
    por_usfm = {livro.usfm: livro for livro in livros()}
    trechos: list[Trecho] = []
    for parte in texto.strip().lower().split(";"):
        m = _CANON.match(parte)
        if not m or m[1] not in por_usfm:
            return None
        livro = por_usfm[m[1]]
        cap, v1, x, y = int(m[2]), m[3], m[4], m[5]
        if v1 is None:
            t = Trecho(livro.id, cap, None, int(x) if x else cap, None)
            if y is not None:
                return None
        else:
            v1 = int(v1)
            if x is None:
                t = Trecho(livro.id, cap, v1, cap, v1)
            elif y is None:
                t = Trecho(livro.id, cap, v1, cap, int(x))
            else:
                t = Trecho(livro.id, cap, v1, int(x), int(y))
        if not _valido(t, livro):
            return None
        trechos.append(t)
    return Referencia(tuple(trechos)) if trechos else None


def _corpo(t: Trecho, livro: Livro, mesmo_cap: bool) -> str:
    """Parte numérica de um trecho (sem o nome do livro)."""
    if t.vers_ini is None:
        return str(t.cap_ini) + (f"-{t.cap_fim}" if t.cap_fim != t.cap_ini else "")
    if t.cap_fim != t.cap_ini:
        return f"{t.cap_ini}.{t.vers_ini}-{t.cap_fim}.{t.vers_fim}"
    if t.vers_fim == t.vers_ini:
        versos = str(t.vers_ini)
    elif t.vers_fim == t.vers_ini + 1:
        versos = f"{t.vers_ini},{t.vers_fim}"
    else:
        versos = f"{t.vers_ini}-{t.vers_fim}"
    return versos if (livro.capitulos == 1 or mesmo_cap) else f"{t.cap_ini}.{versos}"


def formatar(ref: Referencia) -> str:
    """Forma de exibição: `Romanos 5.3,4`, `Tiago 1.2-4`, `Gênesis 1.1-2.3`, `João 3.16; 14.6`."""
    saida = ""
    anterior: Trecho | None = None
    for t in ref.trechos:
        livro = livro_por_id(t.livro_id)
        mesmo_livro = anterior is not None and anterior.livro_id == t.livro_id
        mesmo_cap = (
            mesmo_livro
            and t.vers_ini is not None
            and anterior.vers_fim is not None
            and anterior.cap_fim == t.cap_ini == t.cap_fim
        )
        if not mesmo_livro:
            saida += ("; " if saida else "") + f"{livro.nome} "
        else:
            saida += "," if mesmo_cap else "; "
        saida += _corpo(t, livro, mesmo_cap)
        anterior = t
    return saida


def url_referencia(ref: Referencia) -> str:
    """`/biblia/romanos/8#v28` (primeiro trecho)."""
    t = ref.trechos[0]
    url = f"/biblia/{livro_por_id(t.livro_id).slug}/{t.cap_ini}"
    return url + (f"#v{t.vers_ini}" if t.vers_ini is not None else "")


# ------------------------------------------------------------------ texto livre

_CANDIDATO = re.compile(
    r"(?<![\w.])(?P<ord>(?:[123]|III|II|I)\s?)?(?P<palavra>[A-ZÀ-Ý][\wÀ-ÿ]*)"
    r"(?P<cauda>\s+(?:dos|de|das|do)\s+[A-ZÀ-Ý][\wÀ-ÿ]*)?\.?\s?(?=\d)"
)
_PRIMEIRO = re.compile(r"\d{1,3}(?:[.:]\d{1,3})?(?:\s?[-–]\s?\d{1,3}(?:[.:]\d{1,3})?)?")
_VIRGULA = re.compile(r",\d{1,3}(?:[.:]\d{1,3})?(?:-\d{1,3}(?:[.:]\d{1,3})?)?")
_PONTO_VIRGULA = re.compile(r";\s*\d{1,3}[.:]\d{1,3}(?:\s?[-–]\s?\d{1,3}(?:[.:]\d{1,3})?)?")


def encontrar_referencias(texto: str) -> list[Encontrada]:
    """Acha referências em texto livre, com as regras conservadoras do §5 do BIBLIA.md."""
    _, completos = _tabela()
    achadas: list[Encontrada] = []
    posicao = 0
    while True:
        c = _CANDIDATO.search(texto, posicao)
        if not c:
            return achadas
        posicao = c.end()
        nome = (c["ord"] or "") + c["palavra"] + (c["cauda"] or "")
        livro = buscar_livro(nome)
        primeiro = _PRIMEIRO.match(texto, c.end())
        if livro is None or primeiro is None:
            continue
        fim = primeiro.end()
        if fim < len(texto) and texto[fim].isdigit():
            continue
        if chave(nome) not in completos and not re.search(r"[.:]", primeiro.group()):
            continue  # abreviação só vale com capítulo e versículo
        while True:
            seguinte = _VIRGULA.match(texto, fim) or _PONTO_VIRGULA.match(texto, fim)
            if not seguinte:
                break
            fim = seguinte.end()
        ref = parse_referencia(texto[c.start() : fim])
        if ref is None:
            continue
        achadas.append(Encontrada(c.start(), fim, ref))
        posicao = fim


def linkar_referencias(texto: str, existe: Callable[[Referencia], bool] | None = None) -> str:
    """Escapa o texto e transforma cada referência válida em link `<a class="ref">`.

    `existe` (opcional) confere a referência contra a Bíblia local; as que não existem
    ficam como texto puro e são registradas em log.
    """
    saida: list[str] = []
    pos = 0
    for e in encontrar_referencias(texto):
        if existe is not None and not existe(e.referencia):
            log.warning("Referência inexistente na Bíblia: %r", texto[e.inicio : e.fim])
            continue
        saida.append(escape(texto[pos : e.inicio]))
        saida.append(
            f'<a class="ref" href="{url_referencia(e.referencia)}" '
            f'data-ref="{canonico(e.referencia)}">{escape(texto[e.inicio : e.fim])}</a>'
        )
        pos = e.fim
    saida.append(escape(texto[pos:]))
    return "".join(saida)
