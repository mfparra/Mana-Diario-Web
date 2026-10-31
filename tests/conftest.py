from pathlib import Path

import pytest

from mana.biblia.repositorio import RepositorioBiblia

RAIZ = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def repo() -> RepositorioBiblia:
    caminho = RAIZ / "data" / "biblia" / "biblia.sqlite"
    if not caminho.exists():
        pytest.skip("rode `uv run mana biblia importar` antes")
    return RepositorioBiblia(caminho)
