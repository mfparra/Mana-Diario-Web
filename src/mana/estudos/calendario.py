"""Calendário anual do versículo do dia, montado a partir do acervo (AGENTS.md §6.1).

Determinístico: a semente é o ano. Regras:
- nenhuma referência repete em 1.095 dias (a janela diminui, com aviso, se o acervo não bastar);
- as datas especiais ganham primeiro uma referência marcada com a ocasião;
- o mesmo livro no máximo 2 dias seguidos; o mesmo tema nunca em dias seguidos;
- ~45% AT / 55% NT; Salmos + Provérbios ≤ 25% do período.
Entradas do acervo com ocasião são reservadas a ela (nunca caem em dia comum).
"""

import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import yaml

from mana.biblia.referencias import (
    canonico,
    formatar,
    livro_por_id,
    parse_canonico,
    parse_referencia,
)
from mana.biblia.repositorio import RepositorioBiblia
from mana.estudos.acervo import Acervo, Entrada
from mana.estudos.datas_especiais import OCASIOES, Ocasiao, ocasioes_do_ano
from mana.estudos.repositorio import LinhaCalendario, RepositorioEstudos

JANELA_DIAS = 1095
JANELAS_MENORES = (730, 365, 180, 90, 30)
ALVO_AT = 0.45
LIMITE_SALMOS_PROVERBIOS = 0.25
MAX_LIVRO_SEGUIDO = 2
SALMOS, PROVERBIOS = 19, 20
DISTANCIA_MAXIMA = 1500  # teto do "tempo desde o último uso" usado como peso

SEMANA = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")


class ErroCalendario(Exception):
    pass


@dataclass(frozen=True)
class Info:
    chave: str
    livro_id: int
    temas: frozenset[str]
    testamento: str


@dataclass
class ResultadoGeracao:
    linhas: list[LinhaCalendario] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def _info_de(chave: str, por_chave: dict[str, Entrada]) -> Info:
    entrada = por_chave.get(chave)
    if entrada:
        return Info(chave, entrada.livro_id, frozenset(entrada.temas), entrada.testamento)
    ref = parse_canonico(chave)
    livro_id = ref.trechos[0].livro_id if ref else 0
    testamento = livro_por_id(livro_id).testamento if livro_id else "NT"
    return Info(chave, livro_id, frozenset(), testamento)


class _Planejador:
    def __init__(
        self,
        acervo: Acervo,
        ano: int,
        historico: list[LinhaCalendario],
        total_dias: int,
        janela: int = JANELA_DIAS,
    ) -> None:
        self.rng = random.Random(ano)
        self.janela_base = janela
        self.entradas = sorted(acervo.entradas, key=lambda e: e.chave)
        self.por_chave = {e.chave: e for e in self.entradas}
        self.comuns = {"AT": [], "NT": []}
        for e in self.entradas:
            if not e.ocasioes:
                self.comuns[e.testamento].append(e)
        self.atrib: dict[date, Info] = {}
        self.usos: dict[str, list[date]] = defaultdict(list)
        self.ocasiao_do_dia: dict[date, str] = {}
        self.avisos: list[str] = []
        self._avisados: set[str] = set()
        self.limite_sp = int(LIMITE_SALMOS_PROVERBIOS * total_dias)
        self.n = self.n_at = self.n_sp = 0
        for linha in historico:
            self._registrar(linha.data, _info_de(linha.ref, self.por_chave))

    def _registrar(self, d: date, info: Info) -> None:
        self.atrib[d] = info
        self.usos[info.chave].append(d)

    def _atribuir(self, d: date, entrada: Entrada, ocasiao: str | None) -> None:
        self._registrar(d, _info_de(entrada.chave, self.por_chave))
        if ocasiao:
            self.ocasiao_do_dia[d] = ocasiao
        self.n += 1
        self.n_at += entrada.testamento == "AT"
        self.n_sp += entrada.livro_id in (SALMOS, PROVERBIOS)

    def _avisar(self, texto: str) -> None:
        if texto not in self._avisados:
            self._avisados.add(texto)
            self.avisos.append(texto)

    # --- regras

    def _distancia(self, chave: str, d: date) -> int:
        usos = self.usos.get(chave, ())
        return min([abs((d - u).days) for u in usos] + [DISTANCIA_MAXIMA])

    def _vizinhos_ok(self, d: date, e: Entrada) -> bool:
        temas = set(e.temas)
        for delta in (-1, 1):
            v = self.atrib.get(d + timedelta(days=delta))
            if v and v.temas & temas:
                return False
        corridas = []
        for sinal in (-1, 1):
            n = 0
            while n < MAX_LIVRO_SEGUIDO:
                v = self.atrib.get(d + timedelta(days=sinal * (n + 1)))
                if not v or v.livro_id != e.livro_id:
                    break
                n += 1
            corridas.append(n)
        return sum(corridas) + 1 <= MAX_LIVRO_SEGUIDO

    def _sortear(
        self, d: date, pool: list[Entrada], janela: int, vizinhos: bool, limite_sp: bool
    ) -> Entrada | None:
        candidatas = [
            e
            for e in pool
            if self._distancia(e.chave, d) >= janela
            and (not vizinhos or self._vizinhos_ok(d, e))
            and not (
                limite_sp and e.livro_id in (SALMOS, PROVERBIOS) and self.n_sp >= self.limite_sp
            )
        ]
        if not candidatas:
            return None
        pesos = [self._distancia(e.chave, d) for e in candidatas]
        return self.rng.choices(candidatas, weights=pesos)[0]

    def _janelas(self) -> list[int]:
        return [self.janela_base, *(j for j in JANELAS_MENORES if j < self.janela_base)]

    # --- passos

    def datas_especiais(self, especiais: dict[date, Ocasiao]) -> None:
        for d, oc in especiais.items():
            pool = [e for e in self.entradas if oc.codigo in e.ocasioes]
            if not pool:
                raise ErroCalendario(f"Nenhuma entrada do acervo para a ocasião {oc.codigo!r}")
            escolhida = None
            for janela in self._janelas():
                escolhida = self._sortear(d, pool, janela, vizinhos=True, limite_sp=False)
                if escolhida is None:
                    escolhida = self._sortear(d, pool, janela, vizinhos=False, limite_sp=False)
                    if escolhida:
                        self._avisar(f"{d}: {oc.nome} sem como evitar tema/livro vizinho repetido")
                if escolhida:
                    if janela < self.janela_base:
                        self._avisar(f"janela de não repetição reduzida para {janela} dias")
                    break
            if escolhida is None:
                raise ErroCalendario(f"Sem referência disponível para {oc.nome} em {d}")
            self._atribuir(d, escolhida, oc.codigo)

    def dia_comum(self, d: date) -> None:
        alvo = self.n_at / (self.n + 1) < ALVO_AT
        if abs(self.n_at / (self.n + 1) - ALVO_AT) < 0.05 and self.rng.random() < 0.15:
            alvo = not alvo
        ordem = ("AT", "NT") if alvo else ("NT", "AT")
        for janela in self._janelas():
            for testamento in ordem:
                e = self._sortear(d, self.comuns[testamento], janela, True, True)
                if e:
                    if janela < self.janela_base:
                        self._avisar(f"janela de não repetição reduzida para {janela} dias")
                    if testamento != ordem[0]:
                        self._avisar("proporção AT/NT desviada em alguns dias (faltou candidato)")
                    self._atribuir(d, e, None)
                    return
        raise ErroCalendario(f"Acervo insuficiente: nenhuma referência disponível em {d}")


def gerar(
    ano: int,
    acervo: Acervo,
    ativas: frozenset[str],
    historico: list[LinhaCalendario],
    inicio: date | None = None,
    janela: int = JANELA_DIAS,
) -> ResultadoGeracao:
    """Monta os dias de `inicio` (ou 1º de janeiro) a 31/12 que ainda não estão em `historico`."""
    inicio = max(inicio or date(ano, 1, 1), date(ano, 1, 1))
    fim = date(ano, 12, 31)
    existentes = {linha.data for linha in historico}
    dias = [
        inicio + timedelta(days=i)
        for i in range((fim - inicio).days + 1)
        if inicio + timedelta(days=i) not in existentes
    ]
    plano = _Planejador(acervo, ano, historico, total_dias=len(dias), janela=janela)
    especiais = {d: o for d, o in ocasioes_do_ano(ano, ativas).items() if d in set(dias)}
    plano.datas_especiais(especiais)
    for d in dias:
        if d not in especiais:
            plano.dia_comum(d)
    linhas = [LinhaCalendario(d, plano.atrib[d].chave, plano.ocasiao_do_dia.get(d)) for d in dias]
    return ResultadoGeracao(linhas, plano.avisos)


# ---------------------------------------------------------------------- verificação


def verificar(
    linhas: list[LinhaCalendario], acervo: Acervo, janela: int = JANELA_DIAS
) -> list[str]:
    """Confere as regras sobre um conjunto de linhas (usado nos testes e na importação)."""
    por_chave = {e.chave: e for e in acervo.entradas}
    infos = {x.data: _info_de(x.ref, por_chave) for x in linhas}
    problemas: list[str] = []
    ultimo: dict[str, date] = {}
    for x in sorted(linhas, key=lambda x: x.data):
        antes = ultimo.get(x.ref)
        if antes and (x.data - antes).days < janela:
            problemas.append(f"{x.data}: {x.ref} repete {antes} (< {janela} dias)")
        ultimo[x.ref] = x.data
    for d, info in sorted(infos.items()):
        seguinte = infos.get(d + timedelta(days=1))
        if seguinte and seguinte.temas & info.temas:
            problemas.append(f"{d}: tema repetido no dia seguinte ({info.chave})")
        d2 = infos.get(d + timedelta(days=2))
        if seguinte and d2 and info.livro_id == seguinte.livro_id == d2.livro_id:
            problemas.append(f"{d}: o mesmo livro 3 dias seguidos")
    return problemas


def estatisticas(linhas: list[LinhaCalendario]) -> dict[str, float]:
    total = len(linhas) or 1
    at = sum(
        livro_por_id(parse_canonico(x.ref).trechos[0].livro_id).testamento == "AT" for x in linhas
    )
    sp = sum(parse_canonico(x.ref).trechos[0].livro_id in (SALMOS, PROVERBIOS) for x in linhas)
    return {
        "dias": len(linhas),
        "pct_at": 100 * at / total,
        "pct_salmos_proverbios": 100 * sp / total,
    }


# ------------------------------------------------------------------- YAML de revisão


def exportar_yaml(ano: int, linhas: list[LinhaCalendario], caminho: Path) -> None:
    saida = [
        f"# Calendário de {ano} — edite `ref` (e `ocasiao`) e rode:",
        f"#   uv run mana calendario importar --ano {ano}",
        "# Dias já publicados (hoje ou antes) não mudam. Só a referência é editável: o texto",
        "# do versículo sempre vem da Bíblia local.",
        f"ano: {ano}",
        "dias:",
    ]
    for x in sorted(linhas, key=lambda x: x.data):
        ref = formatar(parse_canonico(x.ref))
        oc = f", ocasiao: {x.ocasiao}" if x.ocasiao else ""
        saida.append(f'  - {{data: "{x.data}", ref: "{ref}"{oc}}}  # {SEMANA[x.data.weekday()]}')
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("\n".join(saida) + "\n", encoding="utf-8")


@dataclass
class RelatorioImportacao:
    alterados: list[date] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


def importar_yaml(
    ano: int,
    caminho: Path,
    repo: RepositorioEstudos,
    biblia: RepositorioBiblia,
    acervo: Acervo,
    hoje: date,
) -> RelatorioImportacao:
    """Aplica as edições do YAML. Tudo ou nada: com qualquer erro, nada é gravado."""
    rel = RelatorioImportacao()
    bruto = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    if bruto.get("ano") != ano:
        rel.erros.append(f"o arquivo é do ano {bruto.get('ano')}, não de {ano}")
        return rel
    atuais = {x.data: x for x in repo.calendario(date(ano, 1, 1), date(ano, 12, 31))}
    novas: list[LinhaCalendario] = []
    for item in bruto.get("dias") or []:
        try:
            data = date.fromisoformat(str(item["data"]))
        except (KeyError, ValueError):
            rel.erros.append(f"data inválida: {item!r}")
            continue
        if data.year != ano:
            rel.erros.append(f"{data}: fora do ano {ano}")
            continue
        ref = parse_referencia(str(item.get("ref", "")))
        if ref is None or not biblia.existe(ref):
            rel.erros.append(f"{data}: referência inválida ou inexistente: {item.get('ref')!r}")
            continue
        ocasiao = item.get("ocasiao")
        if ocasiao is not None and ocasiao not in OCASIOES:
            rel.erros.append(f"{data}: ocasião desconhecida: {ocasiao!r}")
            continue
        nova = LinhaCalendario(data, canonico(ref), ocasiao, "editado")
        atual = atuais.get(data)
        if atual and (atual.ref, atual.ocasiao) == (nova.ref, nova.ocasiao):
            continue
        if atual and data <= hoje:
            rel.erros.append(f"{data}: já publicado, não pode mudar de versículo")
            continue
        novas.append(nova)
    if rel.erros:
        return rel
    final = {**atuais, **{x.data: x for x in novas}}
    conhecidas = {e.chave for e in acervo.entradas}
    rel.avisos += [
        f"{x.data}: {x.ref} não está no acervo" for x in novas if x.ref not in conhecidas
    ]
    rel.avisos += verificar(list(final.values()), acervo)
    repo.gravar(novas)
    rel.alterados = [x.data for x in novas]
    return rel
