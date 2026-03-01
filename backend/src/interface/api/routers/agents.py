from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..deps import AgentRepoDep
from ..schemas.agent_schema import AgentCreate, AgentResponse, AgentUpdate
from ....application.use_cases.get_agents import (
    CreateAgent, CreateAgentCommand,
    GetAgent, ListAgents,
    UpdateAgent, UpdateAgentCommand,
)

router = APIRouter(prefix="/agents", tags=["agents"])


def _agent_to_response(agent) -> AgentResponse:
    return AgentResponse(
        id=agent.id,
        name=agent.name,
        sic_code=str(agent.sic_code),
        risk_profile=agent.risk_profile.value,
        resources=agent.resources,
        installed_capacity_mw=agent.installed_capacity_mw,
        variable_cost_cop_kwh=agent.variable_cost_cop_kwh,
        created_at=agent.created_at,
        is_configured=agent.is_configured,
    )


@router.get("", response_model=list[AgentResponse], summary="Listar todos los agentes")
async def list_agents(repo: AgentRepoDep) -> list[AgentResponse]:
    """
    Retorna todos los agentes configurados en el sistema.
    Usado por el AgentSelector del frontend.
    """
    agents = await ListAgents(repo).execute()
    return [_agent_to_response(a) for a in agents]


@router.get("/{sic_code}", response_model=AgentResponse, summary="Obtener agente por SIC")
async def get_agent(sic_code: str, repo: AgentRepoDep) -> AgentResponse:
    agent = await GetAgent(repo).execute(sic_code.upper())
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agente '{sic_code}' no encontrado",
        )
    return _agent_to_response(agent)


@router.post(
    "",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nuevo agente",
)
async def create_agent(body: AgentCreate, repo: AgentRepoDep) -> AgentResponse:
    try:
        agent = await CreateAgent(repo).execute(
            CreateAgentCommand(
                name=body.name,
                sic_code=body.sic_code.upper(),
                risk_profile=body.risk_profile,
                resources=body.resources,
                installed_capacity_mw=body.installed_capacity_mw,
                variable_cost_cop_kwh=body.variable_cost_cop_kwh,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return _agent_to_response(agent)


@router.patch("/{sic_code}", response_model=AgentResponse, summary="Actualizar perfil del agente")
async def update_agent(sic_code: str, body: AgentUpdate, repo: AgentRepoDep) -> AgentResponse:
    try:
        agent = await UpdateAgent(repo).execute(
            UpdateAgentCommand(
                sic_code=sic_code.upper(),
                risk_profile=body.risk_profile,
                installed_capacity_mw=body.installed_capacity_mw,
                variable_cost_cop_kwh=body.variable_cost_cop_kwh,
                resources=body.resources,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _agent_to_response(agent)
