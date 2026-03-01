from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from ..entities.market_data import MarketSnapshot


class IMarketRepository(ABC):

    @abstractmethod
    async def get_latest(self, agent_sic_code: str | None = None) -> MarketSnapshot | None:
        """Último snapshot disponible del mercado (o del agente)."""
        ...

    @abstractmethod
    async def get_range(
        self,
        start: datetime,
        end: datetime,
        agent_sic_code: str | None = None,
    ) -> list[MarketSnapshot]:
        """Snapshots en un rango de fechas, ordenados por timestamp ASC."""
        ...

    @abstractmethod
    async def get_last_n_hours(
        self,
        hours: int,
        agent_sic_code: str | None = None,
    ) -> list[MarketSnapshot]:
        """Últimas N horas de datos del mercado."""
        ...

    @abstractmethod
    async def bulk_insert(self, snapshots: list[MarketSnapshot]) -> int:
        """Inserta múltiples snapshots. Retorna cantidad insertada."""
        ...

    @abstractmethod
    async def get_average_price(
        self,
        start: datetime,
        end: datetime,
    ) -> float | None:
        """Precio promedio de bolsa en el rango indicado."""
        ...
