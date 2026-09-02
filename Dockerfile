# syntax=docker/dockerfile:1

FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Create non-root user with home directory
RUN groupadd -r appuser && useradd -r -m -g appuser appuser

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 1. Dependency files first for Docker layer caching
COPY pyproject.toml uv.lock README.md ./

# Install dependencies into .venv (excluding root project package to cache dependencies)
RUN uv sync --frozen --no-dev --no-install-project

# 2. Copy application code
COPY . .

# Install root project package and compile bytecode
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    UV_NO_CACHE=1

# Collect static assets during build
RUN DJANGO_SETTINGS_MODULE=config.settings.prod \
    DJANGO_SECRET_KEY=dummy-build-key \
    python manage.py collectstatic --noinput

# Add Render startup script
COPY start-render.sh /app/start-render.sh
RUN chmod +x /app/start-render.sh

# Set ownership
RUN chown -R appuser:appuser /app /home/appuser

USER appuser

EXPOSE 10000

CMD ["/app/start-render.sh"]