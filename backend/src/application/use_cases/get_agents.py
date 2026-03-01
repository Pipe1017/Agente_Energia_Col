"""
Use Cases: Agent Management

- ListAgents     → todos los agentes configurados
- GetAgent       → agente específico por SIC code
- CreateAgent    → registra un nuevo agente
- UpdateAgent    → actualiza perfil del agente
"""
from __future__ import annotations

from dataclasses import dataclass

from ...domain.entities.agent import Agent, RiskProfile
from ...domain.repositories.i_agent_repository import IAgentRepository
from ...domain.value_objects.sic_code import SICCode


class ListAgents:
    def __init__(self, agent_repo: IAgentRepository) -> None:
        self._repo = agent_repo

    async def execute(self) -> list[Agent]:
        return await self._repo.get_all()


class GetAgent:
    def __init__(self, agent_repo: IAgentRepository) -> None:
        self._repo = agent_repo

    async def execute(self, sic_code: str) -> Agent | None:
        return await self._repo.get_by_sic(SICCode(sic_code))


@dataclass
class CreateAgentCommand:
    name: str
    sic_code: str
    risk_profile: str = "moderate"
    resources: list[str] | None = None
    installed_capacity_mw: float | None = None
    variable_cost_cop_kwh: float | None = None


class CreateAgent:
    def __init__(self, agent_repo: IAgentRepository) -> None:
        self._repo = agent_repo

    async def execute(self, cmd: CreateAgentCommand) -> Agent:
        import uuid
        from datetime import datetime, timezone

        existing = await self._repo.get_by_sic(SICCode(cmd.sic_code))
        if existing:
            raise ValueError(f"Agente con SIC {cmd.sic_code} ya existe")

        agent = Agent(
            id=uuid.uuid4(),
            name=cmd.name,
            sic_code=SICCode(cmd.sic_code),
            risk_profile=RiskProfile(cmd.risk_profile),
            resources=cmd.resources or [],
            installed_capacity_mw=cmd.installed_capacity_mw,
            variable_cost_cop_kwh=cmd.variable_cost_cop_kwh,
            created_at=datetime.now(timezone.utc),
        )
        return await self._repo.save(agent)


@dataclass
class UpdateAgentCommand:
    sic_code: str
    risk_profile: str | None = None
    installed_capacity_mw: float | None = None
    variable_cost_cop_kwh: float | None = None
    resources: list[str] | None = None


class UpdateAgent:
    def __init__(self, agent_repo: IAgentRepository) -> None:
        self._repo = agent_repo

    async def execute(self, cmd: UpdateAgentCommand) -> Agent:
        agent = await self._repo.get_by_sic(SICCode(cmd.sic_code))
        if agent is None:
            raise ValueError(f"Agente {cmd.sic_code} no encontrado")

        # Actualizar solo campos provistos
        if cmd.risk_profile is not None:
            object.__setattr__(agent, "risk_profile", RiskProfile(cmd.risk_profile)) \
                if hasattr(agent, "__dataclass_fields__") and agent.__dataclass_fields__["risk_profile"].init \
                else setattr(agent, "risk_profile", RiskProfile(cmd.risk_profile))
        if cmd.installed_capacity_mw is not None:
            agent.installed_capacity_mw = cmd.installed_capacity_mw
        if cmd.variable_cost_cop_kwh is not None:
            agent.variable_cost_cop_kwh = cmd.variable_cost_cop_kwh
        if cmd.resources is not None:
            agent.resources = cmd.resources

        return await self._repo.save(agent)
