# syntax=docker/dockerfile:1
FROM python:3.14-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create app user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install just
RUN curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to /usr/local/bin

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files and README (required by hatchling)
COPY pyproject.toml ./
COPY uv.lock* ./
COPY README.md ./

# Copy package directories needed for editable install
COPY apps/ ./apps/
COPY config/ ./config/

# Install dependencies
RUN uv sync --no-dev

# Copy rest of application
COPY . .

# Change ownership
RUN chown -R appuser:appuser /app

USER appuser

# Expose port
EXPOSE 8000

# Run application
CMD ["uv", "run", "gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
