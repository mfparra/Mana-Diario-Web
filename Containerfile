FROM docker.io/library/python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv

RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 1000 --create-home mana \
    && mkdir -p /app /dados && chown -R 1000:1000 /app /dados

ENV TZ=America/Sao_Paulo \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app
USER 1000

# Dependências antes do código, para aproveitar o cache.
COPY --chown=1000:1000 pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY --chown=1000:1000 src ./src
COPY --chown=1000:1000 prompts ./prompts
COPY --chown=1000:1000 data ./data
RUN uv sync --frozen --no-dev

EXPOSE 8000
CMD ["uvicorn", "mana.web.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
