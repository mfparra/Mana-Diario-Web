"""Hover, foco, Esc e toque do ref-popover.js num Chromium real (Playwright, opcional)."""

import threading
import time

import pytest
import uvicorn

from mana.biblia.referencias import linkar_referencias

sync_api = pytest.importorskip("playwright.sync_api")

HTML = linkar_referencias("Como diz Romanos 8.28, veja Tiago 1.2-4 e Salmos 119.")


@pytest.fixture(scope="module")
def servidor(repo):
    from mana.web.app import app

    config = uvicorn.Config(app, port=8766, log_level="warning")
    srv = uvicorn.Server(config)
    fio = threading.Thread(target=srv.run, daemon=True)
    fio.start()
    while not srv.started:
        time.sleep(0.05)
    yield "http://127.0.0.1:8766"
    srv.should_exit = True
    fio.join(timeout=5)


@pytest.fixture(scope="module")
def navegador():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception:
            pytest.skip("Chromium do Playwright não instalado (uv run playwright install chromium)")
        yield b
        b.close()


def abrir(navegador, servidor, **opcoes):
    ctx = navegador.new_context(**opcoes)
    pg = ctx.new_page()
    erros: list[str] = []
    pg.on("pageerror", lambda e: erros.append(str(e)))
    pg.goto(servidor + "/biblia/genesis/1")
    pg.evaluate(
        "h => { const p = document.createElement('p'); p.innerHTML = h;"
        " document.querySelector('.leitura').prepend(p); }",
        HTML,
    )
    return ctx, pg, erros


def test_hover_foco_esc_e_abrir(navegador, servidor):
    ctx, pg, erros = abrir(navegador, servidor, viewport={"width": 1280, "height": 800})
    pg.hover("a.ref[data-ref='rom.8.28']")
    pg.wait_for_selector("#ref-popover:not([hidden])", timeout=3000)
    assert "E sabemos que todas as coisas" in pg.inner_text("#ref-popover")
    assert "BLIVRE" in pg.inner_text("#ref-popover")
    pg.keyboard.press("Escape")
    assert pg.is_hidden("#ref-popover")
    pg.focus("a.ref[data-ref='jas.1.2-4']")
    pg.wait_for_selector("#ref-popover:not([hidden])", timeout=3000)
    assert pg.get_attribute("a.ref[data-ref='jas.1.2-4']", "aria-describedby") == "ref-popover"
    pg.focus("a.ref[data-ref='psa.119']")
    pg.wait_for_function(
        "document.querySelector('#ref-popover .pop-ref').textContent.startsWith('Salmos')"
    )
    assert "continuar lendo" in pg.inner_text("#ref-popover")
    pg.click("#ref-popover .pop-rodape a")
    pg.wait_for_url("**/biblia/salmos/119")
    assert erros == []
    ctx.close()


def test_toque_abre_no_primeiro_e_navega_no_segundo(navegador, servidor):
    ctx, pg, _ = abrir(
        navegador, servidor, viewport={"width": 375, "height": 700}, has_touch=True, is_mobile=True
    )
    pg.tap("a.ref[data-ref='rom.8.28']")
    pg.wait_for_selector("#ref-popover:not([hidden])", timeout=3000)
    assert pg.url.endswith("/biblia/genesis/1")
    pg.tap("a.ref[data-ref='rom.8.28']")
    pg.wait_for_url("**/biblia/romanos/8#v28")
    ctx.close()
