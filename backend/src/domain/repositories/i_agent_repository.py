from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from ..entities.agent import Agent, RiskProfile
from ..value_objects.sic_code import SICCode


class IAgentRepository(ABC):

    @abstractmethod
    async def get_all(self) -> list[Agent]:
        """Retorna todos los agentes registrados."""
        ...

    @abstractmethod
    async def get_by_id(self, agent_id: UUID) -> Agent | None:
        ...

    @abstractmethod
    async def get_by_sic(self, sic_code: SICCode | str) -> Agent | None:
        ...

    @abstractmethod
    async def save(self, agent: Agent) -> Agent:
        """Crea un nuevo agente. Lanza error si el SIC ya existe."""
        ...

    @abstractmethod
    async def update_risk_profile(
        self, sic_code: SICCode | str, risk_profile: RiskProfile
    ) -> Agent:
        ...

    @abstractmethod
    async def update_private_profile(
        self,
        sic_code: SICCode | str,
        installed_capacity_mw: float | None,
        variable_cost_cop_kwh: float | None,
        resources: list[str] | None,
    ) -> Agent:
        """Actualiza los datos opcionales/privados del agente."""
        ...

    @abstractmethod
    async def exists(self, sic_code: SICCode | str) -> bool:
        ...
