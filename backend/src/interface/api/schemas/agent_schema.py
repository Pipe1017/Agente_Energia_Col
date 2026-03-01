from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AgentBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, examples=["EPM Ituango"])
    sic_code: str = Field(..., min_length=2, max_length=8, examples=["EPMC"])
    risk_profile: str = Field(
        "moderate",
        pattern="^(conservative|moderate|aggressive)$",
        description="Perfil de riesgo del agente",
    )
    installed_capacity_mw: float | None = Field(
        None, gt=0, description="Capacidad instalada en MW (dato privado opcional)"
    )
    variable_cost_cop_kwh: float | None = Field(
        None, ge=0, description="Costo variable en COP/kWh (dato privado opcional)"
    )
    resources: list[str] = Field(
        default_factory=list,
        description="Códigos SIC de plantas asociadas",
    )


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    risk_profile: str | None = Field(
        None, pattern="^(conservative|moderate|aggressive)$"
    )
    installed_capacity_mw: float | None = Field(None, gt=0)
    variable_cost_cop_kwh: float | None = Field(None, ge=0)
    resources: list[str] | None = None


class AgentResponse(AgentBase):
    id: UUID
    created_at: datetime
    is_configured: bool = Field(description="True si el agente tiene datos privados cargados")

    model_config = {"from_attributes": True}
