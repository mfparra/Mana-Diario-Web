"""Data de "hoje", sempre no fuso do site (AGENTS.md §2, regra 6)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from mana.config import obter_configuracao


def hoje() -> date:
    return datetime.now(ZoneInfo(obter_configuracao().fuso_horario)).date()


DIAS_SEMANA = (
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado",
    "domingo",
)  # fmt: skip
MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
    "outubro", "novembro", "dezembro",
)  # fmt: skip


def data_extenso(d: date) -> str:
    """`sábado, 31 de outubro de 2026`."""
    return f"{DIAS_SEMANA[d.weekday()]}, {d.day} de {MESES[d.month - 1]} de {d.year}"
