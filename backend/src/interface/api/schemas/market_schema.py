from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MarketSnapshotResponse(BaseModel):
    timestamp: datetime
    spot_price_cop: float = Field(description="Precio bolsa nacional (COP/kWh)")
    demand_mwh: float = Field(description="Demanda comercial SIN (MWh)")
    hydrology_pct: float = Field(description="Aportes hidrológicos (% del histórico)")
    reservoir_level_pct: float = Field(description="Nivel promedio embalses (%)")
    thermal_dispatch_pct: float = Field(description="Participación térmica en el despacho (%)")
    agent_sic_code: str | None = Field(None, description="SIC del agente (None = sistema general)")

    # Generación por tecnología (GWh/día — fuente SIMEM)
    precio_escasez_cop: float | None = Field(None, description="Precio de escasez (COP/kWh)")
    gen_hidraulica_gwh: float | None = Field(None, description="Generación hidráulica (GWh/día)")
    gen_termica_gwh: float | None = Field(None, description="Generación térmica (GWh/día)")
    gen_solar_gwh: float | None = Field(None, description="Generación solar (GWh/día)")
    gen_eolica_gwh: float | None = Field(None, description="Generación eólica (GWh/día)")

    # Campos derivados calculados en el dominio
    hydrology_status: str = Field(description="Estado hidrológico: crítica/baja/normal/alta")
    is_hydrology_critical: bool
    is_reservoir_low: bool

    model_config = {"from_attributes": True}


class MarketHistoryResponse(BaseModel):
    agent_sic_code: str | None
    start: datetime
    end: datetime
    count: int
    snapshots: list[MarketSnapshotResponse]


class MarketSummaryResponse(BaseModel):
    """Resumen estadístico de un período de mercado."""
    period_hours: int
    avg_price_cop: float
    min_price_cop: float
    max_price_cop: float
    avg_demand_mwh: float
    avg_hydrology_pct: float
    avg_reservoir_pct: float
    current_hydrology_status: str
    latest_timestamp: datetime
