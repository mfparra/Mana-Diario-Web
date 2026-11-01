"""Aplicação FastAPI do site."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from mana.web.rotas import pagina, repositorio_biblia, router
from mana.web.rotas_estudo import router as router_estudo

app = FastAPI(title="Maná Diário")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.include_router(router)
app.include_router(router_estudo)


@app.exception_handler(StarletteHTTPException)
async def erro_http(request: Request, exc: StarletteHTTPException):
    """404 em HTML para o site; JSON para a API."""
    if exc.status_code != 404 or request.url.path.startswith(("/api/", "/static/")):
        return await http_exception_handler(request, exc)
    repo = request.app.dependency_overrides.get(repositorio_biblia, repositorio_biblia)()
    mensagem = exc.detail if exc.detail != "Not Found" else "Essa página não existe."
    return pagina(request, repo, "404.html", status=404, mensagem=mensagem)
