# ============================================================
# Agente Energia Col — Backend Dockerfile
# Multi-stage: base → development | production
# Compatible: linux/amd64 (Ubuntu) + linux/arm64 (Mac M4)
# ============================================================

# ------------------------------------------------------------
# Stage base — dependencias comunes
# ------------------------------------------------------------
FROM python:3.11-slim-bookworm AS base

WORKDIR /app

# Dependencias de sistema necesarias para compilar algunos paquetes
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python en capa separada (mejor cache)
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[dev]"

# ------------------------------------------------------------
# Stage development — hot reload, sin copiar código fuente
# (el código se monta como volumen en docker-compose.dev.yml)
# ------------------------------------------------------------
FROM base AS development

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000 5678

CMD ["uvicorn", "src.interfaces.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ------------------------------------------------------------
# Stage production — imagen mínima, usuario no-root
# ------------------------------------------------------------
FROM base AS production

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copiar solo código fuente
COPY src/ ./src/
COPY alembic.ini .

# Usuario no-root
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "src.interfaces.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
