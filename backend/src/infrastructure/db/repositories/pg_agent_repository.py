from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....domain.entities.agent import Agent, RiskProfile
from ....domain.repositories.i_agent_repository import IAgentRepository
from ....domain.value_objects.sic_code import SICCode
from ..models.agent_model import AgentModel


class PgAgentRepository(IAgentRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Mappers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_domain(row: AgentModel) -> Agent:
        return Agent(
            id=row.id,
            name=row.name,
            sic_code=SICCode(row.sic_code),
            risk_profile=RiskProfile(row.risk_profile),
            resources=list(row.resources or []),
            installed_capacity_mw=row.installed_capacity_mw,
            variable_cost_cop_kwh=row.variable_cost_cop_kwh,
            created_at=row.created_at,
        )

    @staticmethod
    def _to_orm(agent: Agent) -> AgentModel:
        return AgentModel(
            id=agent.id,
            name=agent.name,
            sic_code=str(agent.sic_code),
            risk_profile=agent.risk_profile.value,
            resources=agent.resources,
            installed_capacity_mw=agent.installed_capacity_mw,
            variable_cost_cop_kwh=agent.variable_cost_cop_kwh,
            created_at=agent.created_at,
        )

    # ------------------------------------------------------------------
    # Interface implementation
    # ------------------------------------------------------------------

    async def get_all(self) -> list[Agent]:
        result = await self._session.execute(select(AgentModel).order_by(AgentModel.name))
        return [self._to_domain(row) for row in result.scalars().all()]

    async def get_by_id(self, agent_id: UUID) -> Agent | None:
        row = await self._session.get(AgentModel, agent_id)
        return self._to_domain(row) if row else None

    async def get_by_sic(self, sic_code: SICCode | str) -> Agent | None:
        code = str(sic_code).upper()
        result = await self._session.execute(
            select(AgentModel).where(AgentModel.sic_code == code)
        )
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def save(self, agent: Agent) -> Agent:
        orm = self._to_orm(agent)
        self._session.add(orm)
        await self._session.flush()
        return agent

    async def update_risk_profile(
        self, sic_code: SICCode | str, risk_profile: RiskProfile
    ) -> Agent:
        agent = await self.get_by_sic(sic_code)
        if not agent:
            raise ValueError(f"Agente no encontrado: {sic_code}")
        result = await self._session.execute(
            select(AgentModel).where(AgentModel.sic_code == str(sic_code).upper())
        )
        row = result.scalar_one()
        row.risk_profile = risk_profile.value
        await self._session.flush()
        return self._to_domain(row)

    async def update_private_profile(
        self,
        sic_code: SICCode | str,
        installed_capacity_mw: float | None,
        variable_cost_cop_kwh: float | None,
        resources: list[str] | None,
    ) -> Agent:
        result = await self._session.execute(
            select(AgentModel).where(AgentModel.sic_code == str(sic_code).upper())
        )
        row = result.scalar_one_or_none()
        if not row:
            raise ValueError(f"Agente no encontrado: {sic_code}")
        if installed_capacity_mw is not None:
            row.installed_capacity_mw = installed_capacity_mw
        if variable_cost_cop_kwh is not None:
            row.variable_cost_cop_kwh = variable_cost_cop_kwh
        if resources is not None:
            row.resources = resources
        await self._session.flush()
        return self._to_domain(row)

    async def exists(self, sic_code: SICCode | str) -> bool:
        result = await self._session.execute(
            select(AgentModel.id).where(AgentModel.sic_code == str(sic_code).upper())
        )
        return result.scalar_one_or_none() is not None
