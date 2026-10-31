"""Aplicação FastAPI do site."""

from fastapi import FastAPI

app = FastAPI(title="Maná Diário")


@app.get("/saude")
def saude() -> dict[str, str]:
    return {"status": "ok"}
