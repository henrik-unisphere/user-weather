# syntax=docker/dockerfile:1
ARG PYTHON_IMAGE=python:3.13-slim

FROM ${PYTHON_IMAGE} AS builder
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --locked --no-install-project --no-editable

ADD . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

FROM ${PYTHON_IMAGE} AS runtime
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app

ENV PATH="/app/.venv/bin:$PATH"

VOLUME ["/app/app/data"]

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
