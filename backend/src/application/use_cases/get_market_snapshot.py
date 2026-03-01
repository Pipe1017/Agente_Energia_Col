"""
Use Case: GetMarketSnapshot

Retorna el snapshot más reciente del mercado para un agente dado.
Si agent_sic_code es None retorna el dato general del SIN.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ...domain.entities.market_data import MarketSnapshot
from ...domain.repositories.i_market_repository import IMarketRepository


@dataclass
class MarketSnapshotResult:
    snapshot: MarketSnapshot
    cached: bool = False


class GetMarketSnapshot:

    def __init__(self, market_repo: IMarketRepository) -> None:
        self._repo = market_repo

    async def execute(
        self, agent_sic_code: str | None = None
    ) -> MarketSnapshotResult | None:
        snapshot = await self._repo.get_latest(agent_sic_code=agent_sic_code)
        if snapshot is None:
            return None
        return MarketSnapshotResult(snapshot=snapshot)


class GetMarketHistory:
    """Retorna histórico de mercado para un rango de fechas."""

    def __init__(self, market_repo: IMarketRepository) -> None:
        self._repo = market_repo

    async def execute(
        self,
        start: datetime,
        end: datetime,
        agent_sic_code: str | None = None,
    ) -> list[MarketSnapshot]:
        return await self._repo.get_range(start, end, agent_sic_code=agent_sic_code)


class GetMarketLastNHours:

    def __init__(self, market_repo: IMarketRepository) -> None:
        self._repo = market_repo

    async def execute(
        self,
        hours: int = 24,
        agent_sic_code: str | None = None,
    ) -> list[MarketSnapshot]:
        return await self._repo.get_last_n_hours(hours, agent_sic_code=agent_sic_code)
