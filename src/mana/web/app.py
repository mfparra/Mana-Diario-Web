"""Aplicação FastAPI do site."""

from fastapi import FastAPI

from mana.web.rotas import router

app = FastAPI(title="Maná Diário")
app.include_router(router)
