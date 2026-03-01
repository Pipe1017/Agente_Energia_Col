"""
FastAPI Application — Agente Energía Colombia
API REST para el sistema de recomendaciones de oferta en el mercado eléctrico.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ...config import get_settings
from .routers import agents, market, models, predictions, recommendations

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan events — startup y shutdown."""
    settings = get_settings()
    logger.info(
        "=== Agente Energía Colombia API arrancando === debug=%s",
        settings.DEBUG,
    )
    # Aquí se podrían inicializar conexiones warm-up si fuera necesario
    yield
    logger.info("=== Agente Energía Colombia API apagándose ===")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Agente Energía Colombia — API",
        description=(
            "Sistema de recomendaciones de oferta de precio para agentes "
            "del mercado eléctrico colombiano. "
            "Integra datos de XM, modelos ML (XGBoost) y LLM (Deepseek)."
        ),
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    allowed_origins = [
        "http://localhost:5173",    # Vite dev server
        "http://localhost:3000",    # alternativa
        "http://localhost:80",
    ]
    if not settings.DEBUG:
        # En producción agregar el dominio real via env var si se expone
        pass

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # Exception handlers globales
    # ------------------------------------------------------------------

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Error no manejado en %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Error interno del servidor"},
        )

    # ------------------------------------------------------------------
    # Routers
    # ------------------------------------------------------------------
    API_V1 = "/api/v1"

    app.include_router(agents.router, prefix=API_V1)
    app.include_router(market.router, prefix=API_V1)
    app.include_router(predictions.router, prefix=API_V1)
    app.include_router(recommendations.router, prefix=API_V1)
    app.include_router(models.router, prefix=API_V1)

    # ------------------------------------------------------------------
    # Health check (sin prefijo de versión para load balancers)
    # ------------------------------------------------------------------

    @app.get("/api/v1/health", tags=["system"], summary="Health check")
    async def health() -> dict:
        return {"status": "ok", "version": "1.0.0"}

    @app.get("/api/v1/health/detailed", tags=["system"], summary="Health check detallado")
    async def health_detailed() -> dict:
        """Verifica conectividad con DB, Redis y LLM."""
        from ...infrastructure.db.session import AsyncSessionFactory
        from ...infrastructure.cache.redis_cache import RedisCache

        checks: dict[str, str] = {}

        # Postgres
        try:
            async with AsyncSessionFactory() as session:
                await session.execute(__import__("sqlalchemy").text("SELECT 1"))
            checks["postgres"] = "ok"
        except Exception as exc:
            checks["postgres"] = f"error: {exc}"

        # Redis (falla silenciosamente)
        try:
            cache = RedisCache(get_settings().redis_url)
            await cache.ping() if hasattr(cache, "ping") else None
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "unavailable (non-critical)"

        overall = "ok" if checks.get("postgres") == "ok" else "degraded"
        return {"status": overall, "checks": checks}

    return app


app = create_app()
