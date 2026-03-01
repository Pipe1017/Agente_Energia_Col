from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from ..entities.recommendation import Recommendation


class IRecommendationRepository(ABC):

    @abstractmethod
    async def get_latest(self, agent_sic_code: str) -> Recommendation | None:
        """Recomendación más reciente para el agente."""
        ...

    @abstractmethod
    async def get_by_id(self, recommendation_id: UUID) -> Recommendation | None:
        ...

    @abstractmethod
    async def get_range(
        self,
        agent_sic_code: str,
        start: datetime,
        end: datetime,
    ) -> list[Recommendation]:
        """Recomendaciones en el rango, ordenadas por generated_at DESC."""
        ...

    @abstractmethod
    async def save(self, recommendation: Recommendation) -> Recommendation:
        ...
