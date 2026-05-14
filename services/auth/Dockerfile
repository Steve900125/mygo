FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY services/auth/pyproject.toml ./services/auth/
RUN uv sync --frozen --no-install-project --package auth
COPY services/auth/ ./services/auth/
RUN uv sync --frozen --package auth
WORKDIR /app/services/auth
EXPOSE 8000

CMD ["sh", "-c", "uv run uvicorn src.main:app --host 0.0.0.0 --port 8000"]