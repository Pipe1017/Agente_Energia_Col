from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from ...config import get_settings

logger = logging.getLogger(__name__)


class RedisCache:
    """
    Cache de acceso rápido para predicciones y datos de mercado.
    Falla silenciosamente — si Redis no está disponible, el sistema
    sigue funcionando consultando la base de datos directamente.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

    async def get(self, key: str) -> Any | None:
        try:
            value = await self._client.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.warning("Redis GET falló para key=%s: %s", key, e)
            return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        try:
            await self._client.setex(key, ttl, json.dumps(value, default=str))
        except Exception as e:
            logger.warning("Redis SET falló para key=%s: %s", key, e)

    async def delete(self, key: str) -> None:
        try:
            await self._client.delete(key)
        except Exception as e:
            logger.warning("Redis DELETE falló para key=%s: %s", key, e)

    async def exists(self, key: str) -> bool:
        try:
            return bool(await self._client.exists(key))
        except Exception:
            return False

    async def ping(self) -> bool:
        try:
            return await self._client.ping()
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Keys predefinidos — evita strings mágicos dispersos en el código
    # ------------------------------------------------------------------

    @staticmethod
    def key_latest_prediction(agent_sic_code: str) -> str:
        return f"prediction:latest:{agent_sic_code.upper()}"

    @staticmethod
    def key_latest_recommendation(agent_sic_code: str) -> str:
        return f"recommendation:latest:{agent_sic_code.upper()}"

    @staticmethod
    def key_market_latest() -> str:
        return "market:latest"

    @staticmethod
    def key_agent(sic_code: str) -> str:
        return f"agent:{sic_code.upper()}"
