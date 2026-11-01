"""Data de "hoje", sempre no fuso do site (AGENTS.md §2, regra 6)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from mana.config import obter_configuracao


def hoje() -> date:
    return datetime.now(ZoneInfo(obter_configuracao().fuso_horario)).date()
