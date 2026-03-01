from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from ..entities.prediction import HourlyPrice, PricePrediction


class IPredictionRepository(ABC):

    @abstractmethod
    async def get_latest(self, agent_sic_code: str) -> PricePrediction | None:
        """Predicción más reciente para el agente."""
        ...

    @abstractmethod
    async def get_by_id(self, prediction_id: UUID) -> PricePrediction | None:
        ...

    @abstractmethod
    async def get_range(
        self,
        agent_sic_code: str,
        start: datetime,
        end: datetime,
    ) -> list[PricePrediction]:
        """Predicciones generadas en el rango de fechas, ordenadas por generated_at DESC."""
        ...

    @abstractmethod
    async def save(self, prediction: PricePrediction) -> PricePrediction:
        ...

    @abstractmethod
    async def update_actuals(
        self,
        prediction_id: UUID,
        actuals: list[HourlyPrice],
    ) -> None:
        """Persiste los precios reales para calcular el error del modelo."""
        ...
