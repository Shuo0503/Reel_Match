
FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS builder
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./

RUN uv sync --frozen --no-dev
COPY app/ ./


FROM python:3.12-slim
WORKDIR /app

COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder /app/.venv /app/.venv

COPY --from=builder /app/ ./

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 3000

CMD ["python", "server.py"]
